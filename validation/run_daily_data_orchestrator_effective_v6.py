#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

BASE = Path('validation/run_daily_data_orchestrator_effective_v5.py')
EUR_CREDIT_OVERRIDE = Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_EUR_NFC_CREDIT_REVISION_AWARE_V1_2026-10-13.json')
BASE_POLICY = 'validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json'


def main():
    proc = subprocess.run([sys.executable, str(BASE)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise SystemExit(f'effective v5 failed:\n{proc.stdout}')
    receipt = json.loads(proc.stdout)
    override = json.loads(EUR_CREDIT_OVERRIDE.read_text(encoding='utf-8'))
    if override.get('schema') != 'GMFQ_LIQUIDITY_POLICY_OVERRIDE_V1':
        raise SystemExit('invalid EUR.credit override schema')
    sup = override.get('supersedes') or {}
    if sup.get('policy') != BASE_POLICY or sup.get('subseries') != 'EUR.credit':
        raise SystemExit('EUR.credit override target mismatch')
    row = override.get('effective_row') or {}
    delta = override.get('coverage_delta') or {}

    if row.get('automation_ready') is not True or row.get('controlled_apply_proven') is not True:
        raise SystemExit('EUR.credit controlled apply proof missing')
    if row.get('series_key') != 'BSI.M.U2.N.A.A20.A.1.U2.2240.Z01.E':
        raise SystemExit('EUR.credit ECB series mismatch')
    if row.get('revision_aware_append_only') is not True or row.get('historical_runtime_values_frozen') is not True:
        raise SystemExit('EUR.credit revision-aware safety contract missing')
    if row.get('identity_transform_for_new_observations') is not True:
        raise SystemExit('EUR.credit identity transform for new observations missing')
    if row.get('historical_overlap_count') != 31 or row.get('historical_exact_match_count') != 29:
        raise SystemExit('EUR.credit overlap proof drifted')
    if row.get('historical_revision_mismatch_count') != 2:
        raise SystemExit('EUR.credit revision mismatch count drifted')
    if row.get('official_last_date') != '2026-08' or abs(float(row.get('official_last_value')) - 5462800.13649583) > 1e-6:
        raise SystemExit('EUR.credit official tail mismatch')
    if row.get('collector') != 'validation/fetch_ecb_eur_nfc_loans_revision_aware_candidate.py':
        raise SystemExit('EUR.credit collector mismatch')
    if row.get('applier') != 'validation/apply_ecb_eur_nfc_loans_revision_aware_candidate.py':
        raise SystemExit('EUR.credit applier mismatch')
    if not Path(row['collector']).exists() or not Path(row['applier']).exists():
        raise SystemExit('EUR.credit collector/applier missing')
    if int(delta.get('automation_ready_subseries', 0)) != 1 or int(delta.get('mapping_pending_subseries', 0)) != -1:
        raise SystemExit('EUR.credit coverage delta must be +1 READY / -1 pending')

    liq = receipt['lanes']['LIQUIDITY']
    if liq.get('automation_ready_subseries') != 17 or liq.get('mapping_pending_subseries') != 9:
        raise SystemExit(f'unexpected effective v5 coverage: {liq}')
    liq['verified_subseries'] = 18
    liq['unresolved_subseries'] = 8
    liq['automation_ready_subseries'] = 18
    liq['mapping_pending_subseries'] = 8
    liq.setdefault('source_policy_overrides', []).append(str(EUR_CREDIT_OVERRIDE))
    liq['eur_credit_automation_ready'] = True
    liq['eur_credit_controlled_apply_proven'] = True
    liq['eur_credit_revision_aware_append_only'] = True
    liq['eur_credit_series_key'] = row['series_key']
    liq['eur_credit_collector'] = row['collector']
    liq['eur_credit_applier'] = row['applier']
    liq['eur_credit_apply_proof_run_id'] = row.get('apply_proof_run_id')
    liq['eur_credit_official_tail'] = {'date': row['official_last_date'], 'value': row['official_last_value']}
    liq['reason'] = (
        '26/26 official source families are mapped; 18/26 are automation-ready after the effective V5 '
        'contracts plus the ECB EUR NFC-loans revision-aware append-only controlled-apply promotion. '
        'The remaining 8 stay fail-closed until their exact apply/revision/aggregation contracts are proven.'
    )
    receipt['effective_liquidity_overlay_v6'] = {
        'schema': 'GMFQ_DAILY_DATA_ORCHESTRATOR_EFFECTIVE_LIQUIDITY_OVERLAY_V6',
        'version': '2026-10-13-eur-credit-revision-aware-ready',
        'base_overlay_ready': 17,
        'base_overlay_pending': 9,
        'ready': 18,
        'pending': 8,
        'total': 26,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
