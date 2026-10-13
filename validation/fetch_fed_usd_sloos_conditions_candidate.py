#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
PACKAGE = 'e64f07187815f0e7ed89237d8cb91eeb'
BASE = 'https://www.federalreserve.gov/datadownload/Output.aspx'
SERIES_ID = 'SLOOS/SLOOS/SUBLPDCILS_N.Q'
SERIES_CODE = 'SUBLPDCILS_N.Q'
SERIES_NAME = 'Net percentage of domestic banks tightening standards for C&I loans to large and middle-market firms'
TOL = 1e-9


def norm_date(value: str) -> str | None:
    raw = str(value or '').strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
        return raw
    if re.fullmatch(r'\d{4}Q[1-4]', raw):
        year = int(raw[:4])
        quarter = int(raw[-1])
        month = 1 + 3 * (quarter - 1)
        return f'{year:04d}-{month:02d}-01'
    return None


def as_float(value: str) -> float | None:
    raw = str(value or '').strip().replace(',', '')
    if raw in {'', 'NA', 'N/A', '.'}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def fetch_text() -> tuple[str, str, str]:
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
    with urllib.request.urlopen(req, timeout=60) as response:
        body = response.read().decode('utf-8-sig', errors='replace')
        content_type = response.headers.get('Content-Type', '')
    if not body.strip():
        raise SystemExit('empty Federal Reserve SLOOS DDP response')
    return url, content_type, body


def parse_exact_series(text: str) -> tuple[list[str], dict[str, float]]:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise SystemExit('empty parsed SLOOS CSV')
    width = max(len(row) for row in rows)
    rows = [row + [''] * (width - len(row)) for row in rows]

    data_start = None
    date_col = None
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            if norm_date(cell):
                data_start, date_col = i, j
                break
        if data_start is not None:
            break
    if data_start is None or date_col is None:
        raise SystemExit('no dated rows found in SLOOS CSV')

    matches: list[tuple[int, list[str]]] = []
    for col in range(width):
        if col == date_col:
            continue
        metadata = [str(rows[r][col]).strip() for r in range(data_start) if str(rows[r][col]).strip()]
        if SERIES_ID in metadata and SERIES_CODE in metadata:
            matches.append((col, metadata))
    if len(matches) != 1:
        raise SystemExit(f'expected exactly one exact SLOOS series column, found {len(matches)}')

    col, metadata = matches[0]
    if SERIES_NAME not in metadata:
        raise SystemExit('exact SLOOS series name metadata missing')

    observations: dict[str, float] = {}
    for row in rows[data_start:]:
        dt = norm_date(row[date_col])
        value = as_float(row[col])
        if dt and value is not None:
            observations[dt] = value
    if not observations:
        raise SystemExit('exact SLOOS series returned no observations')
    return metadata, observations


def next_quarter(date_iso: str) -> str:
    year, month, day = map(int, date_iso.split('-'))
    if day != 1 or month not in {1, 4, 7, 10}:
        raise SystemExit(f'non-quarter-start date in USD.conditions contract: {date_iso}')
    if month == 10:
        return f'{year + 1:04d}-01-01'
    return f'{year:04d}-{month + 3:02d}-01'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--runtime', default=str(DEFAULT_RUNTIME))
    ap.add_argument('--out')
    args = ap.parse_args()

    runtime_path = Path(args.runtime)
    payload = json.loads(runtime_path.read_text(encoding='utf-8'))
    lane = payload['USD']['conditions']
    dates = [norm_date(x) for x in lane.get('dates') or []]
    values = [float(x) for x in lane.get('values') or []]
    if not dates or len(dates) != len(values) or any(x is None for x in dates):
        raise SystemExit('invalid USD.conditions runtime arrays')
    if dates[-1] != norm_date(lane.get('last_date')):
        raise SystemExit('USD.conditions runtime last_date inconsistency')
    if abs(values[-1] - float(lane.get('last_value'))) > TOL:
        raise SystemExit('USD.conditions runtime last_value inconsistency')

    runtime = {str(d): v for d, v in zip(dates, values)}
    url, content_type, body = fetch_text()
    metadata, official = parse_exact_series(body)

    common = sorted(set(runtime) & set(official))
    if len(common) != len(runtime):
        raise SystemExit(f'incomplete SLOOS runtime overlap: {len(common)}/{len(runtime)}')
    mismatches = [
        {'date': dt, 'runtime': runtime[dt], 'official': official[dt], 'diff': runtime[dt] - official[dt]}
        for dt in common
        if abs(runtime[dt] - official[dt]) > TOL
    ]
    if mismatches:
        raise SystemExit(f'SLOOS current vintage rewrites runtime history: {mismatches[:5]}')

    runtime_last = str(dates[-1])
    new_dates = sorted(dt for dt in official if dt > runtime_last)
    expected = next_quarter(runtime_last)
    new_observations = []
    for dt in new_dates:
        if dt != expected:
            raise SystemExit(f'non-contiguous SLOOS quarterly observation: got {dt}, expected {expected}')
        new_observations.append({'date': dt, 'value': official[dt]})
        expected = next_quarter(dt)

    latest_date = max(official)
    latest_value = official[latest_date]
    out = {
        'schema': 'GMFQ_LIQUIDITY_USD_SLOOS_CONDITIONS_CANDIDATE_V1',
        'status': 'GREEN_SOURCE_CANDIDATE_ONLY',
        'source': {
            'publisher': 'Board of Governors of the Federal Reserve System',
            'release': 'Senior Loan Officer Opinion Survey on Bank Lending Practices',
            'transport': 'Federal Reserve Board Data Download Program',
            'package_id': PACKAGE,
            'series_id': SERIES_ID,
            'series_code': SERIES_CODE,
            'series_name': SERIES_NAME,
            'frequency': 'Quarterly',
            'unit': 'Percentage',
            'url': url,
            'content_type': content_type,
            'metadata': metadata,
        },
        'runtime': {
            'lane': 'USD.conditions',
            'count': len(runtime),
            'last_date': runtime_last,
            'last_value': values[-1],
        },
        'proof': {
            'overlap_count': len(common),
            'exact_match_count': len(common),
            'exact_match_ratio': 1.0,
            'runtime_history_unchanged_by_current_vintage': True,
        },
        'latest_date': latest_date,
        'latest_value': latest_value,
        'new_observations': new_observations,
        'candidate_update_available': bool(new_observations),
        'candidate_pipeline_ready': True,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    text = json.dumps(out, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + '\n', encoding='utf-8')
    else:
        print(text)


if __name__ == '__main__':
    main()
