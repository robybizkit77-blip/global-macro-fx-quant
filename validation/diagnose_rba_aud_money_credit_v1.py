#!/usr/bin/env python3
import io
import json
import urllib.request
from datetime import datetime, date
from pathlib import Path

from openpyxl import load_workbook

RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
SOURCES = {
    'AUD.money': {
        'url': 'https://www.rba.gov.au/statistics/tables/xls/d03hist.xlsx',
        'codes': ['DMABMS', 'DMABMN'],
    },
    'AUD.credit': {
        'url': 'https://www.rba.gov.au/statistics/tables/xls/d02hist.xlsx',
        'codes': ['DLCACBS', 'DLCACBN'],
    },
}


def norm_month(v):
    if isinstance(v, (datetime, date)):
        return v.strftime('%Y-%m')
    if isinstance(v, str):
        s = v.strip()
        for fmt in ('%Y-%m-%d', '%Y-%m', '%d/%m/%Y', '%b-%Y', '%b %Y'):
            try:
                return datetime.strptime(s, fmt).strftime('%Y-%m')
            except ValueError:
                pass
    return None


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'GMFQ-validation/1.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    if len(body) < 10000:
        raise SystemExit(f'RBA workbook unexpectedly small: {url} bytes={len(body)}')
    return body


def find_code(ws, code):
    # RBA series identifiers are in the workbook header. Limiting the search to
    # the first 40 rows avoids a full-sheet scan while still failing closed if
    # the table layout changes materially.
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 40)):
        for cell in row:
            if str(cell.value).strip() == code:
                return cell.row, cell.column
    return None


def extract_series(wb, code):
    for ws in wb.worksheets:
        hit = find_code(ws, code)
        if not hit:
            continue
        code_row, col = hit
        out = {}
        for r in range(code_row + 1, ws.max_row + 1):
            val = ws.cell(r, col).value
            if not isinstance(val, (int, float)):
                continue
            month = None
            for dc in range(1, col):
                month = norm_month(ws.cell(r, dc).value)
                if month:
                    break
            if month:
                out[month] = float(val)
        if out:
            return {'sheet': ws.title, 'code_row': code_row, 'column': col, 'values': out}
    return None


def runtime_series(rt, key):
    ccy, name = key.split('.')
    row = rt[ccy][name]
    return {str(d)[:7]: float(v) for d, v in zip(row['dates'], row['values'])}


def compare(runtime, official):
    common = sorted(set(runtime) & set(official))
    exact = []
    mismatches = []
    for m in common:
        rv, ov = runtime[m], official[m]
        if abs(rv - ov) <= 1e-6:
            exact.append(m)
        else:
            mismatches.append({'month': m, 'runtime': rv, 'official': ov, 'diff': rv - ov})
    return {
        'overlap': len(common),
        'exact': len(exact),
        'exact_ratio': (len(exact) / len(common)) if common else 0,
        'mismatches': mismatches[-12:],
        'first_common': common[0] if common else None,
        'last_common': common[-1] if common else None,
    }


def main():
    rt = json.loads(RUNTIME.read_text(encoding='utf-8'))
    result = {'schema': 'GMFQ_RBA_AUD_MONEY_CREDIT_DIAGNOSTIC_V1', 'status': 'DIAGNOSTIC_ONLY', 'results': {}}
    for key, spec in SOURCES.items():
        body = fetch(spec['url'])
        # Normal mode makes repeated cell access deterministic and fast enough
        # for these small RBA workbooks; read_only mode is pathologically slow
        # for the random-access extraction used below.
        wb = load_workbook(io.BytesIO(body), data_only=True, read_only=False)
        runtime = runtime_series(rt, key)
        candidates = {}
        for code in spec['codes']:
            ex = extract_series(wb, code)
            if not ex:
                candidates[code] = {'found': False}
                continue
            cmp = compare(runtime, ex['values'])
            candidates[code] = {
                'found': True,
                'sheet': ex['sheet'],
                'code_row': ex['code_row'],
                'column': ex['column'],
                **cmp,
                'runtime_last_date': max(runtime),
                'runtime_last_value': runtime[max(runtime)],
                'official_on_runtime_last_date': ex['values'].get(max(runtime)),
                'official_latest_date': max(ex['values']),
                'official_latest_value': ex['values'][max(ex['values'])],
            }
        result['results'][key] = {'source_url': spec['url'], 'candidates': candidates}
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
