#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'validation/DASHBOARD_PAIR_SIGNED_INPUTS_V1_2026-10-07.json'
OUT = ROOT / 'validation/DASHBOARD_PAIR_TRANSMISSION_RULE_SENSITIVITY_V1_2026-10-07.json'


def classify_strict(r):
    macro = r['macro_anchor']
    cb = r['signed_layers']['central_bank']['vs_macro']
    rates = r['signed_layers']['rates_front_end_relative']['vs_macro']
    price = r['signed_layers']['price']['vs_macro']
    if macro == 'MIXED' or price in {'MISSING', None}:
        return 'WITHHELD'
    if cb == rates == price == 'ALIGNED':
        return 'CLEAN'
    if price == 'DIVERGENT' or (cb == 'DIVERGENT' and rates == 'DIVERGENT'):
        return 'DIVERGENT'
    return 'PARTIAL'


def classify_price_first(r):
    macro = r['macro_anchor']
    cb = r['signed_layers']['central_bank']['vs_macro']
    rates = r['signed_layers']['rates_front_end_relative']['vs_macro']
    price = r['signed_layers']['price']['vs_macro']
    if macro == 'MIXED' or price in {'MISSING', None}:
        return 'WITHHELD'
    if price == 'DIVERGENT':
        return 'DIVERGENT'
    if price == 'ALIGNED' and cb == 'ALIGNED' and rates == 'ALIGNED':
        return 'CLEAN'
    return 'PARTIAL'


def classify_core_two_of_three(r):
    macro = r['macro_anchor']
    vals = [
        r['signed_layers']['central_bank']['vs_macro'],
        r['signed_layers']['rates_front_end_relative']['vs_macro'],
        r['signed_layers']['price']['vs_macro'],
    ]
    if macro == 'MIXED' or vals[2] in {'MISSING', None}:
        return 'WITHHELD'
    aligned = vals.count('ALIGNED')
    divergent = vals.count('DIVERGENT')
    if aligned == 3:
        return 'CLEAN'
    if divergent >= 2:
        return 'DIVERGENT'
    return 'PARTIAL'


def main():
    d = json.loads(SRC.read_text(encoding='utf-8'))
    rows = []
    for pair, r in sorted(d['pairs'].items()):
        s = classify_strict(r)
        p = classify_price_first(r)
        t = classify_core_two_of_three(r)
        rows.append({
            'pair': pair,
            'strict': s,
            'price_first': p,
            'two_of_three': t,
            'stable_all_three': len({s,p,t}) == 1,
            'macro_anchor': r['macro_anchor'],
            'central_bank_vs_macro': r['signed_layers']['central_bank']['vs_macro'],
            'rates_vs_macro': r['signed_layers']['rates_front_end_relative']['vs_macro'],
            'price_vs_macro': r['signed_layers']['price']['vs_macro'],
        })

    stable = [x for x in rows if x['stable_all_three']]
    unstable = [x for x in rows if not x['stable_all_three']]
    directional = [x for x in rows if x['macro_anchor'] != 'MIXED']
    stable_directional = [x for x in directional if x['stable_all_three']]
    out = {
        'schema': 'GMFQ_DASHBOARD_PAIR_TRANSMISSION_RULE_SENSITIVITY_V1',
        'status': 'DIAGNOSTIC_NOT_PROMOTED',
        'created_at': '2026-10-07',
        'purpose': 'Test descriptive-classification stability across three reasonable predeclared non-return-fitted rules.',
        'no_return_fitting': True,
        'rules': {
            'strict': 'Current rule: CLEAN all aligned; DIVERGENT if price diverges or CB+rates both diverge; otherwise PARTIAL.',
            'price_first': 'DIVERGENT only if price diverges; CLEAN only if all aligned; otherwise PARTIAL.',
            'two_of_three': 'DIVERGENT if at least two of CB/rates/price diverge; CLEAN only if all aligned; otherwise PARTIAL.'
        },
        'distribution_by_rule': {
            'strict': dict(Counter(x['strict'] for x in rows)),
            'price_first': dict(Counter(x['price_first'] for x in rows)),
            'two_of_three': dict(Counter(x['two_of_three'] for x in rows)),
        },
        'stability': {
            'all_pairs_n': len(rows),
            'stable_all_three_n': len(stable),
            'stable_all_three_pct': round(100*len(stable)/len(rows), 2),
            'directional_pairs_n': len(directional),
            'stable_directional_n': len(stable_directional),
            'stable_directional_pct': round(100*len(stable_directional)/len(directional), 2) if directional else None,
            'unstable_pairs': [x['pair'] for x in unstable]
        },
        'stable_pairs': stable,
        'unstable_detail': unstable,
        'interpretation_rule': 'If states are unstable across reasonable non-fitted descriptive rules, keep the layer descriptive and avoid production promotion until forward evidence accumulates.'
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps(out['stability'], indent=2))


if __name__ == '__main__':
    main()
