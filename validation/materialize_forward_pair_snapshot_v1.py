#!/usr/bin/env python3
import json, hashlib
from pathlib import Path

ROOT=Path('validation')
LEDGER=ROOT/'FORWARD_SNAPSHOT_LEDGER_V1_2026-10-07.json'
PAYLOAD=ROOT/'DASHBOARD_PAIR_RENDER_PAYLOAD_V1_2026-10-07.json'
SNAPDIR=ROOT/'forward'/'snapshots'
MANIFEST=ROOT/'forward'/'MANIFEST_V1.json'

ledger=json.loads(LEDGER.read_text(encoding='utf-8'))
payload=json.loads(PAYLOAD.read_text(encoding='utf-8'))
pairs=payload.get('pairs',{})
assert len(pairs)==28
seed=ledger['snapshots'][0]
snapshot_id=seed['snapshot_id']
assert snapshot_id=='2026-10-07T08:05:22Z__V1'
filename='2026-10-07T080522Z__V1.json'
path=SNAPDIR/filename
SNAPDIR.mkdir(parents=True,exist_ok=True)

frozen_pairs={}
for pair in sorted(pairs):
    p=pairs[pair]
    frozen_pairs[pair]={
      'pair': pair,
      'macro_anchor': p.get('macro_anchor'),
      'state': p.get('state'),
      'robustness_badge': p.get('robustness_badge'),
      'layers': p.get('layers'),
      'research_evidence': p.get('research_evidence'),
      'production_gate': bool(p.get('production_gate',False)),
      'predictive_claim': bool(p.get('predictive_claim',False)),
    }

snap={
  'schema':'GMFQ_FORWARD_PAIR_SNAPSHOT_V1',
  'status':'FROZEN_RESEARCH_SNAPSHOT',
  'snapshot_id':snapshot_id,
  'captured_at':seed['captured_at'],
  'materialized_before_entry_lock':True,
  'source_payload':str(PAYLOAD),
  'ledger_source':str(LEDGER),
  'engine_commit':ledger['engine_commit'],
  'rules_fingerprint':ledger['rules_fingerprint'],
  'classifier_version':ledger['classifier_version'],
  'robustness_overlay_version':ledger['robustness_overlay_version'],
  'pair_count':28,
  'pairs':frozen_pairs,
  'forward_outcomes':None,
  'guards':{
    'frozen_pair_labels':True,
    'retroactive_label_changes_forbidden':True,
    'changes_engine_rules':False,
    'changes_live_data':False,
    'production_promotion':False,
    'predictive_claim':False,
  }
}
text=json.dumps(snap,indent=2,ensure_ascii=False)+'\n'
if path.exists():
    old=path.read_text(encoding='utf-8')
    if old!=text:
        raise SystemExit('REFUSE_REWRITE_EXISTING_SNAPSHOT')
else:
    path.write_text(text,encoding='utf-8')

digest=hashlib.sha256(path.read_bytes()).hexdigest()
entry={'snapshot_id':snapshot_id,'captured_at':seed['captured_at'],'path':str(path),'sha256':digest,'pair_count':28}
if MANIFEST.exists():
    m=json.loads(MANIFEST.read_text(encoding='utf-8'))
    found=[x for x in m['snapshots'] if x['snapshot_id']==snapshot_id]
    if found:
        assert found[0]==entry, 'MANIFEST_ENTRY_MISMATCH'
    else:
        m['snapshots'].append(entry)
else:
    m={
      'schema':'GMFQ_FORWARD_SNAPSHOT_MANIFEST_V1',
      'status':'ACTIVE_RESEARCH_MANIFEST',
      'append_only_contract':True,
      'digest_algorithm':'SHA256',
      'snapshots':[entry],
      'guards':{'production_promotion':False,'changes_engine_rules':False,'changes_live_data':False}
    }
MANIFEST.parent.mkdir(parents=True,exist_ok=True)
MANIFEST.write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('MATERIALIZED',snapshot_id,digest)
