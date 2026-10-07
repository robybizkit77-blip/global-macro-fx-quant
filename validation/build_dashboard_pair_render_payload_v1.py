#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / 'validation/DASHBOARD_PAIR_TRANSMISSION_CURRENT_V1_2026-10-07.json'
ROBUST = ROOT / 'validation/DASHBOARD_PAIR_TRANSMISSION_ROBUSTNESS_OVERLAY_V1_2026-10-07.json'
OUT = ROOT / 'validation/DASHBOARD_PAIR_RENDER_PAYLOAD_V1_2026-10-07.json'

STATE_IT = {
    'TRANSMISSION_CLEAN': ('TRASMISSIONE PULITA', 'Macro, banca centrale, front-end e prezzo sono coerenti.'),
    'TRANSMISSION_PARTIAL': ('TRASMISSIONE PARZIALE', 'Il quadro macro trova conferme, ma almeno un canale non è pienamente coerente.'),
    'TRANSMISSION_DIVERGENT': ('DIVERGENZA', 'Uno o più canali materiali stanno contraddicendo il quadro macro.'),
    'TRANSMISSION_WITHHELD': ('NON CLASSIFICATA', 'Il quadro macro relativo non è abbastanza direzionale per una classificazione affidabile.'),
}

ROBUST_IT = {
    'ROBUST_ACROSS_RULES': ('ROBUSTA', 'Lo stato resta uguale sotto tre regole descrittive ragionevoli.'),
    'RULE_SENSITIVE': ('SENSIBILE ALLA REGOLA', 'Lo stato cambia sotto almeno una regola descrittiva ragionevole; va letto con prudenza.'),
}

LAYER_IT = {
    'ALIGNED': 'conferma',
    'DIVERGENT': 'diverge',
    'NEUTRAL_OR_MIXED': 'misto/neutrale',
    'NOT_APPLICABLE_MACRO_MIXED': 'non applicabile',
}


def main() -> None:
    cur = json.loads(CURRENT.read_text(encoding='utf-8'))
    rob = json.loads(ROBUST.read_text(encoding='utf-8'))
    if set(cur['pairs']) != set(rob['pairs']):
        raise SystemExit('FAIL: pair universe mismatch')

    rows = {}
    focus = {'clean_robust': [], 'divergent_robust': [], 'partial_robust': [], 'rule_sensitive': [], 'withheld': []}

    for pair in sorted(cur['pairs']):
        p = cur['pairs'][pair]
        r = rob['pairs'][pair]
        state = p['final_transmission_state']
        badge = r['robustness_badge']
        state_label, state_note = STATE_IT[state]
        robust_label, robust_note = ROBUST_IT[badge]
        layers = p['signed_layers']
        cb = layers['central_bank']['vs_macro']
        rates = layers['rates_front_end_relative']['vs_macro']
        price = layers['price']['vs_macro']

        if state == 'TRANSMISSION_CLEAN' and badge == 'ROBUST_ACROSS_RULES':
            bucket = 'clean_robust'
            read_it = 'Catena causale coerente: è uno dei cross più puliti del quadro corrente. Non è un segnale di trade automatico.'
        elif state == 'TRANSMISSION_DIVERGENT' and badge == 'ROBUST_ACROSS_RULES':
            bucket = 'divergent_robust'
            read_it = 'Divergenza stabile tra macro e trasmissione: richiede capire quale layer sta anticipando e quale sta ritardando.'
        elif badge == 'RULE_SENSITIVE':
            bucket = 'rule_sensitive'
            read_it = 'La lettura dipende dalla regola descrittiva: utile come warning, non come conclusione forte.'
        elif state == 'TRANSMISSION_PARTIAL':
            bucket = 'partial_robust'
            read_it = 'Il quadro ha conferme reali ma non complete: serve osservare quale canale manca alla convergenza.'
        else:
            bucket = 'withheld'
            read_it = 'Il macro anchor è misto: meglio non forzare una direzione finché il quadro relativo non si chiarisce.'

        focus[bucket].append(pair)
        rows[pair] = {
            'pair': pair,
            'macro_anchor': p['macro_anchor'],
            'state': state,
            'state_label_it': state_label,
            'state_note_it': state_note,
            'robustness_badge': badge,
            'robustness_label_it': robust_label,
            'robustness_note_it': robust_note,
            'layers': {
                'central_bank': {'status': cb, 'label_it': LAYER_IT[cb]},
                'front_end_rates': {'status': rates, 'label_it': LAYER_IT[rates]},
                'price': {'status': price, 'label_it': LAYER_IT[price]},
            },
            'research_evidence': p['research_evidence'],
            'dashboard_read_it': read_it,
            'production_gate': False,
            'predictive_claim': False,
        }

    payload = {
        'schema': 'GMFQ_DASHBOARD_PAIR_RENDER_PAYLOAD_V1',
        'status': 'RESEARCH_ONLY_UI_READY_NOT_PROMOTED',
        'created_at': '2026-10-07',
        'purpose': 'UI-ready current pair transmission payload. Descriptive only; no return fitting and no trade signal.',
        'display_contract': {
            'primary': 'macro_anchor + transmission_state',
            'secondary': 'central_bank + front_end_rates + price',
            'safety_badges': ['robustness_badge', 'research_evidence'],
            'never_hide_rule_sensitive': True,
            'never_convert_withheld_to_neutral': True,
            'never_flip_macro_from_downstream_layers': True,
        },
        'summary': {
            'state_counts': dict(Counter(v['state'] for v in rows.values())),
            'robustness_counts': dict(Counter(v['robustness_badge'] for v in rows.values())),
            'focus_buckets': focus,
        },
        'pairs': rows,
        'guards': {
            'changes_engine_rules': False,
            'changes_live_data': False,
            'changes_oos_baseline': False,
            'production_promotion': False,
            'return_fitting': False,
            'predictive_claim': False,
        },
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('PASS: UI render payload built')
    print(json.dumps(payload['summary'], indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
