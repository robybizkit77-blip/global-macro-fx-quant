#!/usr/bin/env python3
import csv
import io
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
PACKAGE = 'e64f07187815f0e7ed89237d8cb91eeb'
BASE = 'https://www.federalreserve.gov/datadownload/Output.aspx'
TOL = 1e-9


def fetch_text():
    params = {
        'rel': 'SLOOS',
        'series': PACKAGE,
        'lastObs': '',
        'from': '',
        'to': '',
        'filetype': 'csv',
        'label': 'include',
        'layout': 'seriescolumn',
        'type': 'package',
    }
    url = BASE + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'User-Agent': 'global-macro-fx-quant/1.0',
        'Accept': 'text/csv,*/*;q=0.8',
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode('utf-8-sig', errors='replace')
        ctype = r.headers.get('Content-Type', '')
    if not body.strip():
        raise SystemExit('empty Federal Reserve SLOOS DDP response')
    return url, ctype, body


def norm_date(s):
    s = str(s or '').strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
        return s
    if re.fullmatch(r'\d{4}Q[1-4]', s):
        y = int(s[:4]); q = int(s[-1]); m = 1 + 3 * (q - 1)
        return f'{y:04d}-{m:02d}-01'
    return None


def as_float(s):
    s = str(s or '').strip().replace(',', '')
    if s in {'', 'NA', 'N/A', '.'}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def runtime():
    d = json.loads(RUNTIME.read_text(encoding='utf-8'))['USD']['conditions']
    dates = [norm_date(x) for x in d['dates']]
    if any(x is None for x in dates):
        raise SystemExit('unrecognized USD.conditions runtime date')
    return d, {date: float(value) for date, value in zip(dates, d['values'])}


def parse_columns(text):
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise SystemExit('empty parsed SLOOS CSV')
    width = max(len(r) for r in rows)
    rows = [r + [''] * (width - len(r)) for r in rows]

    date_row_start = None
    date_col = None
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            if norm_date(cell):
                date_row_start, date_col = i, j
                break
        if date_row_start is not None:
            break
    if date_row_start is None:
        raise SystemExit('no dated rows found in SLOOS CSV')

    candidates = []
    for c in range(width):
        if c == date_col:
            continue
        data = {}
        for row in rows[date_row_start:]:
            dt = norm_date(row[date_col])
            value = as_float(row[c])
            if dt and value is not None:
                data[dt] = value
        if not data:
            continue
        meta_cells = []
        for r in range(date_row_start):
            value = str(rows[r][c]).strip()
            if value:
                meta_cells.append(value)
        candidates.append({
            'column': c,
            'metadata': meta_cells,
            'observations': data,
        })
    return rows, date_row_start, date_col, candidates


def score(rt, candidate):
    off = candidate['observations']
    common = sorted(set(rt) & set(off))
    exact = [d for d in common if abs(rt[d] - off[d]) <= TOL]
    diffs = [abs(rt[d] - off[d]) for d in common]
    return {
        'column': candidate['column'],
        'metadata': candidate['metadata'],
        'overlap': len(common),
        'exact': len(exact),
        'exact_ratio': (len(exact) / len(common)) if common else 0.0,
        'mae': (sum(diffs) / len(diffs)) if diffs else None,
        'max_abs_diff': max(diffs) if diffs else None,
        'first_overlap': common[0] if common else None,
        'last_overlap': common[-1] if common else None,
        'last_runtime': rt[common[-1]] if common else None,
        'last_source': off[common[-1]] if common else None,
    }


def main():
    lane, rt = runtime()
    url, ctype, body = fetch_text()
    _, start, date_col, candidates = parse_columns(body)
    ranked = [score(rt, c) for c in candidates]
    ranked.sort(key=lambda x: (x['exact'], x['overlap'], -(x['mae'] if x['mae'] is not None else 1e99)), reverse=True)
    best = ranked[0] if ranked else None
    full_exact = [x for x in ranked if x['overlap'] == len(rt) and x['exact'] == len(rt)]
    out = {
        'schema': 'GMFQ_LIQUIDITY_USD_SLOOS_MAPPING_DIAGNOSTIC_V1',
        'source': {
            'publisher': 'Board of Governors of the Federal Reserve System',
            'release': 'Senior Loan Officer Opinion Survey on Bank Lending Practices',
            'transport': 'Federal Reserve Board Data Download Program',
            'package_id': PACKAGE,
            'url': url,
            'content_type': ctype,
        },
        'runtime': {
            'lane': 'USD.conditions',
            'label': lane.get('label'),
            'count': len(rt),
            'last_date': norm_date(lane['last_date']),
            'last_value': float(lane['last_value']),
        },
        'parse': {
            'data_start_row': start,
            'date_column': date_col,
            'candidate_columns': len(candidates),
        },
        'best_candidate': best,
        'full_exact_match_count': len(full_exact),
        'full_exact_matches': full_exact,
        'runtime_match_certified': len(full_exact) == 1,
        'automation_ready': False,
        'promotion_performed': False,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
