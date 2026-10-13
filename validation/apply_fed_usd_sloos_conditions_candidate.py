#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

DEFAULT_RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
SERIES_ID = 'SLOOS/SLOOS/SUBLPDCILS_N.Q'
TOL = 1e-9


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(str(value or '').strip())
    except ValueError as exc:
        raise SystemExit(f'invalid ISO date: {value}') from exc


def next_quarter(value: str) -> str:
    d = parse_date(value)
    if d.day != 1 or d.month not in {1, 4, 7, 10}:
        raise SystemExit(f'USD.conditions date is not a quarter start: {value}')
    if d.month == 10:
        return f'{d.year + 1:04d}-01-01'
    return f'{d.year:04d}-{d.month + 3:02d}-01'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--runtime', default=str(DEFAULT_RUNTIME))
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    candidate = json.loads(Path(args.candidate).read_text(encoding='utf-8'))
    runtime_path = Path(args.runtime)
    payload = json.loads(runtime_path.read_text(encoding='utf-8'))

    if candidate.get('schema') != 'GMFQ_LIQUIDITY_USD_SLOOS_CONDITIONS_CANDIDATE_V1':
        raise SystemExit('invalid USD SLOOS candidate schema')
    if candidate.get('status') != 'GREEN_SOURCE_CANDIDATE_ONLY':
        raise SystemExit('USD SLOOS candidate is not GREEN')
    source = candidate.get('source') or {}
    if source.get('series_id') != SERIES_ID:
        raise SystemExit('unexpected USD SLOOS series id')
    proof = candidate.get('proof') or {}
    if proof.get('runtime_history_unchanged_by_current_vintage') is not True:
        raise SystemExit('USD SLOOS runtime history proof missing')
    if int(proof.get('overlap_count', 0)) != int(proof.get('exact_match_count', -1)):
        raise SystemExit('USD SLOOS runtime overlap is not fully exact')

    lane = payload['USD']['conditions']
    dates = list(lane.get('dates') or [])
    values = list(lane.get('values') or [])
    if not dates or len(dates) != len(values):
        raise SystemExit('invalid USD.conditions runtime arrays')
    if str(dates[-1]) != str(lane.get('last_date')):
        raise SystemExit('USD.conditions runtime last_date inconsistency')
    if abs(float(values[-1]) - float(lane.get('last_value'))) > TOL:
        raise SystemExit('USD.conditions runtime last_value inconsistency')

    cand_runtime = candidate.get('runtime') or {}
    if cand_runtime.get('lane') != 'USD.conditions':
        raise SystemExit('candidate target lane mismatch')
    if str(cand_runtime.get('last_date')) != str(lane.get('last_date')):
        raise SystemExit('candidate built against different USD.conditions last_date')
    if abs(float(cand_runtime.get('last_value')) - float(lane.get('last_value'))) > TOL:
        raise SystemExit('candidate built against different USD.conditions last_value')
    if int(cand_runtime.get('count', -1)) != len(dates):
        raise SystemExit('candidate built against different USD.conditions history length')

    new_rows = candidate.get('new_observations') or []
    expected = next_quarter(str(lane['last_date']))
    normalized: list[tuple[str, float]] = []
    previous = parse_date(str(lane['last_date']))
    for row in new_rows:
        dt = str(row.get('date') or '')
        value = float(row.get('value'))
        parsed = parse_date(dt)
        if parsed <= previous:
            raise SystemExit(f'non-increasing USD.conditions candidate date: {dt}')
        if dt != expected:
            raise SystemExit(f'non-contiguous USD.conditions quarter: got {dt}, expected {expected}')
        normalized.append((dt, value))
        previous = parsed
        expected = next_quarter(dt)

    if bool(normalized) != bool(candidate.get('candidate_update_available')):
        raise SystemExit('candidate_update_available disagrees with new_observations')

    updated = json.loads(json.dumps(payload))
    target = updated['USD']['conditions']
    original_dates = list(target['dates'])
    original_values = list(target['values'])
    for dt, value in normalized:
        target['dates'].append(dt)
        target['values'].append(value)
    if normalized:
        target['last_date'] = normalized[-1][0]
        target['last_value'] = normalized[-1][1]

    if target['dates'][:len(original_dates)] != original_dates:
        raise SystemExit('controlled apply attempted to rewrite USD.conditions dates')
    if target['values'][:len(original_values)] != original_values:
        raise SystemExit('controlled apply attempted to rewrite USD.conditions values')
    if len(target['dates']) != len(target['values']):
        raise SystemExit('USD.conditions arrays diverged after apply')

    changed = updated != payload
    receipt = {
        'schema': 'GMFQ_LIQUIDITY_USD_SLOOS_CONDITIONS_APPLY_RECEIPT_V1',
        'status': 'UPDATE_AVAILABLE' if changed else 'NO_CHANGE',
        'series_id': SERIES_ID,
        'before_last_date': lane['last_date'],
        'before_last_value': lane['last_value'],
        'after_last_date': target['last_date'],
        'after_last_value': target['last_value'],
        'appended_observations': len(normalized),
        'applied': bool(args.apply and changed),
        'runtime_history_rewritten': False,
        'publication_performed': False,
    }
    if args.apply and changed:
        runtime_path.write_text(json.dumps(updated, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
