#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

BASE = Path('validation/run_daily_data_orchestrator_v1.py')
AUD_OVERRIDE = Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_AUD_ES_V1_2026-10-13.json')
EUR_OVERRIDE = Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_EUR_M3_V1_2026-10-13.json')
USD_SLOOS_OVERRIDE = Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_USD_SLOOS_CONDITIONS_V1_2026-10-13.json')
EUR_CREDIT_DIAGNOSTIC = Path('validation/diagnose_ecb_eur_nfc_loans_variants.py')
USD_SLOOS_DIAGNOSTIC = Path('validation/diagnose_fed_usd_sloos_conditions_v1.py')
BASE_POLICY = 'validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json'
OVERLAY_VERSION = '2026-10-13-usd-sloos-ready'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def validate_override(obj, subseries):
    if obj.get('schema') != 'GMFQ_LIQUIDITY_POLICY_OVERRIDE_V1':
        raise SystemExit(f'invalid liquidity override schema for {subseries}')
    sup = obj.get('supersedes') or {}
    if sup.get('policy') != BASE_POLICY or sup.get('subseries') != subseries:
        raise SystemExit(f'liquidity override target mismatch for {subseries}')
    return obj.get('effective_row') or {}, obj.get('coverage_delta') or {}


def run_json_script(path):
    proc = subprocess.run(
        [sys.executable, str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f'{path} failed:\n{proc.stdout}')
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f'{path} emitted invalid JSON: {exc}\n{proc.stdout}')


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
    usd_row, usd_delta = validate_override(load(USD_SLOOS_OVERRIDE), 'USD.conditions')

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

    if usd_row.get('automation_ready') is not True:
        raise SystemExit('USD.conditions effective override must be automation-ready')
    if usd_row.get('series_key') != 'SLOOS/SLOOS/SUBLPDCILS_N.Q':
        raise SystemExit('USD.conditions effective series mismatch')
    if usd_row.get('controlled_apply_proven') is not True:
        raise SystemExit('USD.conditions controlled apply proof missing')
    if usd_row.get('historical_overlap_count') != 43 or usd_row.get('historical_exact_match_count') != 43:
        raise SystemExit('USD.conditions full runtime exact-match proof drifted')
    if usd_row.get('historical_exact_match_ratio') != 1.0:
        raise SystemExit('USD.conditions runtime exact-match ratio drifted')
    if usd_row.get('runtime_history_unchanged_by_current_vintage') is not True:
        raise SystemExit('USD.conditions current-vintage history proof missing')
    if usd_row.get('collector') != 'validation/fetch_fed_usd_sloos_conditions_candidate.py':
        raise SystemExit('USD.conditions collector mismatch')
    if usd_row.get('applier') != 'validation/apply_fed_usd_sloos_conditions_candidate.py':
        raise SystemExit('USD.conditions applier mismatch')
    if not Path(usd_row['collector']).exists() or not Path(usd_row['applier']).exists():
        raise SystemExit('USD.conditions collector/applier file missing')

    liq = receipt['lanes']['LIQUIDITY']
    # Base V1 already applies the EUR fail-closed override. Apply AUD and USD deltas here.
    if liq.get('automation_ready_subseries') != 10 or liq.get('mapping_pending_subseries') != 16:
        raise SystemExit(f'unexpected base effective liquidity coverage: {liq}')
    if int(aud_delta.get('automation_ready_subseries', 0)) != 1 or int(aud_delta.get('mapping_pending_subseries', 0)) != -1:
        raise SystemExit('AUD liquidity coverage delta must be +1 READY / -1 pending')
    if int(usd_delta.get('automation_ready_subseries', 0)) != 1 or int(usd_delta.get('mapping_pending_subseries', 0)) != -1:
        raise SystemExit('USD.conditions coverage delta must be +1 READY / -1 pending')
    if int(eur_delta.get('automation_ready_subseries', 0)) != -1 or int(eur_delta.get('mapping_pending_subseries', 0)) != 1:
        raise SystemExit('EUR M3 coverage delta drifted from fail-closed contract')

    eur_credit = run_json_script(EUR_CREDIT_DIAGNOSTIC)
    if eur_credit.get('schema') != 'GMFQ_EUR_NFC_LOANS_VARIANT_DIAGNOSTIC_V1':
        raise SystemExit('EUR.credit diagnostic schema mismatch')
    eur_credit_row = (eur_credit.get('candidates') or {}).get('N_A_A20') or {}
    if eur_credit_row.get('series_id') != 'BSI.M.U2.N.A.A20.A.1.U2.2240.Z01.E':
        raise SystemExit('EUR.credit diagnostic exact series mismatch')
    if int(eur_credit_row.get('overlap_count', 0)) <= 0:
        raise SystemExit('EUR.credit diagnostic has no runtime overlap')

    usd_sloos = run_json_script(USD_SLOOS_DIAGNOSTIC)
    if usd_sloos.get('schema') != 'GMFQ_LIQUIDITY_USD_SLOOS_MAPPING_DIAGNOSTIC_V1':
        raise SystemExit('USD.conditions SLOOS diagnostic schema mismatch')
    if usd_sloos.get('runtime', {}).get('lane') != 'USD.conditions':
        raise SystemExit('USD.conditions SLOOS diagnostic target mismatch')
    if usd_sloos.get('runtime_match_certified') is not True:
        raise SystemExit('USD.conditions live diagnostic no longer certifies runtime match')
    if usd_sloos.get('full_exact_match_count') != 1:
        raise SystemExit('USD.conditions exact mapping is no longer unique')
    full_matches = usd_sloos.get('full_exact_matches') or []
    if len(full_matches) != 1 or full_matches[0].get('series_id') != 'SLOOS/SLOOS/SUBLPDCILS_N.Q':
        raise SystemExit('USD.conditions unique full match drifted')

    liq['verified_subseries'] = 12
    liq['unresolved_subseries'] = 14
    liq['automation_ready_subseries'] = 12
    liq['mapping_pending_subseries'] = 14
    liq['source_policy_overrides'] = [str(EUR_OVERRIDE), str(AUD_OVERRIDE), str(USD_SLOOS_OVERRIDE)]
    liq['aud_es_automation_ready'] = True
    liq['aud_es_controlled_apply_proven'] = True
    liq['aud_es_applier'] = aud_row['applier']
    liq['aud_es_apply_proof_run_id'] = aud_row.get('apply_proof_run_id')
    liq['usd_sloos_automation_ready'] = True
    liq['usd_sloos_controlled_apply_proven'] = True
    liq['usd_sloos_series_key'] = usd_row['series_key']
    liq['usd_sloos_collector'] = usd_row['collector']
    liq['usd_sloos_applier'] = usd_row['applier']
    liq['usd_sloos_apply_proof_run_id'] = usd_row.get('apply_proof_run_id')
    liq['eur_credit_revision_diagnostic'] = {
        'runtime_last_date': eur_credit.get('runtime_last_date'),
        'series_id': eur_credit_row.get('series_id'),
        'overlap_count': eur_credit_row.get('overlap_count'),
        'exact_matches_1e6': eur_credit_row.get('exact_matches_1e6'),
        'first_overlap': eur_credit_row.get('first_overlap'),
        'last_overlap': eur_credit_row.get('last_overlap'),
        'last_runtime': eur_credit_row.get('last_runtime'),
        'last_source': eur_credit_row.get('last_source'),
        'last_diff': eur_credit_row.get('last_diff'),
        'mean_abs_diff': eur_credit_row.get('mean_abs_diff'),
        'max_abs_diff': eur_credit_row.get('max_abs_diff'),
        'ranking_by_mean_abs_diff': eur_credit.get('ranking_by_mean_abs_diff'),
        'automation_ready': False,
        'promotion_performed': False,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    liq['usd_sloos_mapping_diagnostic'] = {
        'runtime_count': usd_sloos.get('runtime', {}).get('count'),
        'runtime_last_date': usd_sloos.get('runtime', {}).get('last_date'),
        'runtime_last_value': usd_sloos.get('runtime', {}).get('last_value'),
        'candidate_columns': usd_sloos.get('parse', {}).get('candidate_columns'),
        'best_candidate': usd_sloos.get('best_candidate'),
        'full_exact_match_count': usd_sloos.get('full_exact_match_count'),
        'full_exact_matches': usd_sloos.get('full_exact_matches'),
        'runtime_match_certified': usd_sloos.get('runtime_match_certified'),
        'automation_ready': True,
        'promotion_performed': True,
        'controlled_apply_proven': True,
        'apply_proof_run_id': usd_row.get('apply_proof_run_id'),
        'runtime_mutated': False,
        'publication_performed': False,
    }
    liq['reason'] = (
        '26/26 official source families are mapped; 12/26 are automation-ready after applying '
        'the EUR M3 fail-closed revision override plus the AUD AESAT and USD SLOOS controlled-apply promotions. '
        'The remaining 14 stay fail-closed until their exact apply/revision/aggregation contracts are proven.'
    )
    receipt['effective_liquidity_overlay'] = {
        'schema': 'GMFQ_DAILY_DATA_ORCHESTRATOR_EFFECTIVE_LIQUIDITY_OVERLAY_V1',
        'version': OVERLAY_VERSION,
        'base_receipt_schema': receipt.get('schema'),
        'ready': 12,
        'pending': 14,
        'total': 26,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
