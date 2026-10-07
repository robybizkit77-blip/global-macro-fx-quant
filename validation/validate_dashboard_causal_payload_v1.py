#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'validation/DASHBOARD_CAUSAL_PAYLOAD_CURRENT_V1_2026-10-07.json'
G8 = {'USD','EUR','GBP','JPY','CAD','AUD','NZD','CHF'}
ALLOWED = {None,'TRANSMISSION_CLEAN','TRANSMISSION_PARTIAL','TRANSMISSION_DIVERGENT','TRANSMISSION_WITHHELD'}


def fail(msg):
    raise SystemExit(f'FAIL: {msg}')


def main():
    p = json.loads(PAYLOAD.read_text(encoding='utf-8'))
    if p.get('schema') != 'GMFQ_DASHBOARD_CAUSAL_PAYLOAD_CURRENT_V1':
        fail('schema')
    if p.get('engine_commit') != 'ff52198a75cc67f7dae96fc2bbf65623f170791c':
        fail('engine commit')
    if p.get('rules_fingerprint') != '3356baf0':
        fail('rules fingerprint')
    if set(p.get('currencies', {})) != G8:
        fail('G8 coverage')
    for k in ['changes_engine_rules','changes_live_data','changes_oos_baseline','production_promotion']:
        if p.get(k) is not False:
            fail(k)
    for cur,row in p['currencies'].items():
        if row.get('production_gate') is not False:
            fail(f'{cur} production gate')
        if row.get('transmission_state') not in ALLOWED:
            fail(f'{cur} transmission state')
        status = row.get('classification_status')
        if cur in {'NZD','CHF'}:
            if row.get('transmission_state') != 'TRANSMISSION_WITHHELD' or status != 'WITHHELD_BY_EVIDENCE_MAP':
                fail(f'{cur} must be withheld')
        else:
            if row.get('transmission_state') is not None or status != 'AWAITING_SIGNED_INPUTS':
                fail(f'{cur} premature classification')
        if row.get('front_end_transmission',{}).get('direction_vs_macro') is not None:
            fail(f'{cur} front-end direction inferred prematurely')
        if row.get('relative_rates_transmission',{}).get('direction_vs_macro') is not None:
            fail(f'{cur} relative-rates direction inferred prematurely')
        if row.get('price_confirmation',{}).get('direction_vs_macro') is not None:
            fail(f'{cur} price direction inferred prematurely')
    print('PASS: dashboard causal payload V1 is read-only, G8-complete and does not invent signed transmission states')


if __name__ == '__main__':
    main()
