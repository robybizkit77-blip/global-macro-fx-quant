#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
SERIES_KEY = 'BLS.Q.U2.ALL.O.E.Z.B3.ST.S.WFNET'
API_KEY = SERIES_KEY.removeprefix('BLS.')
TITLE = 'Credit standards-Overall-Enterprise'
BASE = f'https://data-api.ecb.europa.eu/service/data/BLS/{API_KEY}'
TOL = 1e-9


def parse_quarter(value: str) -> tuple[int, int]:
    s = str(value or '').strip()
    if len(s) != 7 or s[4:6] != '-Q' or s[6] not in '1234':
        raise SystemExit(f'invalid quarter: {value}')
    return int(s[:4]), int(s[6])


def next_quarter(value: str) -> str:
    year, quarter = parse_quarter(value)
    return f'{year + 1}-Q1' if quarter == 4 else f'{year}-Q{quarter + 1}'


def fetch_official() -> tuple[dict, dict[str, float], str]:
    url = BASE + '?' + urllib.parse.urlencode({'format': 'csvdata', 'startPeriod': '2016-Q1'})
    req = urllib.request.Request(url, headers={
        'User-Agent': 'global-macro-fx-quant/1.0',
        'Accept': 'text/csv,application/vnd.sdmx.data+csv;version=2.0.0',
    })
    with urllib.request.urlopen(req, timeout=60) as response:
        rows = list(csv.DictReader(io.StringIO(response.read().decode('utf-8-sig'))))
    if not rows:
        raise SystemExit('ECB BLS exact series returned no rows')
    observations: dict[str, float] = {}
    metadata = None
    for row in rows:
        key = str(row.get('KEY') or '').strip()
        if key and key != SERIES_KEY:
            raise SystemExit(f'unexpected ECB BLS series key: {key}')
        title = str(row.get('TITLE') or '').strip()
        if title and title != TITLE:
            raise SystemExit(f'unexpected ECB BLS title: {title}')
        period = str(row.get('TIME_PERIOD') or '').strip()
        raw = row.get('OBS_VALUE')
        if not period or raw in (None, ''):
            continue
        parse_quarter(period)
        observations[period] = float(raw)
        if metadata is None:
            metadata = {k: v for k, v in row.items() if k not in {'TIME_PERIOD', 'OBS_VALUE'} and v not in (None, '')}
    if not observations:
        raise SystemExit('ECB BLS exact series returned no numeric observations')
    return metadata or {}, observations, url


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--runtime', default=str(DEFAULT_RUNTIME))
    ap.add_argument('--out')
    args = ap.parse_args()

    payload = json.loads(Path(args.runtime).read_text(encoding='utf-8'))
    lane = payload['EUR']['conditions']
    dates = [str(x) for x in lane.get('dates') or []]
    values = [float(x) for x in lane.get('values') or []]
    if not dates or len(dates) != len(values):
        raise SystemExit('invalid EUR.conditions runtime arrays')
    for dt in dates:
        parse_quarter(dt)
    if dates[-1] != str(lane.get('last_date')):
        raise SystemExit('EUR.conditions runtime last_date inconsistency')
    if abs(values[-1] - float(lane.get('last_value'))) > TOL:
        raise SystemExit('EUR.conditions runtime last_value inconsistency')

    runtime = dict(zip(dates, values))
    metadata, official, url = fetch_official()
    common = sorted(set(runtime) & set(official))
    if len(common) != len(runtime):
        raise SystemExit(f'incomplete EUR BLS runtime overlap: {len(common)}/{len(runtime)}')
    mismatches = [
        {'date': dt, 'runtime': runtime[dt], 'official': official[dt], 'diff': runtime[dt] - official[dt]}
        for dt in common if abs(runtime[dt] - official[dt]) > TOL
    ]
    if mismatches:
        raise SystemExit(f'ECB BLS current vintage rewrites runtime history: {mismatches[:5]}')

    runtime_last = dates[-1]
    new_dates = sorted((dt for dt in official if dt > runtime_last), key=parse_quarter)
    expected = next_quarter(runtime_last)
    new_observations = []
    for dt in new_dates:
        if dt != expected:
            raise SystemExit(f'non-contiguous EUR BLS quarter: got {dt}, expected {expected}')
        new_observations.append({'date': dt, 'value': official[dt]})
        expected = next_quarter(dt)

    latest_date = max(official, key=parse_quarter)
    result = {
        'schema': 'GMFQ_LIQUIDITY_EUR_BLS_CONDITIONS_CANDIDATE_V1',
        'status': 'GREEN_SOURCE_CANDIDATE_ONLY',
        'source': {
            'publisher': 'European Central Bank / ESCB',
            'dataset': 'BLS',
            'series_key': SERIES_KEY,
            'title': TITLE,
            'title_complete': metadata.get('TITLE_COMPL'),
            'frequency': 'Quarterly',
            'unit': metadata.get('UNIT'),
            'aggregation_method': metadata.get('BLS_AGG_METHOD'),
            'url': url,
        },
        'runtime': {
            'lane': 'EUR.conditions',
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
