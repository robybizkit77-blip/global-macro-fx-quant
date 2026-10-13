#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

DEFAULT_RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')


def next_quarter(q):
    y, n = q.split('-Q')
    y, n = int(y), int(n)
    return f'{y+1}-Q1' if n == 4 else f'{y}-Q{n+1}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--runtime', default=str(DEFAULT_RUNTIME))
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    candidate = json.loads(Path(args.candidate).read_text(encoding='utf-8'))
    if candidate.get('schema') != 'GMFQ_LIQUIDITY_GBP_CCS_CONDITIONS_CANDIDATE_V1':
        raise SystemExit('invalid GBP CCS candidate schema')
    proof = candidate.get('proof') or {}
    if proof.get('overlap_count') != 42 or proof.get('exact_match_count') != 42 or proof.get('exact_match_ratio') != 1.0:
        raise SystemExit('GBP CCS full runtime exact-match proof missing')
    if proof.get('runtime_history_unchanged_by_current_vintage') is not True or proof.get('identity_transform') is not True:
        raise SystemExit('GBP CCS history/identity proof missing')

    path = Path(args.runtime)
    data = json.loads(path.read_text(encoding='utf-8'))
    lane = data['GBP']['conditions']
    before_dates = list(lane['dates'])
    before_values = list(lane['values'])
    if len(before_dates) != len(before_values):
        raise SystemExit('runtime GBP.conditions dates/values length mismatch')
    if before_dates[-1] != candidate['runtime']['last_date'] or float(before_values[-1]) != float(candidate['runtime']['last_value']):
        raise SystemExit('runtime tail drifted from collected candidate contract')

    new = candidate.get('new_observations') or []
    expected = next_quarter(before_dates[-1])
    for row in new:
        if row['date'] != expected:
            raise SystemExit(f'non-contiguous append: expected {expected}, got {row["date"]}')
        if row['date'] in before_dates:
            raise SystemExit(f'append would overwrite existing quarter {row["date"]}')
        expected = next_quarter(expected)

    applied = False
    if args.apply and new:
        lane['dates'].extend(row['date'] for row in new)
        lane['values'].extend(float(row['value']) for row in new)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        applied = True

    after_dates = lane['dates']
    after_values = lane['values']
    if after_dates[:len(before_dates)] != before_dates or after_values[:len(before_values)] != before_values:
        raise SystemExit('historical runtime rewrite detected')

    receipt = {
        'schema': 'GMFQ_LIQUIDITY_GBP_CCS_CONDITIONS_APPLY_RECEIPT_V1',
        'source': 'Bank of England Credit Conditions Survey',
        'before_last_date': before_dates[-1],
        'before_last_value': before_values[-1],
        'after_last_date': after_dates[-1],
        'after_last_value': after_values[-1],
        'appended_observations': len(new) if applied else 0,
        'candidate_new_observations': len(new),
        'applied': applied,
        'status': 'APPENDED' if applied else ('DRY_RUN_UPDATE_AVAILABLE' if new else 'NO_CHANGE'),
        'runtime_history_rewritten': False,
        'publication_performed': False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
