#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_json(cmd):
    p = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if p.returncode:
        raise SystemExit(p.stdout)
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f'invalid JSON from {cmd}: {exc}\n{p.stdout}')


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture-forward-decision', action='store_true', help='Append an observational Core snapshot only after all existing gates pass.')
    parser.add_argument('--decision-cutoff', help='ISO-8601 cutoff with offset; required with --capture-forward-decision.')
    parser.add_argument('--run-id', help='Stable run identifier; required with --capture-forward-decision.')
    args = parser.parse_args()
    if args.capture_forward_decision and (not args.decision_cutoff or not args.run_id):
        raise SystemExit('--capture-forward-decision requires --decision-cutoff and --run-id')
    price = run_json([sys.executable, 'validation/check_price_controlled_apply_contract_v1.py'])
    liquidity = run_json([sys.executable, 'validation/check_liquidity_remaining_blockers_v1.py'])
    risk = run_json([sys.executable, 'validation/check_risk_brent_hard_blocker_v1.py'])
    live_contract = run_json([sys.executable, 'validation/check_live_update_contract.py'])
    rebuild = run_json([sys.executable, 'validation/rebuild_live_data_runtime.py', '--verify-only'])

    if price.get('status') != 'CONTROLLED_APPLY_PROVEN_PUBLICATION_WITHHELD':
        raise SystemExit(f'Price final-gate drift: {price}')
    if (liquidity.get('ready'), liquidity.get('withheld'), liquidity.get('total')) != (23, 3, 26):
        raise SystemExit(f'Liquidity final-gate drift: {liquidity}')
    if liquidity.get('exact_blockers') != ['CHF.liquidity', 'CHF.credit', 'JPY.liquidity']:
        raise SystemExit(f'Liquidity blocker drift: {liquidity}')
    if risk.get('status') != 'HARD_BLOCKER_CERTIFIED_NO_CONTROLLED_APPLY':
        raise SystemExit(f'Risk final-gate drift: {risk}')
    if live_contract.get('status') != 'PASS':
        raise SystemExit(f'Live update contract failed: {live_contract}')
    if rebuild.get('status') != 'PASS' or rebuild.get('noop_roundtrip_byte_identical') is not True:
        raise SystemExit(f'Rebuild verification failed: {rebuild}')

    rates = load('live_data/sections/NATIVE_RATES_DATA.json')
    expected_ccy = ['AUD', 'CAD', 'CHF', 'EUR', 'GBP', 'JPY', 'NZD', 'USD']
    if sorted(rates.keys()) != expected_ccy:
        raise SystemExit(f'Rates G8 universe drift: {sorted(rates.keys())}')
    for ccy in expected_ccy:
        row = rates[ccy]
        for field in ('date', '2Y', '10Y', 'curve_bp'):
            if row.get(field) is None:
                raise SystemExit(f'Rates missing {ccy}.{field}')

    macro = load('live_data/sections/MACRO_SERIES.json')
    if not isinstance(macro, dict) or sorted(macro.keys()) != expected_ccy:
        raise SystemExit(f'Macro G8 universe drift: {sorted(macro.keys()) if isinstance(macro, dict) else type(macro).__name__}')
    if any(not isinstance(macro[ccy], list) for ccy in expected_ccy):
        raise SystemExit('Macro currency buckets must be lists of canonical series')
    macro_count = sum(len(macro[ccy]) for ccy in expected_ccy)
    if macro_count < 16:
        raise SystemExit(f'Macro canonical series unexpectedly sparse: {macro_count}')

    exact_blockers = [
        {'lane': 'LIQUIDITY', 'key': key, 'state': 'WITHHELD_OVERLAY_ONLY'}
        for key in liquidity['exact_blockers']
    ] + [
        {'lane': 'RISK', 'key': 'Brent', 'state': 'WITHHELD_OVERLAY_ONLY'}
    ]

    receipt = {
        'schema': 'GMFQ_DAILY_DATA_ORCHESTRATOR_FINAL_GATE_RECEIPT_V1',
        'status': 'READY_WITH_DEGRADED_OVERLAYS',
        'operational_state': 'READY_WITH_DOCUMENTED_EXPECTED_GAPS',
        'publishable': True,
        'publication_state': 'ELIGIBLE_WITH_WITHHELD_OVERLAYS',
        'publication_policy': 'CORE_LANES_MAY_PUBLISH_WHILE_NON_CORE_OVERLAYS_FAIL_CLOSED',
        'ready_lanes': ['MACRO', 'RATES', 'PRICE', 'REBUILD'],
        'withheld_lanes': ['LIQUIDITY', 'RISK'],
        'exact_blockers': exact_blockers,
        'lane_receipts': {
            'MACRO': {'currency_count': len(macro), 'series_count': macro_count, 'g8_universe_exact': True},
            'RATES': {'currency_count': len(rates), 'g8_universe_exact': True},
            'PRICE': price,
            'LIQUIDITY': liquidity,
            'RISK': risk,
            'REBUILD': {
                'live_update_contract': live_contract['status'],
                'roundtrip_byte_identical': rebuild['noop_roundtrip_byte_identical'],
            },
        },
        'runtime_mutated': False,
        'promotion_performed': False,
        'live_data_published': False,
        'gh_pages_published': False,
        'automatic_publication': False,
        'forward_decision_logger': {'requested': args.capture_forward_decision, 'observational_only': True},
    }
    if args.capture_forward_decision:
        logger = run_json([
            sys.executable, 'validation/forward/log_core_decision_v1.py',
            '--decision-cutoff', args.decision_cutoff, '--run-id', args.run_id,
        ])
        if logger.get('status') != 'PASS' or logger.get('observational_only') is not True:
            raise SystemExit(f'Forward decision logger failed: {logger}')
        receipt['forward_decision_logger']['receipt'] = logger
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
