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

    prov_status=d.get('source_provenance_status') or e.get('source_provenance_status')
    refresh_id=d.get('source_refresh_id') or e.get('source_refresh_id')
    if prov_status=='CERTIFIED_REFRESH_LINKED':
        assert refresh_id
        rp=d.get('source_refresh_record') or e.get('source_refresh_record')
        rh=d.get('source_refresh_record_sha256') or e.get('source_refresh_record_sha256')
        cert_sha=d.get('source_cert53_sha256') or e.get('source_cert53_sha256')
        assert rp and rh and cert_sha
        rpath=Path(rp); assert rpath.exists()
        assert hashlib.sha256(rpath.read_bytes()).hexdigest()==rh
        rec=json.loads(rpath.read_text())
        assert rec['schema']=='GMFQ_CERT53_REFRESH_PROVENANCE_V1'
        assert rec['refresh_id']==refresh_id
        assert rec['section']=='CERT53'
        assert rec['candidate_sha256']==cert_sha
    elif refresh_id is not None:
        raise AssertionError('refresh_id present without CERTIFIED_REFRESH_LINKED status')
assert l['snapshots'][0]['snapshot_id'] in ids
print('PASS',len(ids),'snapshot(s) digest/provenance-verified')
