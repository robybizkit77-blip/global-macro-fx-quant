#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json'
CHF_LIQ = ROOT / 'validation/liquidity/CHF_SIGHT_DEPOSITS_PROVENANCE_RESOLUTION_2026-10-13.json'
CHF_CREDIT = ROOT / 'validation/liquidity/CHF_CREDIT_PROVENANCE_RESOLUTION_2026-10-13.json'
JPY_LIQ = ROOT / 'validation/liquidity/JPY_RESERVE_PROVENANCE_RESOLUTION_2026-10-13.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    policy = load(POLICY)
    chf_liq = load(CHF_LIQ)
    chf_credit = load(CHF_CREDIT)
    jpy_liq = load(JPY_LIQ)

    if policy['policy'].get('fail_closed') is not True or policy['policy'].get('no_proxy_substitution') is not True:
        raise SystemExit('Liquidity source policy no longer fail-closed/no-proxy')

    mapped = policy.get('mapped', {})
    expected_policy_blockers = {
        'CHF.liquidity': mapped.get('CHF.liquidity'),
        'CHF.credit': mapped.get('CHF.credit'),
        'JPY.liquidity': mapped.get('JPY.liquidity'),
    }
    if any(v is None for v in expected_policy_blockers.values()):
        raise SystemExit(f'missing blocker policy entry: {expected_policy_blockers}')
    if any(v.get('automation_ready') is not False for v in expected_policy_blockers.values()):
        raise SystemExit(f'blocker unexpectedly automation-ready: {expected_policy_blockers}')

    if chf_liq.get('automation_ready') is not False or chf_liq.get('fail_closed') is not True:
        raise SystemExit('CHF.liquidity resolution drift')
    if jpy_liq.get('automation_ready') is not False or jpy_liq.get('fail_closed') is not True:
        raise SystemExit('JPY.liquidity resolution drift')
    chf_credit_resolution = chf_credit.get('resolution') or {}
    if chf_credit_resolution.get('automation_ready') is not False or chf_credit_resolution.get('fail_closed') is not True:
        raise SystemExit('CHF.credit resolution drift')

    impact = chf_credit.get('operational_impact') or {}
    coverage = (
        impact.get('effective_coverage_ready'),
        impact.get('effective_coverage_pending'),
        impact.get('effective_coverage_total'),
    )
    if coverage != (23, 3, 26):
        raise SystemExit(f'Liquidity certified coverage drift: {coverage}')

    for doc in (chf_liq, chf_credit, jpy_liq):
        if doc.get('publication_performed') is not False and (doc.get('operational_impact') or {}).get('publication_performed') is not False:
            raise SystemExit('unexpected publication flag')

    receipt = {
        'schema': 'GMFQ_LIQUIDITY_REMAINING_BLOCKERS_RECEIPT_V1',
        'status': 'CERTIFIED_EXPECTED_GAPS',
        'ready': 23,
        'withheld': 3,
        'total': 26,
        'exact_blockers': ['CHF.liquidity', 'CHF.credit', 'JPY.liquidity'],
        'runtime_mutated': False,
        'publication_performed': False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
