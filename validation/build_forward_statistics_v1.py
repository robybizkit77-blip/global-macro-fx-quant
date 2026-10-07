#!/usr/bin/env python3
import json, hashlib
from collections import defaultdict
from pathlib import Path

STATE=Path('validation/FORWARD_ECB_FIXING_STATE_V1_2026-10-07.json')
MANIFEST=Path('validation/forward/MANIFEST_V1.json')
OUT=Path('validation/FORWARD_STATISTICS_V1_2026-10-07.json')

state=json.loads(STATE.read_text())
manifest=json.loads(MANIFEST.read_text())

frozen={}
for e in manifest['snapshots']:
    p=Path(e['path']); assert p.exists()
    assert hashlib.sha256(p.read_bytes()).hexdigest()==e['sha256']
    d=json.loads(p.read_text()); assert len(d['pairs'])==28
    frozen[e['snapshot_id']]=d['pairs']

def bucket_stats(rows):
    signed=[r['signed_macro_return_pct'] for r in rows if r.get('signed_macro_return_pct') is not None]
    hits=[r['hit'] for r in rows if r.get('hit') is not None]
    if not signed:
        return {'n':0,'hit_n':0,'hit_rate_pct':None,'mean_signed_return_pct':None,'median_signed_return_pct':None}
    s=sorted(signed); n=len(s); med=s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2
    return {'n':n,'hit_n':sum(x is True for x in hits),'hit_rate_pct':round(100*sum(x is True for x in hits)/len(hits),4) if hits else None,
      'mean_signed_return_pct':round(sum(s)/n,6),'median_signed_return_pct':round(med,6)}

horizons={5:[],20:[],60:[]}
for sid,st in state.get('snapshots',{}).items():
    if sid not in frozen: raise RuntimeError(f'MISSING_FROZEN_SNAPSHOT:{sid}')
    fpairs=frozen[sid]
    for hk,outcome in st.get('outcomes',{}).items():
        try: h=int(str(hk).replace('t_plus_','').replace('d','').replace('D',''))
        except: continue
        if h not in horizons: continue
        for pair,res in outcome.get('pair_results',{}).items():
            p=fpairs[pair]
            # Integrity check: outcome labels must equal frozen labels.
            assert res.get('state')==p['state']
            assert res.get('robustness_badge')==p['robustness_badge']
            assert res.get('macro_anchor')==p['macro_anchor']
            horizons[h].append({'snapshot_id':sid,'pair':pair,'state':p['state'],'robustness':p['robustness_badge'],
              'macro_anchor':p['macro_anchor'],'raw_return_pct':res.get('raw_return_pct'),
              'signed_macro_return_pct':res.get('signed_macro_return_pct'),'hit':res.get('hit')})

report={'schema':'GMFQ_FORWARD_STATISTICS_V1','status':'AWAITING_MATURED_OUTCOMES','primary_horizon':20,
 'methodology_note':'Descriptive forward evidence only, grouped by frozen snapshot labels. No production promotion, sizing, threshold tuning or predictive claim from small samples.',
 'label_source':'FROZEN_PAIR_SNAPSHOT_MANIFEST_V1','horizons':{},
 'guards':{'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False,'production_promotion':False,
           'retroactive_tuning':False,'uses_current_render_payload_for_historical_labels':False}}
any_mature=False
for h,rows in horizons.items():
    by_state=defaultdict(list); by_rob=defaultdict(list)
    for r in rows:
        by_state[r['state']].append(r); by_rob[r['robustness']].append(r)
    report['horizons'][str(h)]={'matured_pair_observations':len(rows),
      'by_state':{k:bucket_stats(v) for k,v in sorted(by_state.items())},
      'by_robustness':{k:bucket_stats(v) for k,v in sorted(by_rob.items())}}
    if rows: any_mature=True
if any_mature: report['status']='ACTIVE_FORWARD_EVIDENCE_ACCUMULATING'
OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(report['status'])
