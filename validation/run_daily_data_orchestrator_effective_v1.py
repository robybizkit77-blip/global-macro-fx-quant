#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

BASE = Path('validation/run_daily_data_orchestrator_v1.py')
AUD_OVERRIDE = Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_AUD_ES_V1_2026-10-13.json')
EUR_OVERRIDE = Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_EUR_M3_V1_2026-10-13.json')
BASE_POLICY = 'validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def validate_override(obj, subseries):
    if obj.get('schema') != 'GMFQ_LIQUIDITY_POLICY_OVERRIDE_V1':
        raise SystemExit(f'invalid liquidity override schema for {subseries}')
    sup = obj.get('supersedes') or {}
    if sup.get('policy') != BASE_POLICY or sup.get('subseries') != subseries:
        raise SystemExit(f'liquidity override target mismatch for {subseries}')
    return obj.get('effective_row') or {}, obj.get('coverage_delta') or {}


def main():
    proc = subprocess.run(
        [sys.executable, str(BASE)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f'base orchestrator failed:\n{proc.stdout}')
    try:
        receipt = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f'base orchestrator emitted invalid JSON: {exc}\n{proc.stdout}')

    eur_row, eur_delta = validate_override(load(EUR_OVERRIDE), 'EUR.money')
    aud_row, aud_delta = validate_override(load(AUD_OVERRIDE), 'AUD.liquidity')

    if eur_row.get('automation_ready') is not False:
        raise SystemExit('EUR.money must remain fail-closed')
    if eur_row.get('series_key') != 'BSI.M.U2.Y.V.M30.X.1.U2.2300.Z01.E':
        raise SystemExit('EUR.money effective series mismatch')

    if aud_row.get('automation_ready') is not True:
        raise SystemExit('AUD.liquidity effective override must be automation-ready')
    if aud_row.get('series_key') != 'AESAT':
        raise SystemExit('AUD.liquidity effective series must remain RBA AESAT')
    if aud_row.get('controlled_apply_proven') is not True:
        raise SystemExit('AUD.liquidity controlled apply proof missing')
    if aud_row.get('applier') != 'validation/apply_rba_aud_es_balances_candidate.py':
        raise SystemExit('AUD.liquidity applier mismatch')
    if not Path(aud_row['applier']).exists():
        raise SystemExit('AUD.liquidity applier file missing')

    liq = receipt['lanes']['LIQUIDITY']
    # Base V1 already applies the EUR fail-closed override. Apply AUD delta only here.
    if liq.get('automation_ready_subseries') != 10 or liq.get('mapping_pending_subseries') != 16:
        raise SystemExit(f'unexpected base effective liquidity coverage: {liq}')
    if int(aud_delta.get('automation_ready_subseries', 0)) != 1 or int(aud_delta.get('mapping_pending_subseries', 0)) != -1:
        raise SystemExit('AUD liquidity coverage delta must be +1 READY / -1 pending')
    if int(eur_delta.get('automation_ready_subseries', 0)) != -1 or int(eur_delta.get('mapping_pending_subseries', 0)) != 1:
        raise SystemExit('EUR M3 coverage delta drifted from fail-closed contract')

    liq['verified_subseries'] = 11
    liq['unresolved_subseries'] = 15
    liq['automation_ready_subseries'] = 11
    liq['mapping_pending_subseries'] = 15
    liq['source_policy_overrides'] = [str(EUR_OVERRIDE), str(AUD_OVERRIDE)]
    liq['aud_es_automation_ready'] = True
    liq['aud_es_controlled_apply_proven'] = True
    liq['aud_es_applier'] = aud_row['applier']
    liq['aud_es_apply_proof_run_id'] = aud_row.get('apply_proof_run_id')
    liq['reason'] = (
        '26/26 official source families are mapped; 11/26 are automation-ready after applying '
        'the EUR M3 fail-closed revision override and the AUD AESAT controlled-apply promotion. '
        'The remaining 15 stay fail-closed until their exact apply/revision/aggregation contracts are proven.'
    )
    receipt['effective_liquidity_overlay'] = {
        'schema': 'GMFQ_DAILY_DATA_ORCHESTRATOR_EFFECTIVE_LIQUIDITY_OVERLAY_V1',
        'base_receipt_schema': receipt.get('schema'),
        'ready': 11,
        'pending': 15,
        'total': 26,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
