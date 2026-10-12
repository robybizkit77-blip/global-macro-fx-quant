#!/usr/bin/env python3
import csv
import datetime as dt
import io
import json
import urllib.request
from pathlib import Path

POLICY = Path('validation/risk/RISK_SOURCE_POLICY_V1_2026-10-12.json')
OUT = Path('validation/risk-vix-candidate.json')


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
    cfg = policy['gate_inputs']['VIX']
    if cfg['status'] != 'READY':
        raise SystemExit('VIX source is not READY in Risk source policy')

    req = urllib.request.Request(
        cfg['source_url'],
        headers={'User-Agent': 'global-macro-fx-quant/1.0 (+GitHub Actions validation)'}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode('utf-8-sig')

    rows = list(csv.DictReader(io.StringIO(raw)))
    if not rows:
        raise SystemExit('Cboe VIX CSV returned no rows')

    parsed = []
    for row in rows:
        date_raw = (row.get('DATE') or row.get('Date') or '').strip()
        close_raw = (row.get('CLOSE') or row.get('Close') or '').strip()
        if not date_raw or not close_raw:
            continue
        date = dt.datetime.strptime(date_raw, '%m/%d/%Y').date()
        close = float(close_raw)
        if close <= 0:
            raise SystemExit(f'invalid non-positive VIX close on {date}: {close}')
        parsed.append((date, close))

    if not parsed:
        raise SystemExit('no valid Cboe VIX observations parsed')
    parsed.sort(key=lambda x: x[0])
    if len({d for d, _ in parsed}) != len(parsed):
        raise SystemExit('duplicate VIX observation dates detected')

    source_date, source_close = parsed[-1]
    registry_date = dt.date.fromisoformat(policy['as_of'])
    lag = business_days_between(source_date, registry_date)
    if lag < 0:
        raise SystemExit(f'future VIX observation relative to policy as_of: {source_date}')
    if lag > int(cfg['max_business_day_lag_vs_price']):
        raise SystemExit(
            f'VIX candidate stale: latest {source_date}, policy as_of {registry_date}, '
            f'business-day lag {lag} > {cfg["max_business_day_lag_vs_price"]}'
        )

    candidate = {
        'schema': 'GMFQ_RISK_VIX_CANDIDATE_V1',
        'source': {
            'publisher': cfg['publisher'],
            'name': cfg['source_name'],
            'url': cfg['source_url'],
            'field': cfg['field'],
        },
        'policy_as_of': policy['as_of'],
        'latest_date': source_date.isoformat(),
        'latest_value': source_close,
        'business_day_lag': lag,
        'observation_count': len(parsed),
        'status': 'GREEN_SOURCE_CANDIDATE_ONLY',
        'publication_performed': False,
        'runtime_mutated': False,
    }
    OUT.write_text(json.dumps(candidate, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(candidate, indent=2))


if __name__ == '__main__':
    main()
