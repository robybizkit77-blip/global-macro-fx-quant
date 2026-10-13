#!/usr/bin/env python3
import csv
import io
import json
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


def identify_columns(fieldnames):
    low = {f.lower().strip(): f for f in fieldnames}
    date_col = next((f for f in fieldnames if f.lower().strip() in {'date','datum','period','zeit'}), None)
    value_col = next((f for f in fieldnames if f.lower().strip() in {'value','wert','val'}), None)
    key_col = next((f for f in fieldnames if 'timeseries' in f.lower().replace(' ','') and 'key' in f.lower().replace(' ','')), None)
    if not key_col:
        key_col = next((f for f in fieldnames if 'key' in f.lower()), None)
    return date_col, value_col, key_col


def parse_csv_series(text):
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=';,\t')
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ';'
    rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    if not rows:
        raise SystemExit('SNB CSV returned no data rows')
    fields = list(rows[0].keys())
    date_col, value_col, key_col = identify_columns(fields)
    if not date_col or not value_col:
        raise SystemExit(f'Could not identify SNB CSV date/value columns: {fields}')
    grouped = defaultdict(dict)
    metadata = {}
    for row in rows:
        m = norm_month(row.get(date_col))
        raw = row.get(value_col)
        if not m or raw in (None, ''):
            continue
        try:
            value = float(str(raw).replace("'", '').replace(' ', '').replace(',', '.'))
        except ValueError:
            continue
        key = row.get(key_col) if key_col else None
        if not key:
            # Fall back to all invariant non-date/non-value dimension columns.
            key = '|'.join(f'{k}={row.get(k)}' for k in fields if k not in {date_col, value_col})
        grouped[str(key)][m] = value
        metadata[str(key)] = {k: row.get(k) for k in fields if k not in {date_col, value_col}}
    return fields, grouped, metadata


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
        score = (rounded, exact, -(row['mean_abs_error'] or 1e99))
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
    out.sort(key=lambda x: (x['rounded_1dp_exact'], x['exact'], x['overlap'], -(x['mean_abs_error'] or 1e99)), reverse=True)
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
