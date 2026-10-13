#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
SERIES_KEY = 'BLS.Q.U2.ALL.O.E.Z.B3.ST.S.WFNET'
TOL = 1e-9


def parse_quarter(value: str) -> tuple[int, int]:
    s = str(value or '').strip()
    if len(s) != 7 or s[4:6] != '-Q' or s[6] not in '1234':
        raise SystemExit(f'invalid quarter: {value}')
    return int(s[:4]), int(s[6])


def next_quarter(value: str) -> str:
    year, quarter = parse_quarter(value)
    return f'{year + 1}-Q1' if quarter == 4 else f'{year}-Q{quarter + 1}'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--runtime', default=str(DEFAULT_RUNTIME))
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    candidate = json.loads(Path(args.candidate).read_text(encoding='utf-8'))
    runtime_path = Path(args.runtime)
    payload = json.loads(runtime_path.read_text(encoding='utf-8'))

    if candidate.get('schema') != 'GMFQ_LIQUIDITY_EUR_BLS_CONDITIONS_CANDIDATE_V1':
        raise SystemExit('invalid EUR BLS candidate schema')
    if candidate.get('status') != 'GREEN_SOURCE_CANDIDATE_ONLY':
        raise SystemExit('EUR BLS candidate is not GREEN')
    if (candidate.get('source') or {}).get('series_key') != SERIES_KEY:
        raise SystemExit('unexpected EUR BLS series key')
    proof = candidate.get('proof') or {}
    if proof.get('runtime_history_unchanged_by_current_vintage') is not True:
        raise SystemExit('EUR BLS runtime history proof missing')
    if proof.get('identity_transform') is not True:
        raise SystemExit('EUR BLS identity-transform proof missing')
    if int(proof.get('overlap_count', 0)) != int(proof.get('exact_match_count', -1)):
        raise SystemExit('EUR BLS runtime overlap is not fully exact')

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

    cand_runtime = candidate.get('runtime') or {}
    if cand_runtime.get('lane') != 'EUR.conditions':
        raise SystemExit('candidate target lane mismatch')
    if str(cand_runtime.get('last_date')) != str(lane.get('last_date')):
        raise SystemExit('candidate built against different EUR.conditions last_date')
    if abs(float(cand_runtime.get('last_value')) - float(lane.get('last_value'))) > TOL:
        raise SystemExit('candidate built against different EUR.conditions last_value')
    if int(cand_runtime.get('count', -1)) != len(dates):
        raise SystemExit('candidate built against different EUR.conditions history length')

    normalized: list[tuple[str, float]] = []
    expected = next_quarter(dates[-1])
    for row in candidate.get('new_observations') or []:
        dt = str(row.get('date') or '')
        parse_quarter(dt)
        value = float(row.get('value'))
        if dt != expected:
            raise SystemExit(f'non-contiguous EUR.conditions quarter: got {dt}, expected {expected}')
        normalized.append((dt, value))
        expected = next_quarter(dt)

    if bool(normalized) != bool(candidate.get('candidate_update_available')):
        raise SystemExit('candidate_update_available disagrees with new_observations')

    updated = json.loads(json.dumps(payload))
    target = updated['EUR']['conditions']
    original_dates = list(target['dates'])
    original_values = list(target['values'])
    for dt, value in normalized:
        target['dates'].append(dt)
        target['values'].append(value)
    if normalized:
        target['last_date'] = normalized[-1][0]
        target['last_value'] = normalized[-1][1]

    if target['dates'][:len(original_dates)] != original_dates:
        raise SystemExit('controlled apply attempted to rewrite EUR.conditions dates')
    if target['values'][:len(original_values)] != original_values:
        raise SystemExit('controlled apply attempted to rewrite EUR.conditions values')
    if len(target['dates']) != len(target['values']):
        raise SystemExit('EUR.conditions arrays diverged after apply')

    changed = updated != payload
    receipt = {
        'schema': 'GMFQ_LIQUIDITY_EUR_BLS_CONDITIONS_APPLY_RECEIPT_V1',
        'status': 'UPDATE_AVAILABLE' if changed else 'NO_CHANGE',
        'series_key': SERIES_KEY,
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
