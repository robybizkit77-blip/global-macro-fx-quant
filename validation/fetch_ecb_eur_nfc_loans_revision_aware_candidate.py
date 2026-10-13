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
SERIES_KEY = 'BSI.M.U2.N.A.A20.A.1.U2.2240.Z01.E'
API_KEY = SERIES_KEY.removeprefix('BSI.')
BASE = f'https://data-api.ecb.europa.eu/service/data/BSI/{API_KEY}'
TOL = 1e-6


def parse_month(value: str) -> tuple[int, int]:
    s = str(value or '').strip()[:7]
    if len(s) != 7 or s[4] != '-' or not s[:4].isdigit() or not s[5:7].isdigit():
        raise SystemExit(f'invalid month: {value}')
    year, month = int(s[:4]), int(s[5:7])
    if month < 1 or month > 12:
        raise SystemExit(f'invalid month: {value}')
    return year, month


def next_month(value: str) -> str:
    year, month = parse_month(value)
    if month == 12:
        return f'{year + 1:04d}-01'
    return f'{year:04d}-{month + 1:02d}'


def fetch_official(start_period: str) -> tuple[dict, dict[str, float], str]:
    url = BASE + '?' + urllib.parse.urlencode({'format': 'csvdata', 'startPeriod': start_period})
    req = urllib.request.Request(url, headers={
        'User-Agent': 'global-macro-fx-quant/1.0',
        'Accept': 'text/csv,application/vnd.sdmx.data+csv;version=2.0.0',
    })
    with urllib.request.urlopen(req, timeout=60) as response:
        rows = list(csv.DictReader(io.StringIO(response.read().decode('utf-8-sig'))))
    if not rows:
        raise SystemExit('ECB NFC-loans exact series returned no rows')

    observations: dict[str, float] = {}
    metadata = None
    for row in rows:
        key = str(row.get('KEY') or '').strip()
        if key and key != SERIES_KEY:
            raise SystemExit(f'unexpected ECB NFC-loans series key: {key}')
        period = str(row.get('TIME_PERIOD') or '').strip()[:7]
        raw = row.get('OBS_VALUE')
        if not period or raw in (None, ''):
            continue
        parse_month(period)
        observations[period] = float(raw)
        if metadata is None:
            metadata = {k: v for k, v in row.items() if k not in {'TIME_PERIOD', 'OBS_VALUE'} and v not in (None, '')}
    if not observations:
        raise SystemExit('ECB NFC-loans exact series returned no numeric observations')
    return metadata or {}, observations, url


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--runtime', default=str(DEFAULT_RUNTIME))
    ap.add_argument('--out')
    args = ap.parse_args()

    payload = json.loads(Path(args.runtime).read_text(encoding='utf-8'))
    lane = payload['EUR']['credit']
    dates = [str(x)[:7] for x in lane.get('dates') or []]
    values = [float(x) for x in lane.get('values') or []]
    if not dates or len(dates) != len(values):
        raise SystemExit('invalid EUR.credit runtime arrays')
    for dt in dates:
        parse_month(dt)
    if dates[-1] != str(lane.get('last_date'))[:7]:
        raise SystemExit('EUR.credit runtime last_date inconsistency')
    if abs(values[-1] - float(lane.get('last_value'))) > TOL:
        raise SystemExit('EUR.credit runtime last_value inconsistency')

    runtime = dict(zip(dates, values))
    # A two-year overlap is enough to establish continuity while keeping the API request small.
    start_year = max(2000, parse_month(dates[-1])[0] - 2)
    metadata, official, url = fetch_official(f'{start_year:04d}-01')

    common = sorted(set(runtime) & set(official), key=parse_month)
    if len(common) < 12:
        raise SystemExit(f'insufficient EUR.credit overlap for revision-aware contract: {len(common)} months')

    mismatches = []
    exact = 0
    for dt in common:
        diff = runtime[dt] - official[dt]
        if abs(diff) <= TOL:
            exact += 1
        else:
            mismatches.append({'date': dt, 'runtime': runtime[dt], 'official': official[dt], 'diff': diff})

    runtime_last = dates[-1]
    if runtime_last not in official:
        raise SystemExit('official EUR.credit source does not contain runtime last month')

    new_dates = sorted((dt for dt in official if parse_month(dt) > parse_month(runtime_last)), key=parse_month)
    expected = next_month(runtime_last)
    new_observations = []
    for dt in new_dates:
        if dt != expected:
            raise SystemExit(f'non-contiguous EUR.credit month: got {dt}, expected {expected}')
        new_observations.append({'date': dt, 'value': official[dt]})
        expected = next_month(dt)

    latest_date = max(official, key=parse_month)
    result = {
        'schema': 'GMFQ_LIQUIDITY_EUR_NFC_LOANS_REVISION_AWARE_CANDIDATE_V1',
        'status': 'GREEN_SOURCE_CANDIDATE_ONLY',
        'source': {
            'publisher': 'European Central Bank / ESCB',
            'dataset': 'BSI',
            'series_key': SERIES_KEY,
            'frequency': metadata.get('FREQ') or 'Monthly',
            'unit': metadata.get('UNIT'),
            'title': metadata.get('TITLE'),
            'title_complete': metadata.get('TITLE_COMPL'),
            'url': url,
        },
        'runtime': {
            'lane': 'EUR.credit',
            'count': len(dates),
            'last_date': runtime_last,
            'last_value': values[-1],
        },
        'proof': {
            'revision_aware_append_only': True,
            'historical_runtime_values_frozen': True,
            'identity_transform_for_new_observations': True,
            'overlap_count': len(common),
            'exact_match_count': exact,
            'exact_match_ratio': exact / len(common),
            'revision_mismatch_count': len(mismatches),
            'revision_mismatches': mismatches,
            'runtime_last_official_value_current_vintage': official[runtime_last],
            'runtime_last_current_vintage_diff': values[-1] - official[runtime_last],
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
