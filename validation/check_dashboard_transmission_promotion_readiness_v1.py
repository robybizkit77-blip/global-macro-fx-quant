#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'validation/DASHBOARD_PAIR_RENDER_PAYLOAD_V1_2026-10-07.json'
EVIDENCE = ROOT / 'validation/CENTRAL_BANK_REACTION_FUNCTION_EVIDENCE_MAP_V3_2026-10-07.json'
OUT = ROOT / 'validation/DASHBOARD_TRANSMISSION_PROMOTION_READINESS_V1_2026-10-07.json'


def main() -> None:
    p = json.loads(PAYLOAD.read_text(encoding='utf-8'))
    e = json.loads(EVIDENCE.read_text(encoding='utf-8'))
    pairs = p['pairs']
    currencies = e['currencies']

    state_counts = Counter(v['state'] for v in pairs.values())
    robust_counts = Counter(v['robustness_badge'] for v in pairs.values())
    currency_status = {k: v['evidence_status'] for k, v in currencies.items()}

    blockers = []
    warnings = []

    if len(pairs) != 28:
        blockers.append('PAIR_COVERAGE_NOT_28')
    if robust_counts['RULE_SENSITIVE'] > 0:
        warnings.append(f"RULE_SENSITIVE_PAIRS={robust_counts['RULE_SENSITIVE']}")
    if state_counts['TRANSMISSION_WITHHELD'] > 0:
        warnings.append(f"WITHHELD_CURRENT_PAIRS={state_counts['TRANSMISSION_WITHHELD']}")

    withheld_ccy = [c for c,s in currency_status.items() if s.startswith('WITHHELD')]
    weak_ccy = [c for c,s in currency_status.items() if s in {'NO_INCREMENTAL_VALUE','PROMISING_SMALL_SAMPLE'}]
    if withheld_ccy:
        blockers.append('HISTORICAL_REACTION_EVIDENCE_WITHHELD:' + ','.join(sorted(withheld_ccy)))
    if weak_ccy:
        warnings.append('REACTION_EVIDENCE_NOT_PRODUCTION_GRADE:' + ','.join(sorted(weak_ccy)))

    guards = p['guards']
    if guards.get('predictive_claim') is not False:
        blockers.append('PREDICTIVE_CLAIM_PRESENT')
    if guards.get('return_fitting') is not False:
        blockers.append('RETURN_FITTING_PRESENT')
    if guards.get('production_promotion') is not False:
        blockers.append('ALREADY_MARKED_FOR_PRODUCTION')

    # Promotion requires forward evidence, not merely current descriptive coherence.
    blockers.append('FORWARD_VALIDATION_NOT_YET_ACCUMULATED')

    result = {
        'schema': 'GMFQ_DASHBOARD_TRANSMISSION_PROMOTION_READINESS_V1',
        'status': 'NOT_READY_FOR_PRODUCTION' if blockers else 'READY_FOR_CONTROLLED_PROMOTION',
        'created_at': '2026-10-07',
        'scope': 'Transmission/causal UI layer only; frozen macro engine remains unchanged.',
        'current_snapshot': {
            'pair_count': len(pairs),
            'state_counts': dict(state_counts),
            'robustness_counts': dict(robust_counts),
            'currency_evidence_status': currency_status,
        },
        'blockers': blockers,
        'warnings': warnings,
        'what_is_ready_now': [
            'Research-only UI payload for 28 crosses',
            'Current descriptive CLEAN/PARTIAL/DIVERGENT/WITHHELD states',
            'Robustness badge across three non-return-fitted descriptive rules',
            'Separate historical-evidence badge',
        ],
        'what_is_not_ready': [
            'Using transmission state to change macro bias',
            'Using transmission state for trade sizing or entry rules',
            'Claiming predictive edge from CLEAN/DIVERGENT labels',
            'Production promotion before forward validation and unresolved withheld evidence',
        ],
        'recommended_next_gate': 'FORWARD_SNAPSHOT_LEDGER_V1',
        'recommended_rule': 'Freeze current descriptive classifier, append timestamped forward snapshots, and evaluate later without retroactive label changes.',
        'engine_changed': False,
        'live_data_changed': False,
        'oos_baseline_changed': False,
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
