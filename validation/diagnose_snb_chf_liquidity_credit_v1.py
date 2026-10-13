#!/usr/bin/env python3
import csv
import io
import json
import re
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
SIGHT_URLS = {
    'MONA_A40': 'https://data.snb.ch/api/warehouse/cube/BSTA.SNB.MONA_U.BIL.AKT.FMI.GGU/data/csv/en?dimSel=KONSOLIDIERUNGSSTUFE(U),INLANDAUSLAND(T),WAEHRUNG(CHF),BANKENGRUPPE(A40)',
    'MIRE_A50': 'https://data.snb.ch/api/warehouse/cube/BSTA.SNB.MIRE_U.MIR.AAK.GGU/data/csv/en?dimSel=KONSOLIDIERUNGSSTUFE(U),INLANDAUSLAND(T),WAEHRUNG(CHF),BANKENGRUPPE(A50)',
}
CREDIT_URL = 'https://data.snb.ch/api/cube/bakredinausbm/data/csv/en'


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'GMFQ-validation/1.0', 'Accept': 'text/csv'})
    with urllib.request.urlopen(req, timeout=90) as r:
        body = r.read()
    if len(body) < 100:
        raise SystemExit(f'SNB response unexpectedly small: {url} bytes={len(body)}')
    return body.decode('utf-8-sig')


def norm_month(v):
    if not v:
        return None
    s = str(v).strip()
    for fmt in ('%Y-%m', '%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m')
        except ValueError:
            pass
    return None


def parse_number(raw):
    if raw in (None, ''):
        return None
    s = str(raw).strip().replace("'", '').replace('\u202f', '').replace(' ', '')
    if s.count(',') == 1 and '.' not in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def runtime_series(key):
    rt = json.loads(RUNTIME.read_text(encoding='utf-8'))
    ccy, name = key.split('.')
    row = rt[ccy][name]
    out = {}
    for d, v in zip(row['dates'], row['values']):
        m = norm_month(d)
        if not m:
            raise SystemExit(f'unparseable runtime date {key}: {d!r}')
        out[m] = float(v)
    return out


def sniff_rows(text):
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=';,\t')
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ';'
    rows = list(csv.reader(io.StringIO(text), dialect=dialect))
    if not rows:
        raise SystemExit('SNB CSV returned no rows')
    width = max(len(r) for r in rows)
    return [r + [''] * (width - len(r)) for r in rows]


def looks_like_series_key(value):
    s = str(value or '').strip()
    return ('@SNB.' in s) or ('{' in s and '}' in s) or bool(re.match(r'^[A-Za-z0-9_]+\{.+\}$', s))


def parse_csv_series(text):
    rows = sniff_rows(text)
    fields = [str(x).strip() for x in rows[0]]

    if fields and fields[0].lower() == 'cubeid' and len(fields) >= 2:
        data_start = next((i for i, row in enumerate(rows[1:], start=1) if norm_month(row[0])), None)
        if data_start is None:
            raise SystemExit(f'SNB wide CSV has no dated observations. Preview={rows[:12]!r}')

        grouped = defaultdict(dict)
        metadata = {}
        for col in range(1, len(fields)):
            descriptors = []
            exact_key = None
            for r in range(0, data_start):
                label = str(rows[r][0]).strip()
                value = str(rows[r][col]).strip()
                if value:
                    descriptors.append({label or f'row_{r}': value})
                    if looks_like_series_key(value):
                        exact_key = value
            if exact_key is None:
                # Some SNB exports keep the cube ID in row 0 and expose the
                # selected dimensions in subsequent metadata rows. Build a
                # deterministic diagnostic identity instead of pretending it
                # is a certified timeseries key.
                base = fields[col] or f'column_{col}'
                suffix = '|'.join(
                    f'{next(iter(d.keys()))}={next(iter(d.values()))}'
                    for d in descriptors[1:]
                    if d
                )
                exact_key = base if not suffix else f'{base}|{suffix}'
            values = {}
            for row in rows[data_start:]:
                m = norm_month(row[0])
                if not m:
                    continue
                value = parse_number(row[col])
                if value is not None:
                    values[m] = value
            if values:
                grouped[exact_key] = values
                metadata[exact_key] = {
                    'column_index': col,
                    'descriptor_rows': descriptors,
                    'certified_key_from_export': any(looks_like_series_key(next(iter(d.values()))) for d in descriptors if d),
                }
        return fields, grouped, metadata

    raise SystemExit(f'Unsupported SNB CSV format. Preview={rows[:12]!r}')


def best_scale_match(runtime, official):
    common = sorted(set(runtime) & set(official))
    scales = [1, 1e-3, 1e3, 1e-6, 1e6]
    best = None
    for scale in scales:
        exact = 0
        rounded = 0
        abs_err = 0.0
        for m in common:
            ov = official[m] * scale
            rv = runtime[m]
            if abs(rv - ov) <= 1e-9:
                exact += 1
            if abs(rv - round(ov, 1)) <= 1e-9:
                rounded += 1
            abs_err += abs(rv - ov)
        row = {
            'scale': scale,
            'overlap': len(common),
            'exact': exact,
            'rounded_1dp_exact': rounded,
            'mean_abs_error': abs_err / len(common) if common else None,
            'first_common': common[0] if common else None,
            'last_common': common[-1] if common else None,
        }
        score = (rounded, exact, -(row['mean_abs_error'] if row['mean_abs_error'] is not None else 1e99))
        if best is None or score > best[0]:
            best = (score, row)
    return best[1] if best else {'overlap': 0}


def rank_candidates(runtime, grouped, metadata):
    out = []
    for key, values in grouped.items():
        cmp = best_scale_match(runtime, values)
        if cmp.get('overlap', 0) == 0:
            continue
        last_rt = max(runtime)
        out.append({
            'series_key': key,
            'metadata': metadata.get(key, {}),
            **cmp,
            'runtime_last_date': last_rt,
            'runtime_last_value': runtime[last_rt],
            'official_on_runtime_last_date_raw': values.get(last_rt),
            'official_latest_date': max(values),
            'official_latest_value_raw': values[max(values)],
        })
    out.sort(key=lambda x: (x['rounded_1dp_exact'], x['exact'], x['overlap'], -(x['mean_abs_error'] if x['mean_abs_error'] is not None else 1e99)), reverse=True)
    return out


def main():
    liq_runtime = runtime_series('CHF.liquidity')
    credit_runtime = runtime_series('CHF.credit')
    result = {
        'schema': 'GMFQ_SNB_CHF_LIQUIDITY_CREDIT_DIAGNOSTIC_V1',
        'status': 'DIAGNOSTIC_ONLY',
        'liquidity': {},
        'credit': {},
    }
    for name, url in SIGHT_URLS.items():
        text = fetch(url)
        fields, grouped, meta = parse_csv_series(text)
        result['liquidity'][name] = {
            'url': url,
            'fields': fields,
            'candidate_count': len(grouped),
            'ranked': rank_candidates(liq_runtime, grouped, meta)[:10],
        }
    text = fetch(CREDIT_URL)
    fields, grouped, meta = parse_csv_series(text)
    result['credit'] = {
        'url': CREDIT_URL,
        'fields': fields,
        'candidate_count': len(grouped),
        'ranked': rank_candidates(credit_runtime, grouped, meta)[:25],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
