#!/usr/bin/env python3
import argparse, json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--registry', required=True)
    p.add_argument('--contract', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()

    r = load(a.registry)
    c = load(a.contract)
    assert r['schema'] == 'GMFQ_RESEARCH_CANDIDATE_REGISTRY_V1'
    assert c['schema'] == 'GMFQ_RESEARCH_PUBLICATION_GATE_CONTRACT_V1'

    decision_statuses = set(c['policy']['decision_signal_statuses'])
    context_statuses = set(c['policy']['context_only_statuses'])
    excluded_statuses = set(c['policy']['excluded_statuses'])
    allowed = decision_statuses | context_statuses | excluded_statuses

    decision, context, excluded = [], [], []
    seen = set()
    for e in r['entries']:
        eid = e['id']
        assert eid not in seen
        seen.add(eid)
        status = e['status']
        if status not in allowed:
            raise AssertionError(f'unknown status fail-closed: {status}')

        prod = bool(e.get('production_signal_authorized', False))
        size = bool(e.get('sizing_authorized', False))

        if status in decision_statuses:
            if not prod:
                raise AssertionError(f'{eid}: production status without production authorization')
            decision.append({
                'id': eid,
                'layer': e['layer'],
                'status': status,
                'decision_weight_authorized': True,
                'sizing_authorized': size,
            })
        elif status in context_statuses:
            if prod or size:
                raise AssertionError(f'{eid}: context-only entry cannot authorize production or sizing')
            context.append({
                'id': eid,
                'layer': e['layer'],
                'status': status,
                'decision_weight': 0,
                'display_requires_research_status': True,
            })
        else:
            if prod or size:
                raise AssertionError(f'{eid}: falsified entry cannot authorize production or sizing')
            excluded.append({
                'id': eid,
                'layer': e['layer'],
                'status': status,
                'live_dashboard_allowed': False,
                'audit_only': True,
            })

    out = {
        'schema': 'GMFQ_RESEARCH_PUBLICATION_MANIFEST_V1',
        'source_registry_as_of': r['as_of'],
        'decision_signals': decision,
        'context_only': context,
        'excluded': excluded,
        'counts': {
            'decision_signals': len(decision),
            'context_only': len(context),
            'excluded': len(excluded),
            'total': len(r['entries']),
        },
        'publication_state': 'RESEARCH_DECISION_SIGNALS_AVAILABLE' if decision else 'WITHHELD_NO_PRODUCTION_AUTHORIZED_RESEARCH_SIGNALS',
        'sizing_entries': [x['id'] for x in decision if x['sizing_authorized']],
        'fail_closed': True,
    }
    Path(a.output).write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
