#!/usr/bin/env python3
import json
from pathlib import Path
p=Path('validation/PAIR_COMPACT_PAYLOAD_V1_2026-10-07.json')
h=Path('validation/PAIR_COMPACT_HISTORY_V1_2026-10-07.json')
obj=json.loads(p.read_text())
hist=json.loads(h.read_text())
assert obj['schema']=='GMFQ_PAIR_COMPACT_PAYLOAD_V1'
assert obj['pair_count']==28
assert len(obj['pairs'])==28
assert hist['schema']=='GMFQ_PAIR_COMPACT_HISTORY_V1'
assert hist['append_only'] is True
assert len(hist['snapshots'])>=1
for pair,v in obj['pairs'].items():
    assert v['pair']==pair
    assert v['macro_anchor'] in {'A','B','MIXED'}
    assert v['transmission'] in {'TRANSMISSION_CLEAN','TRANSMISSION_PARTIAL','TRANSMISSION_DIVERGENT','TRANSMISSION_WITHHELD'}
    assert v['robustness'] in {'ROBUST_ACROSS_RULES','RULE_SENSITIVE'}
    assert set(v['layers'])=={'central_bank','front_end_rates','price'}
    assert v['what_changed']['status'] in {'BASELINE','CHANGED','STABLE'}
    assert isinstance(v['what_changed']['changed_fields'],list)
    assert v['forward']['primary_horizon']==20
    assert v['production_gate'] is False
    assert v['predictive_claim'] is False
assert all(x is False for x in obj['guards'].values())
print('PASS_VALIDATE_PAIR_COMPACT_PAYLOAD_V1')
