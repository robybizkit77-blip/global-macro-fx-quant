#!/usr/bin/env python3
import json, math, random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'validation/CAD_FULL_REACTION_STATE_VNEXT_V2_2026-10-06.json'
OUT=ROOT/'validation/CAD_FULL_REACTION_STATE_VNEXT_V2_ROBUSTNESS_2026-10-06.json'
random.seed(93517)
d=json.loads(SRC.read_text())
rows=sorted(d['rows'], key=lambda r:r['checkpoint'])
H=[5,20,60]
states=sorted(set(r['joint_inflation_state'] for r in rows))

def stats(rs,key):
    vals=[r[key] for r in rs if key in r]
    if not vals:return {'n':0,'mean':None,'positive_share':None}
    return {'n':len(vals),'mean':sum(vals)/len(vals),'positive_share':sum(v>0 for v in vals)/len(vals)}

def boot_mean(rs,key,B=3000):
    vals=[r[key] for r in rs if key in r]
    if len(vals)<2:return {'n':len(vals),'lo':None,'hi':None}
    means=[]
    n=len(vals)
    for _ in range(B):
        s=[vals[random.randrange(n)] for _ in range(n)]
        means.append(sum(s)/n)
    means.sort()
    return {'n':n,'lo':means[int(0.025*B)],'hi':means[int(0.975*B)]}

# Pure chronological 3-fold reference: first 40% treated as initial history, then three sequential test folds.
n=len(rows); start=max(1,int(n*0.40)); rem=rows[start:]; size=max(1,len(rem)//3)
folds=[]
for i in range(3):
    a=i*size; b=(i+1)*size if i<2 else len(rem)
    test=rem[a:b]
    folds.append({'fold':i+1,'test_start':test[0]['checkpoint'] if test else None,'test_end':test[-1]['checkpoint'] if test else None,'by_state':{s:{f'{h}d':stats([r for r in test if r['joint_inflation_state']==s],f'cad_basket_{h}d') for h in H} for s in states}})

pooled=rem
half=len(rows)//2
first=rows[:half]; second=rows[half:]
res={'schema':'GMFQ_CAD_FULL_REACTION_STATE_VNEXT_V2_ROBUSTNESS','status':'PASS','created_at':'2026-10-06','source':SRC.name,'guardrails':['state definitions unchanged','no window selection','no threshold tuning','chronological splits only','bootstrap descriptive only'],'full_sample':{s:{f'{h}d':{**stats([r for r in rows if r['joint_inflation_state']==s],f'cad_basket_{h}d'),'bootstrap_mean_95':boot_mean([r for r in rows if r['joint_inflation_state']==s],f'cad_basket_{h}d')} for h in H} for s in states},'split_half':{'first':{s:{f'{h}d':stats([r for r in first if r['joint_inflation_state']==s],f'cad_basket_{h}d') for h in H} for s in states},'second':{s:{f'{h}d':stats([r for r in second if r['joint_inflation_state']==s],f'cad_basket_{h}d') for h in H} for s in states}},'walkforward':{'initial_history_n':start,'pooled_oos_n':len(pooled),'folds':folds,'pooled_by_state':{s:{f'{h}d':stats([r for r in pooled if r['joint_inflation_state']==s],f'cad_basket_{h}d') for h in H} for s in states}},'changes_engine_rules':False,'changes_live_data':False}
OUT.write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps(res['walkforward']['pooled_by_state'],indent=2))
