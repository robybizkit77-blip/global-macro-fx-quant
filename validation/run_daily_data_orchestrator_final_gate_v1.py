#!/usr/bin/env python3
from __future__ import annotations

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
    macro_count = len(macro) if isinstance(macro, dict) else len(macro or [])
    if macro_count < 16:
        raise SystemExit(f'Macro canonical series unexpectedly sparse: {macro_count}')

    exact_blockers = [
        {'lane': 'LIQUIDITY', 'key': key, 'state': 'EXPECTED_GAP_WITHHELD'}
        for key in liquidity['exact_blockers']
    ] + [
        {'lane': 'RISK', 'key': 'Brent', 'state': 'EXPECTED_GAP_WITHHELD'}
    ]

    receipt = {
        'schema': 'GMFQ_DAILY_DATA_ORCHESTRATOR_FINAL_GATE_RECEIPT_V1',
        'status': 'EXPECTED_GAP_WITHHELD',
        'operational_state': 'READY_WITH_DOCUMENTED_EXPECTED_GAPS',
        'publishable': False,
        'publication_state': 'WITHHELD',
        'ready_lanes': ['MACRO', 'RATES', 'PRICE', 'REBUILD'],
        'withheld_lanes': ['LIQUIDITY', 'RISK'],
        'exact_blockers': exact_blockers,
        'lane_receipts': {
            'MACRO': {'series_count': macro_count, 'present': True},
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
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
