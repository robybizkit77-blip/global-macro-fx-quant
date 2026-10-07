#!/usr/bin/env python3
import json, hashlib
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path('validation')
SRC=ROOT/'DASHBOARD_PAIR_RENDER_PAYLOAD_V1_2026-10-07.json'
FWD=ROOT/'FORWARD_ECB_FIXING_STATE_V1_2026-10-07.json'
HIST=ROOT/'PAIR_COMPACT_HISTORY_V1_2026-10-07.json'
OUT=ROOT/'PAIR_COMPACT_PAYLOAD_V1_2026-10-07.json'

src=json.loads(SRC.read_text())
fwd=json.loads(FWD.read_text())

pairs={}
for pair,p in sorted(src['pairs'].items()):
    layers=p.get('layers',{})
    pairs[pair]={
        'pair':pair,
        'macro_anchor':p.get('macro_anchor'),
        'transmission':p.get('state'),
        'robustness':p.get('robustness_badge'),
        'layers':{
            'central_bank':layers.get('central_bank',{}).get('status'),
            'front_end_rates':layers.get('front_end_rates',{}).get('status'),
            'price':layers.get('price',{}).get('status'),
        },
        'research_evidence':p.get('research_evidence',{}),
        'production_gate':False,
        'predictive_claim':False,
    }

semantic={k:{'macro_anchor':v['macro_anchor'],'transmission':v['transmission'],'robustness':v['robustness'],'layers':v['layers']} for k,v in pairs.items()}
digest=hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode()).hexdigest()
now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

if HIST.exists():
    hist=json.loads(HIST.read_text())
else:
    hist={'schema':'GMFQ_PAIR_COMPACT_HISTORY_V1','status':'ACTIVE_RESEARCH_HISTORY','append_only':True,'snapshots':[]}

if not hist['snapshots'] or hist['snapshots'][-1]['semantic_digest']!=digest:
    hist['snapshots'].append({'snapshot_id':now+'__PAIR_COMPACT_V1','captured_at':now,'semantic_digest':digest,'pairs':semantic})
HIST.write_text(json.dumps(hist,indent=2,ensure_ascii=False)+'\n')

prev=hist['snapshots'][-2]['pairs'] if len(hist['snapshots'])>1 else None
changes={}
for pair,cur in semantic.items():
    if prev is None:
        changes[pair]={'status':'BASELINE','changed_fields':[]}
        continue
    old=prev[pair]
    fields=[]
    for k in ('macro_anchor','transmission','robustness'):
        if old.get(k)!=cur.get(k): fields.append(k)
    for k in ('central_bank','front_end_rates','price'):
        if old.get('layers',{}).get(k)!=cur.get('layers',{}).get(k): fields.append('layers.'+k)
    changes[pair]={'status':'CHANGED' if fields else 'STABLE','changed_fields':fields}

latest_fwd=None
if fwd.get('snapshots'):
    latest_fwd=list(fwd['snapshots'].values())[-1]

for pair in pairs:
    pairs[pair]['what_changed']=changes[pair]
    pairs[pair]['forward']={
        'entry_locked': bool(latest_fwd and latest_fwd.get('entry_locked')),
        'entry_fixing_date': latest_fwd.get('entry_fixing_date') if latest_fwd else None,
        'primary_horizon': fwd.get('primary_horizon',20),
        'status':'ENTRY_LOCKED' if latest_fwd and latest_fwd.get('entry_locked') else 'ENTRY_PENDING'
    }

out={
    'schema':'GMFQ_PAIR_COMPACT_PAYLOAD_V1',
    'status':'RESEARCH_ONLY_UI_READY_NOT_PROMOTED',
    'purpose':'Minimal pair payload for future compact dashboard; no score, no trade signal, no macro override.',
    'fields':['macro_anchor','transmission','robustness','layers','what_changed','forward','research_evidence'],
    'pair_count':len(pairs),
    'pairs':pairs,
    'guards':{
        'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False,
        'production_promotion':False,'creates_universal_score':False,'overrides_macro_bias':False,'predictive_claim':False
    }
}
OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print('PASS_PAIR_COMPACT_PAYLOAD_V1',len(pairs), 'history_snapshots',len(hist['snapshots']))
