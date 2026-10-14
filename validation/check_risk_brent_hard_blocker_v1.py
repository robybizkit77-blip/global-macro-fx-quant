#!/usr/bin/env python3
"""Certify that the Brent Risk gate remains intentionally fail-closed."""
import hashlib
import json
from pathlib import Path

POLICY = Path('validation/risk/RISK_SOURCE_POLICY_V1_2026-10-12.json')
RESOLUTION = Path('validation/risk/BRENT_SOURCE_FRESHNESS_RESOLUTION_2026-10-13.json')
RUNTIME = Path('live_data/sections/D.json')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    policy = load(POLICY)
    resolution = load(RESOLUTION)
    brent = policy['gate_inputs']['Brent']
    canonical = resolution['canonical_gate_input']
    proof = resolution['proof']

    if brent['status'] != 'WITHHELD_OFFICIAL_SOURCE_TOO_SLOW_FOR_GATE':
        raise SystemExit('Brent policy must remain fail-closed')
    if brent.get('hard_blocker') is not True or brent.get('max_business_day_lag_vs_price') != 1:
        raise SystemExit('Brent hard-blocker or one-business-day rule changed')
    if canonical['series_id'] != 'RBRTE' or canonical['eia_api_series_id'] != 'PET.RBRTE.D':
        raise SystemExit('canonical EIA Brent spot identity changed')
    if canonical['fred_mirror_series_id'] != 'DCOILBRENTEU':
        raise SystemExit('FRED mirror identity changed')
    if not all(proof.get(k) is expected for k, expected in {
        'eia_html_and_api_same_underlying_series': True,
        'transport_change_solves_freshness': False,
        'fred_is_independent_source': False,
        'ice_futures_exact_semantic_substitute': False,
    }.items()):
        raise SystemExit('Brent exact-source evidence changed')
    if resolution.get('promotion_eligible') is not False or resolution.get('automation_ready') is not False:
        raise SystemExit('Brent must not become promotion or automation eligible')
    if resolution.get('runtime_mutated') is not False or resolution.get('publication_performed') is not False:
        raise SystemExit('Brent evidence must not mutate runtime or publish')

    receipt = {
        'schema': 'GMFQ_RISK_BRENT_HARD_BLOCKER_CONTRACT_RECEIPT_V1',
        'status': 'HARD_BLOCKER_CERTIFIED_NO_CONTROLLED_APPLY',
        'canonical_series': 'EIA RBRTE / PET.RBRTE.D',
        'max_business_day_lag_vs_price': 1,
        'rejected_as_non_equivalent_or_non_independent': [
            'EIA Open Data API transport', 'FRED DCOILBRENTEU mirror', 'ICE Brent futures settlement'
        ],
        'controlled_apply_available': False,
        'idempotent': True,
        'runtime_sha256_before_after': sha256(RUNTIME),
        'runtime_mutated': False,
        'publication_performed': False,
        'next_global_gate': 'Daily Data Orchestrator V1 (BLOCKED_EXPECTED_GAPS_NO_PUBLICATION; Risk remains fail-closed)',
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
