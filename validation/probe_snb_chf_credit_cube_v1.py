#!/usr/bin/env python3
import csv
import io
import json
import urllib.request
from datetime import datetime
from pathlib import Path

RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
URL = 'https://data.snb.ch/api/cube/bakredinausbm/data/csv/en?fromDate=2025-07&toDate=2026-07'
SCALES = (1.0, 1e-3, 1e3, 1e-6, 1e6)


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent':'GMFQ-validation/1.0','Accept':'text/csv'})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode('utf-8-sig')


def norm_month(v):
    s = str(v or '').strip()
    for fmt in ('%Y-%m', '%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m')
        except ValueError:
            pass
    return None


def as_float(v):
    s = str(v or '').strip().replace("'", '').replace(' ', '').replace(',', '')
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def runtime_series():
    d = json.loads(RUNTIME.read_text(encoding='utf-8'))['CHF']['credit']
    return {norm_month(x): float(v) for x, v in zip(d['dates'], d['values']) if norm_month(x)}


def compare(rt, raw):
    common = sorted(set(rt) & set(raw))
    best = None
    for scale in SCALES:
        exact = sum(abs(rt[m] - raw[m] * scale) <= 1e-9 for m in common)
        mae = (sum(abs(rt[m] - raw[m] * scale) for m in common) / len(common)) if common else None
        score = (exact, -(mae if mae is not None else 1e99))
        row = {'scale': scale, 'overlap': len(common), 'exact': exact, 'mae': mae}
        if best is None or score > best[0]:
            best = (score, row)
    row = best[1]
    last = max(rt)
    latest = max(raw) if raw else None
    row.update({
        'runtime_last_date': last,
        'runtime_last_value': rt[last],
        'official_raw_on_runtime_last': raw.get(last),
        'official_scaled_on_runtime_last': raw.get(last) * row['scale'] if raw.get(last) is not None else None,
        'official_latest_date': latest,
        'official_latest_raw': raw.get(latest) if latest else None,
    })
    return row


def parse(text):
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=';,\t')
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ';'
    rows = list(csv.reader(io.StringIO(text), dialect=dialect))
    if not rows:
        raise SystemExit('empty SNB CSV')
    width = max(len(r) for r in rows)
    rows = [r + [''] * (width - len(r)) for r in rows]

    data_start = None
    date_idx = None
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            if norm_month(cell):
                data_start, date_idx = i, j
                break
        if data_start is not None:
            break
    if data_start is None:
        raise SystemExit('no dated data rows in SNB CSV')

    numeric_cols = []
    for c in range(width):
        if c == date_idx:
            continue
        n = 0
        for row in rows[data_start:]:
            if norm_month(row[date_idx]) and as_float(row[c]) is not None:
                n += 1
        if n:
            numeric_cols.append((n, c))

    candidates = {}
    if len(numeric_cols) > 1:
        for _, c in numeric_cols:
            raw = {}
            for row in rows[data_start:]:
                m = norm_month(row[date_idx])
                v = as_float(row[c])
                if m and v is not None:
                    raw[m] = v
            header = ' | '.join(str(rows[r][c]).strip() for r in range(data_start) if str(rows[r][c]).strip())
            candidates[f'column_{c}'] = {'identity': header or f'column_{c}', 'raw': raw}
    else:
        if not numeric_cols:
            raise SystemExit('no numeric values in SNB CSV')
        value_idx = numeric_cols[0][1]
        grouped = {}
        for row in rows[data_start:]:
            m = norm_month(row[date_idx])
            v = as_float(row[value_idx])
            if not m or v is None:
                continue
            key_parts = []
            for c, cell in enumerate(row):
                if c in (date_idx, value_idx):
                    continue
                s = str(cell).strip()
                if s:
                    key_parts.append(s)
            key = ' | '.join(key_parts) or 'single_series'
            grouped.setdefault(key, {})[m] = v
        for i, (key, raw) in enumerate(grouped.items()):
            candidates[f'group_{i}'] = {'identity': key, 'raw': raw}

    return {
        'delimiter': getattr(dialect, 'delimiter', None),
        'width': width,
        'data_start_row': data_start,
        'date_column': date_idx,
        'candidate_count': len(candidates),
        'candidates': candidates,
    }


def main():
    rt = runtime_series()
    parsed = parse(fetch(URL))
    ranked = []
    for key, item in parsed['candidates'].items():
        row = {'key': key, 'identity': item['identity'], **compare(rt, item['raw'])}
        ranked.append(row)
    ranked.sort(key=lambda x: (x['exact'], -(x['mae'] if x['mae'] is not None else 1e99)), reverse=True)
    best = ranked[0] if ranked else None
    out = {
        'schema': 'GMFQ_SNB_CHF_CREDIT_CUBE_PROBE_V1',
        'source': {
            'publisher': 'Swiss National Bank',
            'cube': 'bakredinausbm',
            'url': URL,
            'frequency': 'MONTHLY',
        },
        'runtime': {
            'lane': 'CHF.credit',
            'count': len(rt),
            'last_date': max(rt),
            'last_value': rt[max(rt)],
        },
        'parse': {k: v for k, v in parsed.items() if k != 'candidates'},
        'best_candidate': best,
        'top_candidates': ranked[:10],
        'runtime_match_certified': bool(best and best['overlap'] > 0 and best['exact'] == best['overlap']),
        'promotion_performed': False,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
