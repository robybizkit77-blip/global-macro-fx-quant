#!/usr/bin/env python3
from __future__ import annotations
import json, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'validation/TRANSMISSION_REGIME_ATTRIBUTION_V1_2026-10-07.json'
OUT=ROOT/'validation/TRANSMISSION_DIRECTIONAL_ASYMMETRY_V1_2026-10-07.json'
ENGINE='ff52198a75cc67f7dae96fc2bbf65623f170791c'; FP='3356baf0'

def stat(rows):
    v=[r['signed_20d'] for r in rows if r.get('signed_20d') is not None]
    return {'n':len(v),'hit_rate':sum(x>0 for x in v)/len(v) if v else None,'mean':sum(v)/len(v) if v else None,'median':statistics.median(v) if v else None}

src=json.loads(SRC.read_text())
rows=src['rows']
# Same OOS rule as prior evidence, reconstructed per currency.
oos=[]
for c in ('USD','GBP','CAD','JPY'):
    rr=sorted([r for r in rows if r['currency']==c],key=lambda x:x['checkpoint']); oos.extend(rr[int(len(rr)*.4):])

def one(rs):
    out={}
    for d,label in ((1,'HAWKISH_POSITIVE'),(-1,'DOVISH_NEGATIVE')):
        q=[r for r in rs if r['macro_regime']=='COHERENT' and r['macro_direction']==d]
        out[label]={k:stat([r for r in q if r['conviction']==k]) for k in ('MEDIUM','LOW')}
        m,l=out[label]['MEDIUM'],out[label]['LOW']
        out[label]['medium_gt_low_hit']=bool(m['n'] and l['n'] and m['hit_rate']>l['hit_rate'])
        out[label]['medium_gt_low_mean']=bool(m['n'] and l['n'] and m['mean']>l['mean'])
    return out
res={'schema':'GMFQ_TRANSMISSION_DIRECTIONAL_ASYMMETRY_V1','status':'PASS_DIAGNOSTIC_NOT_PROMOTED','created_at':'2026-10-07','engine_baseline':{'commit':ENGINE,'rules_fingerprint':FP,'modified':False},'purpose':'Predeclared directional asymmetry test inside coherent macro regimes: positive/hawkish versus negative/dovish macro direction; same common-core transmission labels and same signed 20d outcome.','guardrails':['direction split economically predeclared','coherent regimes unchanged','same 40% chronological OOS exclusion','no tuning','no engine/live/OOS baseline changes'],'pooled_oos':one(oos),'oos_by_currency':{c:one([r for r in oos if r['currency']==c]) for c in ('USD','GBP','CAD','JPY')},'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
OUT.write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps({'pooled_oos':res['pooled_oos'],'oos_by_currency':res['oos_by_currency']},indent=2))
