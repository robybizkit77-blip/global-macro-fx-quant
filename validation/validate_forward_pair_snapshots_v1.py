#!/usr/bin/env python3
import json,hashlib
from pathlib import Path
M=Path('validation/forward/MANIFEST_V1.json')
L=Path('validation/FORWARD_SNAPSHOT_LEDGER_V1_2026-10-07.json')
m=json.loads(M.read_text())
l=json.loads(L.read_text())
assert m['schema']=='GMFQ_FORWARD_SNAPSHOT_MANIFEST_V1'
assert m['append_only_contract'] is True
ids=set()
ledger_ids={x['snapshot_id'] for x in l['snapshots']}
for e in m['snapshots']:
    assert e['snapshot_id'] not in ids
    ids.add(e['snapshot_id'])
    assert e['snapshot_id'] in ledger_ids
    p=Path(e['path']); assert p.exists()
    assert hashlib.sha256(p.read_bytes()).hexdigest()==e['sha256']
    d=json.loads(p.read_text())
    assert d['schema']=='GMFQ_FORWARD_PAIR_SNAPSHOT_V1'
    assert d['snapshot_id']==e['snapshot_id']
    assert d['pair_count']==28==len(d['pairs'])
    assert len(set(d['pairs']))==28
    for pair,r in d['pairs'].items():
        assert r['pair']==pair
        assert r['macro_anchor'] in {'A','B','MIXED'}
        assert r['state'] in {'TRANSMISSION_CLEAN','TRANSMISSION_PARTIAL','TRANSMISSION_DIVERGENT','TRANSMISSION_WITHHELD'}
        assert r['robustness_badge'] in {'ROBUST_ACROSS_RULES','RULE_SENSITIVE'}
        assert r['production_gate'] is False
        assert r['predictive_claim'] is False
    assert d['forward_outcomes'] is None
assert l['snapshots'][0]['snapshot_id'] in ids
print('PASS',len(ids),'snapshot(s) digest-verified')
