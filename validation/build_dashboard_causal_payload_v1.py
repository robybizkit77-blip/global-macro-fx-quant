#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CTX = ROOT / 'live_data/sections/COUNTRY_CTX.json'
CB = ROOT / 'live_data/sections/NATIVE_CB_DATA.json'
RATES = ROOT / 'live_data/sections/NATIVE_RATES_DATA.json'
CONTRACT = ROOT / 'validation/DASHBOARD_REACTION_FUNCTION_CONTRACT_V2_2026-10-07.json'
OUT = ROOT / 'validation/DASHBOARD_CAUSAL_PAYLOAD_CURRENT_V1_2026-10-07.json'
G8 = ['USD','EUR','GBP','JPY','CAD','AUD','NZD','CHF']
WITHHELD = {'WITHHELD_SOURCE_ACCESS_GAP','WITHHELD'}


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    ctx = load(CTX)
    cb = load(CB)
    rates = load(RATES)
    contract = load(CONTRACT)
    rows = {}

    for cur in G8:
        cctx = ctx.get(cur, {})
        ccb = cb.get(cur, {})
        cr = rates.get(cur, {})
        cc = contract['currency_contracts'][cur]
        is_withheld = cc.get('evidence_status') in WITHHELD or str(cc.get('evidence_status','')).startswith('WITHHELD')

        rows[cur] = {
            'currency': cur,
            'macro_state': {
                'status': cctx.get('status'),
                'macro_quality': cctx.get('macro_quality'),
                'summary_it': cctx.get('summary_it'),
                'sector_states_it': cctx.get('sector_states_it'),
                'mechanical_override': cctx.get('mechanical_override', False)
            },
            'central_bank_reaction_function': {
                'central_bank': cc.get('central_bank'),
                'reaction_function': cc.get('reaction_function'),
                'evidence_status': cc.get('evidence_status'),
                'dashboard_read': cc.get('dashboard_read')
            },
            'cb_implication': {
                'stance': ccb.get('stance'),
                'impulse': ccb.get('impulse'),
                'official_bias': ccb.get('official_bias'),
                'context': ccb.get('context'),
                'pricing_quality': (ccb.get('market_pricing') or {}).get('quality'),
                'pricing_freshness': (ccb.get('market_pricing') or {}).get('freshness_status')
            },
            'front_end_transmission': {
                'level_2y': cr.get('2Y'),
                'change_2y_bp': cr.get('chg2_bp'),
                'date': cr.get('date'),
                'quality': cr.get('quality'),
                'source': cr.get('source'),
                'direction_vs_macro': None
            },
            'relative_rates_transmission': {
                'direction_vs_macro': None,
                'value': None,
                'benchmark': cc.get('relative_rates')
            },
            'price_confirmation': {
                'direction_vs_macro': None,
                'source': None
            },
            'transmission_state': 'TRANSMISSION_WITHHELD' if is_withheld else None,
            'classification_status': 'WITHHELD_BY_EVIDENCE_MAP' if is_withheld else 'AWAITING_SIGNED_INPUTS',
            'withheld_reason': cc.get('dashboard_read') if is_withheld else None,
            'production_gate': False
        }

    payload = {
        'schema': 'GMFQ_DASHBOARD_CAUSAL_PAYLOAD_CURRENT_V1',
        'status': 'RESEARCH_ONLY_READ_ONLY_ADAPTER',
        'created_at': '2026-10-07',
        'engine_commit': 'ff52198a75cc67f7dae96fc2bbf65623f170791c',
        'rules_fingerprint': '3356baf0',
        'source_files': [
            'live_data/sections/COUNTRY_CTX.json',
            'live_data/sections/NATIVE_CB_DATA.json',
            'live_data/sections/NATIVE_RATES_DATA.json',
            'validation/DASHBOARD_REACTION_FUNCTION_CONTRACT_V2_2026-10-07.json'
        ],
        'classification_policy': 'Adapter only. It normalizes validated current inputs but does not infer macro sign, relative-rate sign, price sign, or final transmission state unless the evidence map requires WITHHELD.',
        'currencies': rows,
        'changes_engine_rules': False,
        'changes_live_data': False,
        'changes_oos_baseline': False,
        'production_promotion': False
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status':'PASS','currencies':list(rows),'output':str(OUT.relative_to(ROOT))}, indent=2))


if __name__ == '__main__':
    main()
