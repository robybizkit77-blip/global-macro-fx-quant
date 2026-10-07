#!/usr/bin/env python3
import json, hashlib
from datetime import datetime, timezone
from pathlib import Path

LEDGER=Path('validation/FORWARD_SNAPSHOT_LEDGER_V1_2026-10-07.json')
PAYLOAD=Path('validation/DASHBOARD_PAIR_RENDER_PAYLOAD_V1_2026-10-07.json')
CERT53=Path('live_data/sections/CERT53.json')
MANIFEST=Path('validation/forward/MANIFEST_V1.json')
SNAPDIR=Path('validation/forward/snapshots')

ledger=json.loads(LEDGER.read_text(encoding='utf-8'))
payload=json.loads(PAYLOAD.read_text(encoding='utf-8'))
pairs=payload.get('pairs',{})
assert len(pairs)==28, f'expected 28 pairs, got {len(pairs)}'
manifest=json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() else {
  'schema':'GMFQ_FORWARD_SNAPSHOT_MANIFEST_V1','status':'ACTIVE_RESEARCH_MANIFEST','append_only_contract':True,
  'digest_algorithm':'SHA256','snapshots':[],
  'guards':{'production_promotion':False,'changes_engine_rules':False,'changes_live_data':False}}

def sha256_file(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

semantic={}
for pair in sorted(pairs):
    p=pairs[pair] or {}
    semantic[pair]={'macro_anchor':p.get('macro_anchor'),'state':p.get('state'),'robustness_badge':p.get('robustness_badge')}
fingerprint=hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode()).hexdigest()

state_counts={k:0 for k in ['TRANSMISSION_CLEAN','TRANSMISSION_PARTIAL','TRANSMISSION_DIVERGENT','TRANSMISSION_WITHHELD']}
robustness_counts={'ROBUST_ACROSS_RULES':0,'RULE_SENSITIVE':0}
focus={'clean_robust':[],'divergent_robust':[],'partial_robust':[],'rule_sensitive':[],'withheld':[]}
for pair,p in sorted(pairs.items()):
    st=p.get('state'); rb=p.get('robustness_badge')
    assert st in state_counts and rb in robustness_counts
    state_counts[st]+=1; robustness_counts[rb]+=1
    if st=='TRANSMISSION_WITHHELD': focus['withheld'].append(pair)
    elif rb=='RULE_SENSITIVE': focus['rule_sensitive'].append(pair)
    elif st=='TRANSMISSION_CLEAN': focus['clean_robust'].append(pair)
    elif st=='TRANSMISSION_DIVERGENT': focus['divergent_robust'].append(pair)
    else: focus['partial_robust'].append(pair)

last=ledger['snapshots'][-1]; last_fp=last.get('semantic_fingerprint')
def equivalent_to_seeded_last():
    return last.get('state_counts')==state_counts and last.get('robustness_counts')==robustness_counts and all(last.get('focus_buckets',{}).get(k,[])==focus[k] for k in focus)
if last_fp==fingerprint or (last_fp is None and equivalent_to_seeded_last()):
    print('NO_NEW_SNAPSHOT: semantic state unchanged')
    raise SystemExit(0)

now=datetime.now(timezone.utc).replace(microsecond=0); iso=now.isoformat().replace('+00:00','Z')
snapshot_id=f'{iso}__AUTO_V1'; safe=iso.replace(':','').replace('-','')
path=SNAPDIR/f'{safe}__AUTO_V1.json'
if path.exists(): raise SystemExit(f'REFUSE_EXISTING_SNAPSHOT_PATH:{path}')
if any(x['snapshot_id']==snapshot_id for x in manifest['snapshots']): raise SystemExit(f'REFUSE_DUPLICATE_SNAPSHOT_ID:{snapshot_id}')

source_payload_sha256=sha256_file(PAYLOAD)
source_cert53_sha256=sha256_file(CERT53)

frozen_pairs={}
for pair in sorted(pairs):
    p=pairs[pair]
    frozen_pairs[pair]={'pair':pair,'macro_anchor':p.get('macro_anchor'),'state':p.get('state'),'robustness_badge':p.get('robustness_badge'),
      'layers':p.get('layers'),'research_evidence':p.get('research_evidence'),'production_gate':bool(p.get('production_gate',False)),
      'predictive_claim':bool(p.get('predictive_claim',False))}

full={'schema':'GMFQ_FORWARD_PAIR_SNAPSHOT_V1','status':'FROZEN_RESEARCH_SNAPSHOT','snapshot_id':snapshot_id,'captured_at':iso,
  'materialized_before_entry_lock':True,'source_payload':str(PAYLOAD),'source_payload_sha256':source_payload_sha256,
  'source_cert53':'live_data/sections/CERT53.json','source_cert53_sha256':source_cert53_sha256,
  'source_provenance_status':'HASH_LINKED_FROM_CERT53_DOWNSTREAM__UPSTREAM_LINEAGE_PARTIAL',
  'ledger_source':str(LEDGER),'engine_commit':ledger['engine_commit'],
  'rules_fingerprint':ledger['rules_fingerprint'],'classifier_version':ledger['classifier_version'],
  'robustness_overlay_version':ledger['robustness_overlay_version'],'semantic_fingerprint':fingerprint,'pair_count':28,'pairs':frozen_pairs,
  'forward_outcomes':None,'guards':{'frozen_pair_labels':True,'retroactive_label_changes_forbidden':True,'changes_engine_rules':False,
  'changes_live_data':False,'production_promotion':False,'predictive_claim':False}}
SNAPDIR.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(full,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
digest=hashlib.sha256(path.read_bytes()).hexdigest()
manifest['snapshots'].append({'snapshot_id':snapshot_id,'captured_at':iso,'path':str(path),'sha256':digest,'pair_count':28,
  'source_payload_sha256':source_payload_sha256,'source_cert53_sha256':source_cert53_sha256})
MANIFEST.parent.mkdir(parents=True,exist_ok=True); MANIFEST.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

snap={'snapshot_id':snapshot_id,'captured_at':iso,'source_payload':str(PAYLOAD),'source_payload_sha256':source_payload_sha256,
  'source_cert53_sha256':source_cert53_sha256,'semantic_fingerprint':fingerprint,'pair_count':28,
  'state_counts':state_counts,'robustness_counts':robustness_counts,'focus_buckets':focus,
  'historical_evidence_status':last.get('historical_evidence_status',{}),'forward_outcomes':{'t_plus_5':None,'t_plus_20':None,'t_plus_60':None},
  'frozen':True,'frozen_pair_snapshot_path':str(path),'frozen_pair_snapshot_sha256':digest}
ledger['snapshots'].append(snap); LEDGER.write_text(json.dumps(ledger,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(f'APPENDED_FORWARD_SNAPSHOT {snapshot_id} {fingerprint[:12]} {digest[:12]} cert53={source_cert53_sha256[:12]}')
