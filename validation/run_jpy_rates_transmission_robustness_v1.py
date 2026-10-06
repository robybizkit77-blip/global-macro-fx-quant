#!/usr/bin/env python3
from __future__ import annotations
import json, math, random, statistics
from pathlib import Path

SRC=Path('validation/JPY_RATES_TRANSMISSION_OOS_V1_2026-10-07.json')
TRANS=Path('validation/JPY_RATES_TRANSMISSION_V1_2026-10-07.json')
REPLAY=Path('validation/JPY_REACTION_FUNCTION_REPLAY_V1_2026-10-06.json')
OUT=Path('validation/JPY_RATES_TRANSMISSION_ROBUSTNESS_V1_2026-10-07.json')
ENGINE='ff52198a75cc67f7dae96fc2bbf65623f170791c'
FP='3356baf0'
SEED=20261007

random.seed(SEED)

def mean(xs): return sum(xs)/len(xs) if xs else None

def median(xs): return statistics.median(xs) if xs else None

def hit(xs): return sum(x>0 for x in xs)/len(xs) if xs else None

def bootstrap_ci(xs, n=20000):
    if not xs:return [None,None]
    vals=[]; m=len(xs)
    for _ in range(n): vals.append(mean([xs[random.randrange(m)] for _ in range(m)]))
    vals.sort()
    return [vals[int(.025*n)], vals[min(n-1,int(.975*n))]]

def sign_perm_p(xs, n=30000):
    if not xs:return None
    obs=abs(mean(xs)); ge=0
    for _ in range(n):
        z=[x if random.random()<.5 else -x for x in xs]
        if abs(mean(z))>=obs: ge+=1
    return (ge+1)/(n+1)

def loo(xs):
    if len(xs)<2:return {'mean_range':[None,None],'hit_range':[None,None]}
    ms=[]; hs=[]
    for i in range(len(xs)):
        z=xs[:i]+xs[i+1:]; ms.append(mean(z)); hs.append(hit(z))
    return {'mean_range':[min(ms),max(ms)],'hit_range':[min(hs),max(hs)]}

def top_share(xs,k=3):
    if not xs:return None
    a=sorted((abs(x) for x in xs),reverse=True); den=sum(a)
    return sum(a[:k])/den if den else None

def exact_sign_p(pos,n):
    if n==0:return None
    from math import comb
    p=sum(comb(n,k) for k in range(pos,n+1))/(2**n)
    q=sum(comb(n,k) for k in range(0,pos+1))/(2**n)
    return min(1.0,2*min(p,q))

def diagnostics(rows,key,state):
    xs=[r['signed_20d'] for r in rows if r.get(key)==state and r.get('signed_20d') is not None]
    return {'n':len(xs),'hit_rate':hit(xs),'mean':mean(xs),'median':median(xs),'positive':sum(x>0 for x in xs),'exact_sign_p_two_sided':exact_sign_p(sum(x>0 for x in xs),len(xs)),'bootstrap_mean_95pct_ci':bootstrap_ci(xs),'random_sign_permutation_p_two_sided':sign_perm_p(xs),**loo(xs),'top3_absolute_contribution_share':top_share(xs)}

def contrast(rows,key):
    a=[r['signed_20d'] for r in rows if r.get(key)=='CONFIRM' and r.get('signed_20d') is not None]
    b=[r['signed_20d'] for r in rows if r.get(key)=='DIVERGE' and r.get('signed_20d') is not None]
    obs=(mean(a) or 0)-(mean(b) or 0)
    pool=[(x,'A') for x in a]+[(x,'B') for x in b]
    ge=0; nperm=30000
    vals=[x for x,_ in pool]; na=len(a)
    for _ in range(nperm):
        random.shuffle(vals)
        d=mean(vals[:na])-mean(vals[na:])
        if abs(d)>=abs(obs): ge+=1
    return {'confirm_n':len(a),'diverge_n':len(b),'mean_spread_confirm_minus_diverge':obs,'permutation_p_two_sided':(ge+1)/(nperm+1)}

def fold_id(cp):
    if cp<='2021-07-20': return 1
    if cp<='2022-08-19': return 2
    return 3

def fold_table(rows,key):
    out=[]
    for f in (1,2,3):
        rr=[r for r in rows if fold_id(r['checkpoint'])==f]
        out.append({'fold':f,'confirm':diagnostics(rr,key,'CONFIRM'),'diverge':diagnostics(rr,key,'DIVERGE')})
    return out

def main():
    src=json.loads(SRC.read_text()); trans=json.loads(TRANS.read_text()); replay=json.loads(REPLAY.read_text())
    assert src['status']=='PASS_DIAGNOSTIC_NOT_PROMOTED'
    assert replay['engine']['frozen_commit']==ENGINE and replay['engine']['rules_fingerprint']==FP
    oos_dates=set()
    samples=replay['directional_samples']; start=math.floor(len(samples)*.4)
    oos_dates={r['checkpoint'] for r in samples[start:]}
    rows=[r for r in trans['paired_events'] if r['checkpoint'] in oos_dates]
    assert len(rows)==29
    keys=['jpy2y_state_5obs','jpy2y_state_20obs','diff_state_5obs','diff_state_20obs']
    result={}
    for key in keys:
        result[key]={'confirm':diagnostics(rows,key,'CONFIRM'),'diverge':diagnostics(rows,key,'DIVERGE'),'contrast':contrast(rows,key),'folds':fold_table(rows,key)}
    payload={'schema':'GMFQ_JPY_RATES_TRANSMISSION_ROBUSTNESS_V1','status':'PASS_DIAGNOSTIC_NOT_PROMOTED','created_at':'2026-10-07','engine_frozen_commit':ENGINE,'rules_fingerprint':FP,'oos_events':len(rows),'method':{'bootstrap_draws':20000,'random_sign_permutations':30000,'contrast_label_permutations':30000,'leave_one_out':True,'folds':'same 3 chronological OOS cohorts as frozen replay','seed':SEED,'no_selection_after_results':True},'results':result,'interpretation_guardrail':'diagnostic only; no threshold/window/filter tuning or promotion from this result alone','changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
    OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':payload['status'],'oos_events':len(rows),'results':result},indent=2,ensure_ascii=False))

if __name__=='__main__': main()
