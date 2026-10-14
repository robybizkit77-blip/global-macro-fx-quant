#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')


def month_key(value: str) -> str:
    parts = str(value).split('-')
    if len(parts) < 2:
        raise SystemExit(f'invalid monthly date: {value}')
    y, m = map(int, parts[:2])
    if not 1 <= m <= 12:
        raise SystemExit(f'invalid monthly date: {value}')
    return f'{y:04d}-{m:02d}'


def next_month(value: str) -> str:
    y, m = map(int, month_key(value).split('-'))
    if m == 12:
        return f'{y + 1:04d}-01'
    return f'{y:04d}-{m + 1:02d}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--runtime', default=str(DEFAULT_RUNTIME))
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    candidate = json.loads(Path(args.candidate).read_text(encoding='utf-8'))
    runtime_path = Path(args.runtime)
    liq = json.loads(runtime_path.read_text(encoding='utf-8'))

    if candidate.get('schema') != 'GMFQ_LIQUIDITY_CAD_M2PP_CANDIDATE_V1':
        raise SystemExit('invalid CAD M2++ candidate schema')
    if candidate.get('status') != 'GREEN_SOURCE_CANDIDATE_ONLY':
        raise SystemExit('candidate source proof is not GREEN')
    if candidate.get('runtime_match_confirmed') is not True:
        raise SystemExit('candidate runtime/source match is not confirmed')
    source = candidate.get('source') or {}
    if source.get('series_id') != 'V41552801':
        raise SystemExit('unexpected CAD M2++ series id')

    money = (liq.get('CAD') or {}).get('money') or {}
    dates = list(money.get('dates') or [])
    values = list(money.get('values') or [])
    if len(dates) != len(values) or not dates:
        raise SystemExit('invalid CAD.money runtime arrays')
    if dates[-1] != money.get('last_date'):
        raise SystemExit('CAD.money last_date is inconsistent with dates array')
    if abs(float(values[-1]) - float(money.get('last_value'))) > 1e-9:
        raise SystemExit('CAD.money last_value is inconsistent with values array')

    cand_runtime = candidate.get('runtime') or {}
    if str(cand_runtime.get('last_date')) != str(money.get('last_date')):
        raise SystemExit('candidate was built against a different runtime last_date')
    if abs(float(cand_runtime.get('last_value')) - float(money.get('last_value'))) > 1e-9:
        raise SystemExit('candidate was built against a different runtime last_value')

    normalized = []
    expected_month = next_month(str(money['last_date']))
    for row in candidate.get('new_observations') or []:
        date = str(row.get('date') or '')
        value = float(row.get('value'))
        if month_key(date) != expected_month:
            raise SystemExit(f'non-contiguous CAD M2++ candidate sequence: expected month {expected_month}, got {date}')
        if value <= 0:
            raise SystemExit(f'invalid CAD M2++ candidate value on {date}: {value}')
        normalized.append((date, value))
        expected_month = next_month(date)

    if bool(normalized) != bool(candidate.get('candidate_update_available')):
        raise SystemExit('candidate_update_available flag disagrees with new_observations')

    updated = json.loads(json.dumps(liq))
    target = updated['CAD']['money']
    for date, value in normalized:
        target['dates'].append(date)
        target['values'].append(value)
    if normalized:
        target['last_date'] = normalized[-1][0]
        target['last_value'] = normalized[-1][1]

    changed = updated != liq
    receipt = {
        'schema': 'GMFQ_LIQUIDITY_CAD_M2PP_APPLY_RECEIPT_V1',
        'status': 'UPDATE_AVAILABLE' if changed else 'NO_CHANGE',
        'series_id': 'V41552801',
        'before_last_date': money['last_date'],
        'before_last_value': money['last_value'],
        'after_last_date': target['last_date'],
        'after_last_value': target['last_value'],
        'appended_observations': len(normalized),
        'applied': bool(args.apply and changed),
        'publication_performed': False,
    }

    if args.apply and changed:
        runtime_path.write_text(json.dumps(updated, separators=(',', ':')) + '\n', encoding='utf-8')

    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
