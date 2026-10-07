import json
from pathlib import Path
p=Path(__file__).resolve().parent/'FOCUS_THEMES_V1_2026-10-07.json'
d=json.loads(p.read_text())
assert d['schema']=='GMFQ_FOCUS_THEMES_V1'
assert d['status']=='RESEARCH_ONLY_DESCRIPTIVE_NOT_PROMOTED'
assert 0 <= d['theme_count'] <= 4
assert d['theme_count']==len(d['themes'])
assert d['max_themes']==4
assert d['guards']['numeric_ranking'] is False
assert d['guards']['trade_signal'] is False
assert d['guards']['predictive_claim'] is False
assert d['guards']['changes_engine_rules'] is False
assert d['guards']['changes_live_data'] is False
assert d['guards']['production_promotion'] is False
seen=set()
allowed={'NEW_CHANGE','CLEAN_CROSSES','CURRENCY_BROAD_COHERENCE','MACRO_TRANSMISSION_DISCONNECT'}
for t in d['themes']:
    assert t['type'] in allowed
    assert t['type'] not in seen
    seen.add(t['type'])
    assert t['subjects']
    assert t['label_it'] and t['read_it'] and t['meaning_it'] and t['action_it']
print('PASS', d['theme_count'], sorted(seen))
