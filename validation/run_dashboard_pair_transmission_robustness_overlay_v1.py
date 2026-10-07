#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / 'validation/DASHBOARD_PAIR_TRANSMISSION_CURRENT_V1_2026-10-07.json'
SENS = ROOT / 'validation/DASHBOARD_PAIR_TRANSMISSION_RULE_SENSITIVITY_V1_2026-10-07.json'
OUT = ROOT / 'validation/DASHBOARD_PAIR_TRANSMISSION_ROBUSTNESS_OVERLAY_V1_2026-10-07.json'


def main():
    cur = json.loads(CURRENT.read_text(encoding='utf-8'))
    sen = json.loads(SENS.read_text(encoding='utf-8'))
    sens_map = {x['pair']: x for x in sen['stable_pairs']}
    sens_map.update({x['pair']: x for x in sen['unstable_detail']})

    pairs = {}
    for pair, row in sorted(cur['pairs'].items()):
        s = sens_map[pair]
        stable = s['stable_all_three']
        pairs[pair] = {
            'pair': pair,
            'current_state': row['final_transmission_state'],
            'robustness_badge': 'ROBUST_ACROSS_RULES' if stable else 'RULE_SENSITIVE',
            'rule_states': {
                'strict': s['strict'],
                'price_first': s['price_first'],
                'two_of_three': s['two_of_three'],
            },
            'ui_rule': 'Show current state normally' if stable else 'Show current state with RULE_SENSITIVE warning; do not present as strong confirmation/divergence.',
            'production_gate': False,
        }

    out = {
        'schema': 'GMFQ_DASHBOARD_PAIR_TRANSMISSION_ROBUSTNESS_OVERLAY_V1',
        'status': 'RESEARCH_ONLY_NOT_PROMOTED',
        'created_at': '2026-10-07',
        'purpose': 'Expose whether the current descriptive pair transmission state is stable across reasonable non-return-fitted classification rules.',
        'summary': {
            'all_pairs': len(pairs),
            'robust_across_rules': sum(v['robustness_badge']=='ROBUST_ACROSS_RULES' for v in pairs.values()),
            'rule_sensitive': sum(v['robustness_badge']=='RULE_SENSITIVE' for v in pairs.values()),
            'directional_stability_pct': sen['stability']['stable_directional_pct'],
        },
        'pairs': pairs,
        'guards': {
            'changes_engine_rules': False,
            'changes_live_data': False,
            'changes_oos_baseline': False,
            'production_promotion': False,
            'return_fitting': False,
        }
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps(out['summary'], indent=2))


if __name__ == '__main__':
    main()
