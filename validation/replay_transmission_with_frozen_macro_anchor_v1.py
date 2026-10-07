#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

SIGNED = Path('validation/DASHBOARD_PAIR_SIGNED_INPUTS_V1_2026-10-07.json')
AUDIT = Path('validation/FROZEN_MACRO_ANCHOR_PARITY_AUDIT_V1_2026-10-07.json')
OUT = Path('validation/FROZEN_MACRO_TRANSMISSION_REPLAY_V1_2026-10-07.json')


def relation(direction, macro):
    if macro == 'MIXED':
        return 'NOT_APPLICABLE_MACRO_MIXED'
    if direction in ('MIXED', 'WITHHELD', None):
        return 'NEUTRAL_OR_MIXED'
    return 'ALIGNED' if direction == macro else 'DIVERGENT'


def classify(macro, cb, rates, price):
    # Exact strict descriptive rule used by the current research transmission layer.
    # This replay changes only the Macro anchor source; it does not fit/tune a rule.
    if macro == 'MIXED':
        return 'WITHHELD'
    if price in ('WITHHELD', None):
        return 'WITHHELD'
    price_rel = relation(price, macro)
    cb_rel = relation(cb, macro)
    rates_rel = relation(rates, macro)
    if price_rel == 'DIVERGENT' or (cb_rel == 'DIVERGENT' and rates_rel == 'DIVERGENT'):
        return 'DIVERGENT'
    if cb_rel == rates_rel == price_rel == 'ALIGNED':
        return 'CLEAN'
    return 'PARTIAL'


def main():
    signed = json.loads(SIGNED.read_text())
    audit = json.loads(AUDIT.read_text())
    rows = {}
    old_dist = Counter()
    new_dist = Counter()
    changed = []

    # Current transmission labels are reconstructed from the same strict rule and current signed inputs,
    # rather than read from a downstream payload, so old/new differ only by Macro anchor.
    for pair, rec in sorted(signed['pairs'].items()):
        layers = rec['signed_layers']
        cb = layers['central_bank']['direction']
        rates = layers['rates_front_end_relative']['direction']
        price = layers['price']['direction']
        current_macro = rec['macro_anchor']
        frozen_macro = audit['pairs'][pair]['frozen_canonical_anchor']
        current_state = classify(current_macro, cb, rates, price)
        replay_state = classify(frozen_macro, cb, rates, price)
        old_dist[current_state] += 1
        new_dist[replay_state] += 1
        is_changed = current_state != replay_state
        if is_changed:
            changed.append(pair)
        rows[pair] = {
            'current_macro_anchor': current_macro,
            'frozen_macro_anchor': frozen_macro,
            'central_bank_direction': cb,
            'rates_direction': rates,
            'price_direction': price,
            'current_reconstructed_transmission': current_state,
            'frozen_macro_replay_transmission': replay_state,
            'transmission_changed': is_changed,
        }

    out = {
        'schema': 'GMFQ_FROZEN_MACRO_TRANSMISSION_REPLAY_V1',
        'status': 'READ_ONLY_ARCHITECTURE_SENSITIVITY',
        'purpose': 'Measure how much the current strict transmission classification depends on using CERT53 Macro anchors instead of the frozen canonical currency-Macro comparison rule.',
        'important_limit': 'Frozen currency Macro labels are the historical frozen snapshot, not regenerated current Macro states. This is architecture sensitivity, not a proposal to replace current live Macro with stale labels.',
        'rule_change': False,
        'only_changed_input': 'macro_anchor_source',
        'distribution': {
            'current_reconstructed': dict(sorted(old_dist.items())),
            'frozen_macro_replay': dict(sorted(new_dist.items())),
            'unchanged_pairs': 28-len(changed),
            'changed_pairs': len(changed),
        },
        'changed_pair_list': changed,
        'pairs': rows,
        'conclusion': {
            'if_material_change': 'Current transmission research is materially dependent on the legacy CERT53 Macro anchor source. Do not treat it as frozen-engine-parity until a current canonical currency-Macro regeneration contract exists.',
            'macro_apply_gate': 'BLOCKED',
            'next_required_artifact': 'CURRENT_CANONICAL_CURRENCY_MACRO_REGENERATION_CONTRACT_V1'
        },
        'guards': {
            'changes_engine_rules': False,
            'changes_live_data': False,
            'changes_oos_baseline': False,
            'production_promotion': False,
            'predictive_claim': False,
        }
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(out['distribution'], ensure_ascii=False))

if __name__ == '__main__':
    main()
