#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
SERIES_KEY = 'BSI.M.U2.N.A.A20.A.1.U2.2240.Z01.E'
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
    return f'{year + 1:04d}-01' if month == 12 else f'{year:04d}-{month + 1:02d}'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--runtime', default=str(DEFAULT_RUNTIME))
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    candidate = json.loads(Path(args.candidate).read_text(encoding='utf-8'))
    runtime_path = Path(args.runtime)
    payload = json.loads(runtime_path.read_text(encoding='utf-8'))

    if candidate.get('schema') != 'GMFQ_LIQUIDITY_EUR_NFC_LOANS_REVISION_AWARE_CANDIDATE_V1':
        raise SystemExit('invalid EUR.credit candidate schema')
    if candidate.get('status') != 'GREEN_SOURCE_CANDIDATE_ONLY':
        raise SystemExit('EUR.credit candidate is not GREEN')
    if (candidate.get('source') or {}).get('series_key') != SERIES_KEY:
        raise SystemExit('unexpected EUR.credit series key')

    proof = candidate.get('proof') or {}
    if proof.get('revision_aware_append_only') is not True:
        raise SystemExit('EUR.credit revision-aware contract missing')
    if proof.get('historical_runtime_values_frozen') is not True:
        raise SystemExit('EUR.credit historical freeze contract missing')
    if proof.get('identity_transform_for_new_observations') is not True:
        raise SystemExit('EUR.credit identity transform proof missing')
    if int(proof.get('overlap_count', 0)) < 12:
        raise SystemExit('EUR.credit overlap proof too short')

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

    cand_runtime = candidate.get('runtime') or {}
    if cand_runtime.get('lane') != 'EUR.credit':
        raise SystemExit('candidate target lane mismatch')
    if str(cand_runtime.get('last_date'))[:7] != dates[-1]:
        raise SystemExit('candidate built against different EUR.credit last_date')
    if abs(float(cand_runtime.get('last_value')) - values[-1]) > TOL:
        raise SystemExit('candidate built against different EUR.credit last_value')
    if int(cand_runtime.get('count', -1)) != len(dates):
        raise SystemExit('candidate built against different EUR.credit history length')

    normalized: list[tuple[str, float]] = []
    expected = next_month(dates[-1])
    for row in candidate.get('new_observations') or []:
        dt = str(row.get('date') or '')[:7]
        parse_month(dt)
        value = float(row.get('value'))
        if dt != expected:
            raise SystemExit(f'non-contiguous EUR.credit month: got {dt}, expected {expected}')
        normalized.append((dt, value))
        expected = next_month(dt)

    if bool(normalized) != bool(candidate.get('candidate_update_available')):
        raise SystemExit('candidate_update_available disagrees with new_observations')

    updated = json.loads(json.dumps(payload))
    target = updated['EUR']['credit']
    original_dates = list(target['dates'])
    original_values = list(target['values'])

    # Core safety rule: current-vintage revisions are diagnostic only. Existing PIT history is immutable.
    for dt, value in normalized:
        target['dates'].append(dt)
        target['values'].append(value)
    if normalized:
        target['last_date'] = normalized[-1][0]
        target['last_value'] = normalized[-1][1]

    if target['dates'][:len(original_dates)] != original_dates:
        raise SystemExit('controlled apply attempted to rewrite EUR.credit dates')
    if target['values'][:len(original_values)] != original_values:
        raise SystemExit('controlled apply attempted to rewrite EUR.credit historical values')
    if len(target['dates']) != len(target['values']):
        raise SystemExit('EUR.credit arrays diverged after apply')

    changed = updated != payload
    receipt = {
        'schema': 'GMFQ_LIQUIDITY_EUR_NFC_LOANS_REVISION_AWARE_APPLY_RECEIPT_V1',
        'status': 'UPDATE_AVAILABLE' if changed else 'NO_CHANGE',
        'series_key': SERIES_KEY,
        'before_last_date': lane['last_date'],
        'before_last_value': lane['last_value'],
        'after_last_date': target['last_date'],
        'after_last_value': target['last_value'],
        'appended_observations': len(normalized),
        'applied': bool(args.apply and changed),
        'runtime_history_rewritten': False,
        'revision_aware_append_only': True,
        'publication_performed': False,
    }
    if args.apply and changed:
        runtime_path.write_text(json.dumps(updated, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
