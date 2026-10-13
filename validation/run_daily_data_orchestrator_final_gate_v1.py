#!/usr/bin/env python3
"""Classify the certified daily lanes without authorising any runtime write or publication."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'validation' / 'run_daily_data_orchestrator_effective_price_v1.py'


def run_base() -> dict:
    proc = subprocess.run(
        [sys.executable, str(BASE)], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if proc.returncode:
        raise SystemExit(proc.stdout)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f'effective orchestrator emitted invalid JSON: {exc}\n{proc.stdout}')


def main() -> None:
    base = run_base()
    lanes = base.get('lanes') or {}
    price = lanes.get('PRICE') or {}
    liq = lanes.get('LIQUIDITY') or {}
    risk = lanes.get('RISK') or {}

    if price.get('state') != 'CONTROLLED_APPLY_PROVEN_PUBLICATION_WITHHELD':
        raise SystemExit(f'Price certification not reflected in global gate: {price}')
    if price.get('controlled_apply_proven') is not True or price.get('idempotent_apply_proven') is not True:
        raise SystemExit('Price global readiness requires proven idempotent controlled apply')
    if price.get('persistent_publication_enabled') is not False or price.get('publication_eligible') is not False:
        raise SystemExit('Price must remain publication-withheld')

    if (liq.get('automation_ready_subseries'), liq.get('mapping_pending_subseries'), liq.get('total_subseries')) != (23, 3, 26):
        raise SystemExit(f'Liquidity coverage drift: {liq}')
    liq_overlay = base.get('effective_liquidity_overlay_v11') or {}
    liquidity_gaps = liq_overlay.get('remaining_fail_closed')
    if liquidity_gaps != ['CHF.liquidity', 'CHF.credit', 'JPY.liquidity']:
        raise SystemExit(f'Liquidity exact blockers drift: {liquidity_gaps}')

    if risk.get('state') != 'BLOCKED_BRENT_OFFICIAL_SOURCE_TOO_SLOW_FOR_GATE' or risk.get('guard_proven') is not True:
        raise SystemExit(f'Risk Brent hard blocker drift: {risk}')
    if risk.get('brent_exact_equivalent_timely_source_proven') is not False:
        raise SystemExit('Risk gate cannot accept a Brent proxy')

    for key in ('promotion_performed', 'live_data_published', 'gh_pages_published', 'automatic_publication'):
        if base.get(key) is not False:
            raise SystemExit(f'base receipt unsafe {key}={base.get(key)!r}')

    exact_blockers = [
        {'lane': 'LIQUIDITY', 'key': key, 'state': 'EXPECTED_GAP_WITHHELD', 'reason': 'Exact provenance/control path remains unproven; no substitute is permitted.'}
        for key in liquidity_gaps
    ] + [
        {'lane': 'RISK', 'key': 'Brent', 'state': 'EXPECTED_GAP_WITHHELD', 'reason': 'Canonical EIA spot is beyond the one-business-day gate; no semantically equivalent timely source is proven.'}
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
            'PRICE': {'state': price['state'], 'controlled_apply_proven': True, 'persistent_publication_enabled': False},
            'LIQUIDITY': {'ready_subseries': 23, 'withheld_subseries': 3, 'total_subseries': 26},
            'RISK': {'state': risk['state'], 'brent_guard_proven': True},
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
