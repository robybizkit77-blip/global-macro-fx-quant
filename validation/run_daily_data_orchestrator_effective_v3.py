#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

BASE = Path('validation/run_daily_data_orchestrator_effective_v2.py')
EUR_BLS_OVERRIDE = Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_EUR_BLS_CONDITIONS_V1_2026-10-13.json')
BASE_POLICY = 'validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json'


def main():
    proc = subprocess.run([sys.executable, str(BASE)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise SystemExit(f'effective v2 failed:\n{proc.stdout}')
    receipt = json.loads(proc.stdout)
    override = json.loads(EUR_BLS_OVERRIDE.read_text(encoding='utf-8'))
    if override.get('schema') != 'GMFQ_LIQUIDITY_POLICY_OVERRIDE_V1':
        raise SystemExit('invalid EUR.conditions override schema')
    sup = override.get('supersedes') or {}
    if sup.get('policy') != BASE_POLICY or sup.get('subseries') != 'EUR.conditions':
        raise SystemExit('EUR.conditions override target mismatch')
    row = override.get('effective_row') or {}
    delta = override.get('coverage_delta') or {}
    if row.get('automation_ready') is not True or row.get('controlled_apply_proven') is not True:
        raise SystemExit('EUR.conditions controlled apply proof missing')
    if row.get('series_key') != 'BLS.Q.U2.ALL.O.E.Z.B3.ST.S.WFNET':
        raise SystemExit('EUR.conditions series key mismatch')
    if row.get('historical_overlap_count') != 43 or row.get('historical_exact_match_count') != 43 or row.get('historical_exact_match_ratio') != 1.0:
        raise SystemExit('EUR.conditions historical proof drifted')
    if row.get('runtime_history_unchanged_by_current_vintage') is not True or row.get('identity_transform') is not True:
        raise SystemExit('EUR.conditions history/identity proof missing')
    if row.get('official_last_date') != '2026-Q3' or abs(float(row.get('official_last_value')) - 7.294703918588041) > 1e-12:
        raise SystemExit('EUR.conditions official tail mismatch')
    if row.get('collector') != 'validation/fetch_ecb_eur_bls_conditions_candidate.py' or row.get('applier') != 'validation/apply_ecb_eur_bls_conditions_candidate.py':
        raise SystemExit('EUR.conditions collector/applier mismatch')
    if not Path(row['collector']).exists() or not Path(row['applier']).exists():
        raise SystemExit('EUR.conditions collector/applier missing')
    if int(delta.get('automation_ready_subseries', 0)) != 1 or int(delta.get('mapping_pending_subseries', 0)) != -1:
        raise SystemExit('EUR.conditions coverage delta must be +1 READY / -1 pending')

    liq = receipt['lanes']['LIQUIDITY']
    if liq.get('automation_ready_subseries') != 14 or liq.get('mapping_pending_subseries') != 12:
        raise SystemExit(f'unexpected effective v2 coverage: {liq}')
    liq['verified_subseries'] = 15
    liq['unresolved_subseries'] = 11
    liq['automation_ready_subseries'] = 15
    liq['mapping_pending_subseries'] = 11
    liq.setdefault('source_policy_overrides', []).append(str(EUR_BLS_OVERRIDE))
    liq['eur_bls_automation_ready'] = True
    liq['eur_bls_controlled_apply_proven'] = True
    liq['eur_bls_series_key'] = row['series_key']
    liq['eur_bls_collector'] = row['collector']
    liq['eur_bls_applier'] = row['applier']
    liq['eur_bls_apply_proof_run_id'] = row.get('apply_proof_run_id')
    liq['eur_bls_official_tail'] = {'date': row['official_last_date'], 'value': row['official_last_value']}
    liq['reason'] = (
        '26/26 official source families are mapped; 15/26 are automation-ready after the effective V2 '
        'contracts plus the ECB BLS enterprise credit-standards controlled-apply promotion. '
        'The remaining 11 stay fail-closed until their exact apply/revision/aggregation contracts are proven.'
    )
    receipt['effective_liquidity_overlay_v3'] = {
        'schema': 'GMFQ_DAILY_DATA_ORCHESTRATOR_EFFECTIVE_LIQUIDITY_OVERLAY_V3',
        'version': '2026-10-13-eur-bls-ready',
        'base_overlay_ready': 14,
        'base_overlay_pending': 12,
        'ready': 15,
        'pending': 11,
        'total': 26,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
