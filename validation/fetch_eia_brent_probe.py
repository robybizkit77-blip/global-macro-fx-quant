#!/usr/bin/env python3
import csv
import datetime as dt
import io
import json
import subprocess
from pathlib import Path

POLICY = Path('validation/risk/RISK_SOURCE_POLICY_V1_2026-10-12.json')
OUT = Path('validation/risk-brent-probe.json')
BASE_URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU'


def business_days_between(start: dt.date, end: dt.date) -> int:
    if end < start:
        return -1
    n = 0
    cur = start
    while cur < end:
        cur += dt.timedelta(days=1)
        if cur.weekday() < 5:
            n += 1
    return n


def main():
    policy = json.loads(POLICY.read_text(encoding='utf-8'))
    cfg = policy['gate_inputs']['Brent']
    as_of = dt.date.fromisoformat(policy['as_of'])
    start = as_of - dt.timedelta(days=45)
    url = f'{BASE_URL}&cosd={start.isoformat()}&coed={as_of.isoformat()}'
    tmp = Path('/tmp/DCOILBRENTEU.csv')
    cmd = [
        'curl', '-fL', '--compressed', '--http1.1',
        '--retry', '4', '--retry-all-errors', '--retry-delay', '2',
        '--connect-timeout', '15', '--max-time', '90',
        '-A', 'Mozilla/5.0', url, '-o', str(tmp),
    ]
    subprocess.run(cmd, check=True)
    raw = tmp.read_text(encoding='utf-8-sig')

    rows = list(csv.DictReader(io.StringIO(raw)))
    parsed = []
    for row in rows:
        date_raw = (row.get('observation_date') or row.get('DATE') or '').strip()
        value_raw = (row.get('DCOILBRENTEU') or '').strip()
        if not date_raw or value_raw in ('', '.', 'NA', 'N/A'):
            continue
        date = dt.date.fromisoformat(date_raw)
        value = float(value_raw)
        if value <= 0:
            raise SystemExit(f'invalid Brent value on {date}: {value}')
        parsed.append((date, value))

    if not parsed:
        raise SystemExit('no valid Brent observations parsed')
    parsed.sort(key=lambda x: x[0])
    latest_date, latest_value = parsed[-1]
    lag = business_days_between(latest_date, as_of)
    if lag < 0:
        raise SystemExit(f'future Brent observation relative to policy as_of: {latest_date}')

    max_lag = int(cfg['max_business_day_lag_vs_price'])
    status = 'GREEN_SOURCE_CANDIDATE_ONLY' if lag <= max_lag else 'WITHHELD_OFFICIAL_SOURCE_TOO_SLOW_FOR_GATE'
    result = {
        'schema': 'GMFQ_RISK_BRENT_SOURCE_PROBE_V1',
        'source': {
            'publisher': 'U.S. Energy Information Administration via FRED',
            'series_id': 'DCOILBRENTEU',
            'name': 'Crude Oil Prices: Brent - Europe',
            'url': BASE_URL,
            'frequency': 'Daily',
        },
        'request_window': {
            'start': start.isoformat(),
            'end': as_of.isoformat(),
        },
        'policy_as_of': policy['as_of'],
        'latest_date': latest_date.isoformat(),
        'latest_value': latest_value,
        'business_day_lag': lag,
        'max_business_day_lag': max_lag,
        'status': status,
        'publication_performed': False,
        'runtime_mutated': False,
    }
    OUT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
