#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'validation/DASHBOARD_REACTION_FUNCTION_CONTRACT_V2_2026-10-07.json'
EVIDENCE = ROOT / 'validation/CENTRAL_BANK_REACTION_FUNCTION_EVIDENCE_MAP_V3_2026-10-07.json'
G8 = {'USD','EUR','GBP','JPY','CAD','AUD','NZD','CHF'}
FORBIDDEN = {'HIGH','MEDIUM','LOW'}


def fail(msg: str) -> None:
    raise SystemExit(f'FAIL: {msg}')


def main() -> None:
    c = json.loads(CONTRACT.read_text(encoding='utf-8'))
    e = json.loads(EVIDENCE.read_text(encoding='utf-8'))

    if c.get('schema') != 'GMFQ_DASHBOARD_REACTION_FUNCTION_CONTRACT_V2':
        fail('unexpected schema')
    if c.get('engine_baseline', {}).get('commit') != 'ff52198a75cc67f7dae96fc2bbf65623f170791c':
        fail('frozen engine mismatch')
    if c.get('engine_baseline', {}).get('rules_fingerprint') != '3356baf0':
        fail('rules fingerprint mismatch')
    if c.get('engine_baseline', {}).get('modified') is not False:
        fail('engine marked modified')

    cc = c.get('currency_contracts', {})
    ec = e.get('currencies', {})
    if set(cc) != G8:
        fail(f'currency coverage mismatch: {sorted(set(cc) ^ G8)}')
    if set(ec) != G8:
        fail(f'evidence-map currency coverage mismatch: {sorted(set(ec) ^ G8)}')

    allowed_states = set(c.get('allowed_transmission_states', {}))
    expected_states = {
        'TRANSMISSION_CLEAN','TRANSMISSION_PARTIAL',
        'TRANSMISSION_DIVERGENT','TRANSMISSION_WITHHELD'
    }
    if allowed_states != expected_states:
        fail(f'transmission state set mismatch: {sorted(allowed_states)}')

    blob = CONTRACT.read_text(encoding='utf-8')
    for token in FORBIDDEN:
        # Allowed only in the explicit forbidden-output sentence, not as an operative label.
        operative_occurrences = [line for line in blob.splitlines() if token in line and 'forbidden_outputs' not in line and 'Universal HIGH/MEDIUM/LOW conviction score' not in line]
        if operative_occurrences:
            fail(f'forbidden universal conviction token present operationally: {token}')

    rr = c.get('rendering_rules', {})
    required_false = ['transmission_can_flip_macro_bias','rates_can_flip_macro_bias','price_can_flip_macro_bias','missing_is_neutral']
    for key in required_false:
        if rr.get(key) is not False:
            fail(f'{key} must be false')
    if rr.get('macro_bias_is_primary') is not True:
        fail('macro_bias_is_primary must be true')
    if rr.get('show_reason_for_withheld') is not True:
        fail('show_reason_for_withheld must be true')

    for cur in sorted(G8):
        row = cc[cur]
        if row.get('production_gate') is not False:
            fail(f'{cur}: production_gate must be false')
        if row.get('evidence_status') != ec[cur].get('evidence_status'):
            fail(f"{cur}: evidence status mismatch contract={row.get('evidence_status')} map={ec[cur].get('evidence_status')}")
        if not row.get('central_bank') or not row.get('reaction_function'):
            fail(f'{cur}: missing central bank/reaction function')
        if not row.get('dashboard_read'):
            fail(f'{cur}: missing dashboard_read')
        if not isinstance(row.get('macro_drivers'), list) or not row['macro_drivers']:
            fail(f'{cur}: macro_drivers missing')

    guards = c.get('research_guards', {})
    for key in ['changes_engine_rules','changes_live_data','changes_oos_baseline','production_promotion']:
        if guards.get(key) is not False:
            fail(f'research guard {key} must be false')

    print('PASS: dashboard reaction-function contract V2 is internally consistent and aligned with Evidence Map V3')


if __name__ == '__main__':
    main()
