#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'validation' / 'risk' / 'RISK_SOURCE_POLICY_V1_2026-10-12.json'
DEFAULT_OUT = Path('/tmp/gmfq-vix-candidate.json')


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


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': 'GMFQ/1.0 VIX official-source collector'})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode('utf-8-sig')


def parse_date(raw: str) -> dt.date:
    raw = raw.strip()
    for fmt in ('%m/%d/%Y', '%Y-%m-%d'):
        try:
            return dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    raise ValueError(f'unrecognized Cboe date: {raw!r}')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--as-of', help='PIT freshness reference date YYYY-MM-DD; defaults to current UTC date')
    ap.add_argument('--out', default=str(DEFAULT_OUT))
    args = ap.parse_args()

    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else dt.datetime.now(dt.timezone.utc).date()
    policy = json.loads(POLICY.read_text(encoding='utf-8'))
    cfg = policy['gate_inputs']['VIX']
    if cfg.get('status') != 'READY' or cfg.get('publisher') != 'Cboe Global Markets':
        raise SystemExit(f'VIX source policy is not READY/Cboe: {cfg}')
    if int(cfg.get('max_business_day_lag_vs_price')) != 1:
        raise SystemExit('unexpected VIX max business-day lag policy')

    text = fetch_text(cfg['source_url'])
    rows = []
    seen = set()
    reader = csv.DictReader(io.StringIO(text))
    required = {'DATE', 'CLOSE'}
    if not reader.fieldnames or not required.issubset({x.strip().upper() for x in reader.fieldnames}):
        raise SystemExit(f'unexpected Cboe VIX CSV columns: {reader.fieldnames}')

    field_map = {x.strip().upper(): x for x in reader.fieldnames}
    for row in reader:
        day = parse_date(row[field_map['DATE']])
        if day > as_of:
            continue
        if day in seen:
            raise SystemExit(f'duplicate VIX date from Cboe: {day}')
        seen.add(day)
        value = float(row[field_map['CLOSE']])
        if value <= 0:
            raise SystemExit(f'invalid VIX close on {day}: {value}')
        rows.append({'date': day.isoformat(), 'value': value})

    if not rows:
        raise SystemExit('no Cboe VIX observations found on/before as-of')
    rows.sort(key=lambda x: x['date'])
    latest_date = dt.date.fromisoformat(rows[-1]['date'])
    lag = business_days_between(latest_date, as_of)
    max_lag = int(cfg['max_business_day_lag_vs_price'])
    if lag < 0:
        raise SystemExit(f'future VIX observation relative to as-of: {latest_date} > {as_of}')
    if lag > max_lag:
        raise SystemExit(f'VIX source stale at as-of {as_of}: latest={latest_date}, business_day_lag={lag}, max={max_lag}')

    receipt = {
        'schema': 'GMFQ_RISK_VIX_CANDIDATE_V2',
        'as_of': as_of.isoformat(),
        'source': {
            'publisher': cfg['publisher'],
            'name': cfg['source_name'],
            'url': cfg['source_url'],
            'field': cfg['field'],
            'frequency': cfg['frequency'],
        },
        'latest_date': rows[-1]['date'],
        'latest_value': rows[-1]['value'],
        'business_day_lag': lag,
        'max_business_day_lag': max_lag,
        'observation_count': len(rows),
        'observations': rows,
        'status': 'GREEN_OFFICIAL_SOURCE_CANDIDATE',
        'runtime_mutated': False,
        'publication_performed': False,
    }
    out = Path(args.out)
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'observations'}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
