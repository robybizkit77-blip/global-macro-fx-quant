#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'validation/DASHBOARD_PAIR_SIGNED_INPUTS_V1_2026-10-07.json'
OUT = ROOT / 'validation/DASHBOARD_PAIR_TRANSMISSION_CURRENT_V1_2026-10-07.json'


def classify(row: dict) -> tuple[str, str]:
    macro = row.get('macro_anchor')
    layers = row.get('signed_layers', {})
    cb = layers.get('central_bank', {}).get('vs_macro')
    rates = layers.get('rates_front_end_relative', {}).get('vs_macro')
    price = layers.get('price', {}).get('vs_macro')

    if macro not in {'A','B'}:
        return 'TRANSMISSION_WITHHELD', 'Macro anchor is MIXED or unavailable; no directional transmission classification is permitted.'
    if price == 'MISSING':
        return 'TRANSMISSION_WITHHELD', 'Price confirmation is missing.'
    if price == 'DIVERGENT':
        return 'TRANSMISSION_DIVERGENT', 'Price, the final confirmation layer, is moving against the macro anchor.'
    if cb == 'DIVERGENT' and rates == 'DIVERGENT':
        return 'TRANSMISSION_DIVERGENT', 'Both central-bank impulse and front-end relative rates contradict the macro anchor, even if price has not yet broken with it.'
    if price == 'ALIGNED' and cb == 'ALIGNED' and rates == 'ALIGNED':
        return 'TRANSMISSION_CLEAN', 'Macro, central-bank impulse, front-end relative rates and price are directionally coherent.'
    return 'TRANSMISSION_PARTIAL', 'The macro anchor has some downstream confirmation, but at least one material channel is neutral, mixed or contradictory.'


def main() -> None:
    src = json.loads(SRC.read_text(encoding='utf-8'))
    pairs = src['pairs']
    counts = Counter()
    out_pairs = {}
    for pair, row in sorted(pairs.items()):
        state, reason = classify(row)
        counts[state] += 1
        out = dict(row)
        out['final_transmission_state'] = state
        out['classification_status'] = 'CURRENT_DESCRIPTIVE_CLASSIFICATION_READY'
        out['classification_reason'] = reason
        out_pairs[pair] = out

    if sum(counts.values()) != 28:
        raise SystemExit('FAIL pair count')
    if counts['TRANSMISSION_PARTIAL'] == 28:
        raise SystemExit('FAIL degenerate all-PARTIAL distribution')

    payload = {
        'schema': 'GMFQ_DASHBOARD_PAIR_TRANSMISSION_CURRENT_V1',
        'status': 'RESEARCH_ONLY_DESCRIPTIVE_NOT_PREDICTIVE',
        'created_at': '2026-10-07',
        'rule_contract': {
            'WITHHELD': 'Macro anchor MIXED/unavailable or price missing.',
            'DIVERGENT': 'Price diverges from macro OR both central-bank impulse and rates diverge from macro.',
            'CLEAN': 'Macro directional and CB + rates + price all aligned.',
            'PARTIAL': 'All remaining directional cases with incomplete/contradictory transmission.',
            'optimization': 'NONE',
            'return_fitting': False,
            'predictive_claim': False
        },
        'distribution': dict(counts),
        'pairs': out_pairs,
        'historical_evidence_rule': 'Historical PIT/OOS evidence remains a separate badge and does not mechanically overwrite current descriptive state.',
        'engine_commit': 'ff52198a75cc67f7dae96fc2bbf65623f170791c',
        'rules_fingerprint': '3356baf0',
        'guards': {
            'changes_engine_rules': False,
            'changes_live_data': False,
            'changes_oos_baseline': False,
            'production_promotion': False
        }
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('PASS distribution', dict(counts))

if __name__ == '__main__':
    main()
