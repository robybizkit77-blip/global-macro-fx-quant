#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'validation/DASHBOARD_PAIR_TRANSMISSION_CURRENT_V1_2026-10-07.json'
OUT = ROOT / 'validation/DASHBOARD_PAIR_TRANSMISSION_ECONOMIC_AUDIT_V1_2026-10-07.json'


def main():
    d = json.loads(SRC.read_text(encoding='utf-8'))
    rows = []
    for pair, r in sorted(d['pairs'].items()):
        layers = r['signed_layers']
        cb = layers['central_bank']['vs_macro']
        rates = layers['rates_front_end_relative']['vs_macro']
        price = layers['price']['vs_macro']
        state = r['final_transmission_state']
        macro = r['macro_anchor']

        # Pure consistency checks only. No return fitting and no reclassification.
        issues = []
        if state == 'TRANSMISSION_CLEAN' and not (cb == rates == price == 'ALIGNED'):
            issues.append('CLEAN_WITH_NONALIGNED_LAYER')
        if state == 'TRANSMISSION_DIVERGENT' and price != 'DIVERGENT' and not (cb == 'DIVERGENT' and rates == 'DIVERGENT'):
            issues.append('DIVERGENT_WITHOUT_RULE_TRIGGER')
        if state == 'TRANSMISSION_WITHHELD' and macro != 'MIXED':
            issues.append('WITHHELD_WITH_DIRECTIONAL_MACRO')
        if state == 'TRANSMISSION_PARTIAL' and macro == 'MIXED':
            issues.append('PARTIAL_WITH_MIXED_MACRO')

        rows.append({
            'pair': pair,
            'state': state,
            'macro_anchor': macro,
            'central_bank_vs_macro': cb,
            'rates_vs_macro': rates,
            'price_vs_macro': price,
            'classification_reason': r.get('classification_reason'),
            'economic_pattern': f'MACRO_{macro}__CB_{cb}__RATES_{rates}__PRICE_{price}',
            'sanity_issues': issues,
            'historical_evidence': r.get('research_evidence', {}),
        })

    by_state = {}
    for state in ['TRANSMISSION_CLEAN','TRANSMISSION_PARTIAL','TRANSMISSION_DIVERGENT','TRANSMISSION_WITHHELD']:
        by_state[state] = [x for x in rows if x['state'] == state]

    out = {
        'schema': 'GMFQ_DASHBOARD_PAIR_TRANSMISSION_ECONOMIC_AUDIT_V1',
        'status': 'PASS_SANITY' if not any(x['sanity_issues'] for x in rows) else 'FAIL_SANITY',
        'created_at': '2026-10-07',
        'purpose': 'Economic-logic sanity audit of the current descriptive pair transmission classification; no return fitting, no rule tuning, no production promotion.',
        'distribution': dict(Counter(x['state'] for x in rows)),
        'clean_pairs': [x['pair'] for x in by_state['TRANSMISSION_CLEAN']],
        'partial_pairs': [x['pair'] for x in by_state['TRANSMISSION_PARTIAL']],
        'divergent_pairs': [x['pair'] for x in by_state['TRANSMISSION_DIVERGENT']],
        'withheld_pairs': [x['pair'] for x in by_state['TRANSMISSION_WITHHELD']],
        'clean_detail': by_state['TRANSMISSION_CLEAN'],
        'partial_detail': by_state['TRANSMISSION_PARTIAL'],
        'divergent_detail': by_state['TRANSMISSION_DIVERGENT'],
        'withheld_detail': by_state['TRANSMISSION_WITHHELD'],
        'sanity_issue_count': sum(bool(x['sanity_issues']) for x in rows),
        'notes': [
            'This audit checks internal economic/classification coherence only.',
            'It does not claim predictive edge or statistical superiority.',
            'Historical reaction-function evidence remains separate from current live-state classification.'
        ]
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if out['status'] != 'PASS_SANITY':
        raise SystemExit('FAIL: transmission sanity issues detected')
    print(json.dumps({
        'status': out['status'],
        'distribution': out['distribution'],
        'clean_pairs': out['clean_pairs'],
        'sanity_issue_count': out['sanity_issue_count'],
    }, indent=2))


if __name__ == '__main__':
    main()
