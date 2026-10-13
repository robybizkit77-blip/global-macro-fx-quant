#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

BASE = Path('validation/run_daily_data_orchestrator_effective_v3.py')
JPY_M3_OVERRIDE = Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_JPY_M3_V1_2026-10-13.json')
BASE_POLICY = 'validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json'


def main():
    proc = subprocess.run([sys.executable, str(BASE)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise SystemExit(f'effective v3 failed:\n{proc.stdout}')
    receipt = json.loads(proc.stdout)
    override = json.loads(JPY_M3_OVERRIDE.read_text(encoding='utf-8'))
    if override.get('schema') != 'GMFQ_LIQUIDITY_POLICY_OVERRIDE_V1':
        raise SystemExit('invalid JPY.money override schema')
    sup = override.get('supersedes') or {}
    if sup.get('policy') != BASE_POLICY or sup.get('subseries') != 'JPY.money':
        raise SystemExit('JPY.money override target mismatch')
    row = override.get('effective_row') or {}
    delta = override.get('coverage_delta') or {}
    if row.get('automation_ready') is not True or row.get('controlled_apply_proven') is not True:
        raise SystemExit('JPY.money controlled apply proof missing')
    if row.get('series_id') != 'MAM1XAM3M3MO':
        raise SystemExit('JPY.money BOJ series mismatch')
    if row.get('historical_overlap_count') != 128 or row.get('historical_exact_match_count') != 128 or row.get('historical_exact_match_ratio') != 1.0:
        raise SystemExit('JPY.money historical exact-match proof drifted')
    if row.get('unique_exact_series_count') != 1:
        raise SystemExit('JPY.money unique exact-series proof missing')
    if row.get('runtime_history_unchanged_by_current_vintage') is not True or row.get('identity_transform') is not True:
        raise SystemExit('JPY.money history/identity proof missing')
    if row.get('official_last_date') != '2026-08' or abs(float(row.get('official_last_value')) - 16377129.0) > 1e-6:
        raise SystemExit('JPY.money official tail mismatch')
    if row.get('collector') != 'validation/fetch_boj_jpy_m3_exact_candidate.py' or row.get('applier') != 'validation/apply_boj_jpy_m3_exact_candidate.py':
        raise SystemExit('JPY.money collector/applier mismatch')
    if not Path(row['collector']).exists() or not Path(row['applier']).exists():
        raise SystemExit('JPY.money collector/applier missing')
    if int(delta.get('automation_ready_subseries', 0)) != 1 or int(delta.get('mapping_pending_subseries', 0)) != -1:
        raise SystemExit('JPY.money coverage delta must be +1 READY / -1 pending')

    liq = receipt['lanes']['LIQUIDITY']
    if liq.get('automation_ready_subseries') != 15 or liq.get('mapping_pending_subseries') != 11:
        raise SystemExit(f'unexpected effective v3 coverage: {liq}')
    liq['verified_subseries'] = 16
    liq['unresolved_subseries'] = 10
    liq['automation_ready_subseries'] = 16
    liq['mapping_pending_subseries'] = 10
    liq.setdefault('source_policy_overrides', []).append(str(JPY_M3_OVERRIDE))
    liq['jpy_m3_automation_ready'] = True
    liq['jpy_m3_controlled_apply_proven'] = True
    liq['jpy_m3_series_id'] = row['series_id']
    liq['jpy_m3_collector'] = row['collector']
    liq['jpy_m3_applier'] = row['applier']
    liq['jpy_m3_apply_proof_run_id'] = row.get('apply_proof_run_id')
    liq['jpy_m3_official_tail'] = {'date': row['official_last_date'], 'value': row['official_last_value']}
    liq['reason'] = (
        '26/26 official source families are mapped; 16/26 are automation-ready after the effective V3 '
        'contracts plus the unique exact BOJ seasonally-adjusted M3 controlled-apply promotion. '
        'The remaining 10 stay fail-closed until their exact apply/revision/aggregation contracts are proven.'
    )
    receipt['effective_liquidity_overlay_v4'] = {
        'schema': 'GMFQ_DAILY_DATA_ORCHESTRATOR_EFFECTIVE_LIQUIDITY_OVERLAY_V4',
        'version': '2026-10-13-jpy-m3-ready',
        'base_overlay_ready': 15,
        'base_overlay_pending': 11,
        'ready': 16,
        'pending': 10,
        'total': 26,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
