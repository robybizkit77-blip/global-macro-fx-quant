#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import date
from pathlib import Path

DEFAULT_RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
SERIES_ID = 'SLOS_BUS_LEND'
SERIES_NAME = 'Overall business lending conditions'
URL = f'https://www.bankofcanada.ca/valet/observations/{SERIES_ID}/json?start_date=2015-01-01'
TOL = 1e-9


def parse_date(value: str) -> date:
    try:
        d = date.fromisoformat(str(value or '').strip())
    except ValueError as exc:
        raise SystemExit(f'invalid ISO date: {value}') from exc
    if d.day != 1 or d.month not in {1, 4, 7, 10}:
        raise SystemExit(f'CAD.conditions date is not a quarter start: {value}')
    return d


def next_quarter(value: str) -> str:
    d = parse_date(value)
    if d.month == 10:
        return f'{d.year + 1:04d}-01-01'
    return f'{d.year:04d}-{d.month + 3:02d}-01'


def fetch_official() -> tuple[dict, dict[str, float]]:
    req = urllib.request.Request(URL, headers={
        'User-Agent': 'global-macro-fx-quant/1.0',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode('utf-8'))
    details = (payload.get('seriesDetail') or {}).get(SERIES_ID) or {}
    label = str(details.get('label') or '').strip()
    if label and label != SERIES_NAME:
        raise SystemExit(f'unexpected BoC SLOS label: {label}')
    observations: dict[str, float] = {}
    for row in payload.get('observations') or []:
        dt = str(row.get('d') or '').strip()
        cell = row.get(SERIES_ID) or {}
        raw = cell.get('v') if isinstance(cell, dict) else cell
        if not dt or raw in (None, ''):
            continue
        parse_date(dt)
        observations[dt] = float(raw)
    if not observations:
        raise SystemExit('BoC SLOS series returned no observations')
    return details, observations


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--runtime', default=str(DEFAULT_RUNTIME))
    ap.add_argument('--out')
    args = ap.parse_args()

    runtime_path = Path(args.runtime)
    payload = json.loads(runtime_path.read_text(encoding='utf-8'))
    lane = payload['CAD']['conditions']
    dates = [str(x) for x in lane.get('dates') or []]
    values = [float(x) for x in lane.get('values') or []]
    if not dates or len(dates) != len(values):
        raise SystemExit('invalid CAD.conditions runtime arrays')
    for dt in dates:
        parse_date(dt)
    if dates[-1] != str(lane.get('last_date')):
        raise SystemExit('CAD.conditions runtime last_date inconsistency')
    if abs(values[-1] - float(lane.get('last_value'))) > TOL:
        raise SystemExit('CAD.conditions runtime last_value inconsistency')

    runtime = dict(zip(dates, values))
    details, official = fetch_official()
    common = sorted(set(runtime) & set(official))
    if len(common) != len(runtime):
        raise SystemExit(f'incomplete CAD SLOS runtime overlap: {len(common)}/{len(runtime)}')
    mismatches = [
        {'date': dt, 'runtime': runtime[dt], 'official': official[dt], 'diff': runtime[dt] - official[dt]}
        for dt in common
        if abs(runtime[dt] - official[dt]) > TOL
    ]
    if mismatches:
        raise SystemExit(f'BoC SLOS current vintage rewrites runtime history: {mismatches[:5]}')

    runtime_last = dates[-1]
    new_dates = sorted(dt for dt in official if dt > runtime_last)
    expected = next_quarter(runtime_last)
    new_observations = []
    for dt in new_dates:
        if dt != expected:
            raise SystemExit(f'non-contiguous CAD SLOS quarter: got {dt}, expected {expected}')
        new_observations.append({'date': dt, 'value': official[dt]})
        expected = next_quarter(dt)

    latest_date = max(official)
    result = {
        'schema': 'GMFQ_LIQUIDITY_CAD_SLOS_CONDITIONS_CANDIDATE_V1',
        'status': 'GREEN_SOURCE_CANDIDATE_ONLY',
        'source': {
            'publisher': 'Bank of Canada',
            'release': 'Senior Loan Officer Survey',
            'transport': 'Valet API',
            'series_id': SERIES_ID,
            'series_name': SERIES_NAME,
            'description': details.get('description'),
            'frequency': 'Quarterly',
            'url': URL,
        },
        'runtime': {
            'lane': 'CAD.conditions',
            'count': len(runtime),
            'last_date': runtime_last,
            'last_value': values[-1],
        },
        'proof': {
            'overlap_count': len(common),
            'exact_match_count': len(common),
            'exact_match_ratio': 1.0,
            'runtime_history_unchanged_by_current_vintage': True,
            'identity_transform': True,
        },
        'latest_date': latest_date,
        'latest_value': official[latest_date],
        'new_observations': new_observations,
        'candidate_update_available': bool(new_observations),
        'candidate_pipeline_ready': True,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + '\n', encoding='utf-8')
    else:
        print(text)


if __name__ == '__main__':
    main()
