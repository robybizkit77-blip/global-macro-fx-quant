#!/usr/bin/env python3
import argparse, json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', required=True)
    p.add_argument('--contract', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()

    m = load(a.manifest)
    c = load(a.contract)
    assert m['schema'] == 'GMFQ_RESEARCH_PUBLICATION_MANIFEST_V1'
    assert c['schema'] == 'GMFQ_DASHBOARD_RESEARCH_STATE_ADAPTER_CONTRACT_V1'
    assert m['fail_closed'] is True

    labels = c['labels_it']
    context_cards = []
    for x in m['context_only']:
        status = x['status']
        if status not in labels:
            raise AssertionError(f'missing UI label for status {status}')
        assert x['decision_weight'] == 0
        context_cards.append({
            'id': x['id'],
            'layer': x['layer'],
            'status': status,
            'label_it': labels[status],
            'decision_weight': 0,
            'affects_pair_bias': False,
            'affects_currency_score': False,
            'affects_sizing': False,
        })

    decision_signals = []
    for x in m['decision_signals']:
        status = x['status']
        if status not in labels:
            raise AssertionError(f'missing UI label for status {status}')
        decision_signals.append({
            'id': x['id'],
            'layer': x['layer'],
            'status': status,
            'label_it': labels[status],
            'decision_weight_authorized': bool(x['decision_weight_authorized']),
            'sizing_authorized': bool(x['sizing_authorized']),
        })

    out = {
        'schema': 'GMFQ_DASHBOARD_RESEARCH_STATE_V1',
        'source_publication_state': m['publication_state'],
        'research_signal_state': 'WITHHELD' if not decision_signals else 'AVAILABLE',
        'decision_signals': decision_signals,
        'context_cards': context_cards,
        'excluded_live_count': len(m['excluded']),
        'excluded_live_ids_exposed': [],
        'guardrails': {
            'pair_bias_unchanged_by_context': True,
            'currency_score_unchanged_by_context': True,
            'sizing_unchanged_by_context': True,
            'context_decision_weight_zero': True,
            'fail_closed': True,
        },
        'counts': {
            'decision_signals': len(decision_signals),
            'context_cards': len(context_cards),
            'excluded_live': len(m['excluded']),
        }
    }
    Path(a.output).write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
