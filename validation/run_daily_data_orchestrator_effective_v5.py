#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

BASE = Path('validation/run_daily_data_orchestrator_effective_v4.py')
JPY_TANKAN_OVERRIDE = Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_JPY_TANKAN_CONDITIONS_V1_2026-10-13.json')
BASE_POLICY = 'validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json'


def main():
    proc = subprocess.run([sys.executable, str(BASE)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise SystemExit(f'effective v4 failed:\n{proc.stdout}')
    receipt = json.loads(proc.stdout)
    override = json.loads(JPY_TANKAN_OVERRIDE.read_text(encoding='utf-8'))
    if override.get('schema') != 'GMFQ_LIQUIDITY_POLICY_OVERRIDE_V1':
        raise SystemExit('invalid JPY.conditions override schema')
    sup = override.get('supersedes') or {}
    if sup.get('policy') != BASE_POLICY or sup.get('subseries') != 'JPY.conditions':
        raise SystemExit('JPY.conditions override target mismatch')
    row = override.get('effective_row') or {}
    delta = override.get('coverage_delta') or {}
    if row.get('automation_ready') is not True or row.get('controlled_apply_proven') is not True:
        raise SystemExit('JPY.conditions controlled apply proof missing')
    if row.get('series_id') != 'TK99F0000612GCQ00000':
        raise SystemExit('JPY.conditions BOJ Tankan series mismatch')
    if row.get('historical_overlap_count') != 42 or row.get('historical_exact_match_count') != 42 or row.get('historical_exact_match_ratio') != 1.0:
        raise SystemExit('JPY.conditions historical exact-match proof drifted')
    if row.get('unique_exact_series_count') != 1:
        raise SystemExit('JPY.conditions unique exact-series proof missing')
    if row.get('runtime_history_unchanged_by_current_vintage') is not True or row.get('identity_transform') is not True:
        raise SystemExit('JPY.conditions history/identity proof missing')
    if row.get('official_last_date') != '2026-Q3' or abs(float(row.get('official_last_value')) - 13.0) > 1e-9:
        raise SystemExit('JPY.conditions official tail mismatch')
    if row.get('collector') != 'validation/fetch_boj_jpy_tankan_lending_attitude_candidate.py' or row.get('applier') != 'validation/apply_boj_jpy_tankan_lending_attitude_candidate.py':
        raise SystemExit('JPY.conditions collector/applier mismatch')
    if not Path(row['collector']).exists() or not Path(row['applier']).exists():
        raise SystemExit('JPY.conditions collector/applier missing')
    if int(delta.get('automation_ready_subseries', 0)) != 1 or int(delta.get('mapping_pending_subseries', 0)) != -1:
        raise SystemExit('JPY.conditions coverage delta must be +1 READY / -1 pending')

    liq = receipt['lanes']['LIQUIDITY']
    if liq.get('automation_ready_subseries') != 16 or liq.get('mapping_pending_subseries') != 10:
        raise SystemExit(f'unexpected effective v4 coverage: {liq}')
    liq['verified_subseries'] = 17
    liq['unresolved_subseries'] = 9
    liq['automation_ready_subseries'] = 17
    liq['mapping_pending_subseries'] = 9
    liq.setdefault('source_policy_overrides', []).append(str(JPY_TANKAN_OVERRIDE))
    liq['jpy_conditions_automation_ready'] = True
    liq['jpy_conditions_controlled_apply_proven'] = True
    liq['jpy_conditions_series_id'] = row['series_id']
    liq['jpy_conditions_collector'] = row['collector']
    liq['jpy_conditions_applier'] = row['applier']
    liq['jpy_conditions_apply_proof_run_id'] = row.get('apply_proof_run_id')
    liq['jpy_conditions_official_tail'] = {'date': row['official_last_date'], 'value': row['official_last_value']}
    liq['reason'] = (
        '26/26 official source families are mapped; 17/26 are automation-ready after the effective V4 '
        'contracts plus the unique exact BOJ Tankan lending-attitude controlled-apply promotion. '
        'The remaining 9 stay fail-closed until their exact apply/revision/aggregation contracts are proven.'
    )
    receipt['effective_liquidity_overlay_v5'] = {
        'schema': 'GMFQ_DAILY_DATA_ORCHESTRATOR_EFFECTIVE_LIQUIDITY_OVERLAY_V5',
        'version': '2026-10-13-jpy-tankan-ready',
        'base_overlay_ready': 16,
        'base_overlay_pending': 10,
        'ready': 17,
        'pending': 9,
        'total': 26,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
