import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
P = ROOT / 'DASHBOARD_DATA_READINESS_V1_2026-10-07.json'
d = json.loads(P.read_text())

assert d['schema'] == 'GMFQ_DASHBOARD_DATA_READINESS_V1'
assert d['status'] == 'RESEARCH_ONLY_UI_PLANNING_NOT_PROMOTED'
allowed = {'READY','PARTIAL','WITHHELD'}
sections = d['sections']
assert sections
counts = {k:0 for k in allowed}
for name, item in sections.items():
    assert item['readiness'] in allowed, (name, item['readiness'])
    counts[item['readiness']] += 1
    assert item['source']
    assert item['note_it']
    if item['readiness'] != 'READY':
        assert item.get('missing')
assert counts == d['summary'], (counts, d['summary'])
assert d['redesign_rule']['never_present_withheld_as_neutral'] is True
assert d['redesign_rule']['no_new_universal_scores'] is True
for k in ['changes_engine_rules','changes_live_data','production_promotion','trade_signal','predictive_claim']:
    assert d['guards'][k] is False
print('PASS', counts)
