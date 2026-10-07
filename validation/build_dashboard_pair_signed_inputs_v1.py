#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERT53 = ROOT / 'live_data/sections/CERT53.json'
EVIDENCE = ROOT / 'validation/CENTRAL_BANK_REACTION_FUNCTION_EVIDENCE_MAP_V3_2026-10-07.json'
OUT = ROOT / 'validation/DASHBOARD_PAIR_SIGNED_INPUTS_V1_2026-10-07.json'


def rel(direction: str | None, macro: str | None) -> str:
    if macro not in {'A','B'}:
        return 'NOT_APPLICABLE_MACRO_MIXED'
    if direction in {'A','B'}:
        return 'ALIGNED' if direction == macro else 'DIVERGENT'
    if direction in {'MIXED','NEUTRAL','CONTEXT'}:
        return 'NEUTRAL_OR_MIXED'
    return 'MISSING'


def main() -> None:
    cert = json.loads(CERT53.read_text(encoding='utf-8'))
    evidence = json.loads(EVIDENCE.read_text(encoding='utf-8'))['currencies']
    pairs = cert.get('pairs', {})
    if len(pairs) != 28:
        raise SystemExit(f'FAIL: expected 28 G8 crosses, found {len(pairs)}')

    rows = {}
    macro_counts = Counter()
    layer_counts = {k: Counter() for k in ('central_bank','rates','price')}
    pattern_counts = Counter()

    for pair, src in sorted(pairs.items()):
        a, b = pair.split('/')
        macro = src.get('fundamental_anchor_macro')
        layer_dirs = src.get('layer_directions', {})
        cb_dir = src.get('central_bank_realized_direction') or layer_dirs.get('central_bank')
        rates_dir = src.get('lead_direction') or layer_dirs.get('rates')
        price_dir = layer_dirs.get('price')

        macro_counts[macro or 'MISSING'] += 1
        cb_rel = rel(cb_dir, macro)
        rates_rel = rel(rates_dir, macro)
        price_rel = rel(price_dir, macro)
        layer_counts['central_bank'][cb_rel] += 1
        layer_counts['rates'][rates_rel] += 1
        layer_counts['price'][price_rel] += 1
        pattern_counts[(macro or 'MISSING', cb_rel, rates_rel, price_rel)] += 1

        rows[pair] = {
            'pair': pair,
            'leg_a': a,
            'leg_b': b,
            'macro_anchor': macro,
            'macro_source': 'CERT53.fundamental_anchor_macro',
            'signed_layers': {
                'central_bank': {'direction': cb_dir, 'vs_macro': cb_rel},
                'rates_front_end_relative': {'direction': rates_dir, 'vs_macro': rates_rel},
                'price': {'direction': price_dir, 'vs_macro': price_rel},
            },
            'research_evidence': {
                a: evidence[a]['evidence_status'],
                b: evidence[b]['evidence_status'],
                'note': 'Historical evidence quality is separate from current live-state availability.'
            },
            'legacy_state_reference_only': src.get('state'),
            'final_transmission_state': None,
            'classification_status': 'SIGNED_INPUTS_READY__FINAL_RULE_NOT_YET_APPLIED' if macro in {'A','B'} else 'MACRO_MIXED__NO_DIRECTIONAL_CLASSIFICATION',
            'production_gate': False,
        }

    out = {
        'schema': 'GMFQ_DASHBOARD_PAIR_SIGNED_INPUTS_V1',
        'status': 'RESEARCH_ONLY_READ_ONLY_ADAPTER',
        'created_at': '2026-10-07',
        'purpose': 'Normalize the already-signed current 28-cross macro, central-bank, rates and price inputs without applying a new final transmission rule.',
        'engine_commit': 'ff52198a75cc67f7dae96fc2bbf65623f170791c',
        'rules_fingerprint': '3356baf0',
        'important_separation': {
            'live_transmission_state': 'Current market-state description.',
            'historical_evidence_status': 'Quality of PIT/OOS evidence for the currency-specific reaction function.',
            'rule': 'A historical WITHHELD label does not automatically force the current pair state to WITHHELD; it limits predictive claims and production promotion.'
        },
        'distribution': {
            'macro_anchor': dict(macro_counts),
            'central_bank_vs_macro': dict(layer_counts['central_bank']),
            'rates_vs_macro': dict(layer_counts['rates']),
            'price_vs_macro': dict(layer_counts['price']),
            'exact_patterns': [
                {'macro': k[0], 'central_bank': k[1], 'rates': k[2], 'price': k[3], 'count': v}
                for k, v in sorted(pattern_counts.items(), key=lambda kv: (-kv[1], kv[0]))
            ]
        },
        'pairs': rows,
        'guards': {
            'final_transmission_rule_applied': False,
            'legacy_CERT53_state_used_as_new_output': False,
            'changes_engine_rules': False,
            'changes_live_data': False,
            'changes_oos_baseline': False,
            'production_promotion': False
        }
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('PASS:', len(rows), 'pair signed inputs normalized')
    print('macro:', dict(macro_counts))
    print('cb:', dict(layer_counts['central_bank']))
    print('rates:', dict(layer_counts['rates']))
    print('price:', dict(layer_counts['price']))

if __name__ == '__main__':
    main()
