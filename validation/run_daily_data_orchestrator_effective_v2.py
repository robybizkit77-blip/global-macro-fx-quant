#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

BASE = Path('validation/run_daily_data_orchestrator_effective_v1.py')
GBP_OVERRIDE = Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_GBP_CCS_CONDITIONS_V1_2026-10-13.json')
BASE_POLICY = 'validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json'


def main():
    proc = subprocess.run([sys.executable, str(BASE)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise SystemExit(f'effective v1 failed:\n{proc.stdout}')
    receipt = json.loads(proc.stdout)
    override = json.loads(GBP_OVERRIDE.read_text(encoding='utf-8'))
    if override.get('schema') != 'GMFQ_LIQUIDITY_POLICY_OVERRIDE_V1':
        raise SystemExit('invalid GBP.conditions override schema')
    sup = override.get('supersedes') or {}
    if sup.get('policy') != BASE_POLICY or sup.get('subseries') != 'GBP.conditions':
        raise SystemExit('GBP.conditions override target mismatch')
    row = override.get('effective_row') or {}
    delta = override.get('coverage_delta') or {}
    if row.get('automation_ready') is not True or row.get('controlled_apply_proven') is not True:
        raise SystemExit('GBP.conditions controlled apply proof missing')
    if row.get('series_key') != 'CCS_CORPORATE_AVAILABILITY_OVERALL_PAST_3M':
        raise SystemExit('GBP.conditions series key mismatch')
    if row.get('historical_overlap_count') != 42 or row.get('historical_exact_match_count') != 42 or row.get('historical_exact_match_ratio') != 1.0:
        raise SystemExit('GBP.conditions historical proof drifted')
    if row.get('runtime_history_unchanged_by_current_vintage') is not True or row.get('identity_transform') is not True:
        raise SystemExit('GBP.conditions history/identity proof missing')
    if row.get('official_last_date') != '2026-Q3' or float(row.get('official_last_value')) != -0.1:
        raise SystemExit('GBP.conditions official tail mismatch')
    if row.get('collector') != 'validation/fetch_boe_gbp_credit_conditions_candidate.py' or row.get('applier') != 'validation/apply_boe_gbp_credit_conditions_candidate.py':
        raise SystemExit('GBP.conditions collector/applier mismatch')
    if not Path(row['collector']).exists() or not Path(row['applier']).exists():
        raise SystemExit('GBP.conditions collector/applier missing')
    if int(delta.get('automation_ready_subseries', 0)) != 1 or int(delta.get('mapping_pending_subseries', 0)) != -1:
        raise SystemExit('GBP.conditions coverage delta must be +1 READY / -1 pending')

    liq = receipt['lanes']['LIQUIDITY']
    if liq.get('automation_ready_subseries') != 13 or liq.get('mapping_pending_subseries') != 13:
        raise SystemExit(f'unexpected effective v1 coverage: {liq}')
    liq['verified_subseries'] = 14
    liq['unresolved_subseries'] = 12
    liq['automation_ready_subseries'] = 14
    liq['mapping_pending_subseries'] = 12
    liq.setdefault('source_policy_overrides', []).append(str(GBP_OVERRIDE))
    liq['gbp_ccs_automation_ready'] = True
    liq['gbp_ccs_controlled_apply_proven'] = True
    liq['gbp_ccs_series_key'] = row['series_key']
    liq['gbp_ccs_collector'] = row['collector']
    liq['gbp_ccs_applier'] = row['applier']
    liq['gbp_ccs_apply_proof_run_id'] = row.get('apply_proof_run_id')
    liq['gbp_ccs_official_tail'] = {'date': row['official_last_date'], 'value': row['official_last_value']}
    liq['reason'] = (
        '26/26 official source families are mapped; 14/26 are automation-ready after the effective V1 '
        'contracts plus the Bank of England CCS corporate credit-availability controlled-apply promotion. '
        'The remaining 12 stay fail-closed until their exact apply/revision/aggregation contracts are proven.'
    )
    receipt['effective_liquidity_overlay_v2'] = {
        'schema': 'GMFQ_DAILY_DATA_ORCHESTRATOR_EFFECTIVE_LIQUIDITY_OVERLAY_V2',
        'version': '2026-10-13-gbp-ccs-ready',
        'base_overlay_ready': 13,
        'base_overlay_pending': 13,
        'ready': 14,
        'pending': 12,
        'total': 26,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
