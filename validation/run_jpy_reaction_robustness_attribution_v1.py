#!/usr/bin/env python3
from __future__ import annotations
import csv, json, math, random, statistics
from bisect import bisect_right
from pathlib import Path

ROOT=Path('history/pit_v1')
WAGES=ROOT/'JPY_WAGES_SCHEDULED_CASH_EARNINGS_FIRST_RELEASE_2018_2023_07.csv'
CPI=ROOT/'JPY_CPI_HEADLINE_CORE_FIRST_RELEASE_2018_2023_07.csv'
FX=ROOT/'FX_G8_DAILY_ECB_2016_2026.csv'
REPLAY=Path('validation/JPY_REACTION_FUNCTION_REPLAY_V1_2026-10-06.json')
OUT=Path('validation/JPY_REACTION_ROBUSTNESS_ATTRIBUTION_V1_2026-10-07.json')
CCY=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']; H=(5,20,60)
TH=.20; MINOBS=8; WIN=80


def med(xs):
    xs=[float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.median(xs) if xs else None

def impulse(values):
    if len(values)<MINOBS:return None
    vals=[float(x) for x in values]; tail=vals[-WIN:]
    diffs=[abs(tail[i]-tail[i-1]) for i in range(1,len(tail))]
    s=med(diffs)
    if not s or s<=0:return None
    return (vals[-1]-vals[-2])/s

def pol(x):
    if x is None:return 0
    if x>=TH:return 1
    if x<=-TH:return -1
    return 0

def pair_value(row,a,b):
    if a==b:return 1.0
    ordered=CCY.index(a)<CCY.index(b); key=a+b if ordered else b+a
    v=float(row[key]); return v if ordered else 1.0/v

def stats(vals):
    vals=[float(x) for x in vals if x is not None and math.isfinite(float(x))]
    if not vals:return {'n':0,'hit_rate':None,'mean_signed_log_return':None,'median_signed_log_return':None}
    return {'n':len(vals),'hit_rate':sum(x>0 for x in vals)/len(vals),'mean_signed_log_return':sum(vals)/len(vals),'median_signed_log_return':statistics.median(vals)}

def summarize(rows):
    return {f'{h}d':stats([r.get(f'signed_{h}d') for r in rows]) for h in H}

def walk(rows):
    rows=sorted(rows,key=lambda r:r['checkpoint']); n=len(rows); start=math.floor(n*.4); prev=start; folds=[]; pooled=[]
    for k,frac in enumerate((.6,.8,1.0),1):
        end=n if frac==1 else max(prev+1,math.floor(n*frac)); test=rows[prev:end]; pooled+=test
        folds.append({'fold':k,'train_event_count':prev,'test_event_count':len(test),'test_start':test[0]['checkpoint'] if test else None,'test_end':test[-1]['checkpoint'] if test else None,'stats':summarize(test)}); prev=end
    return {'initial_train_fraction':.4,'folds':folds,'pooled_oos_event_count':len(pooled),'pooled_oos':summarize(pooled),'pooled_rows':pooled}

def binom_two_sided(k,n,p=.5):
    if n==0:return None
    probs=[math.comb(n,i)*(p**i)*((1-p)**(n-i)) for i in range(n+1)]
    obs=probs[k]
    return min(1.0,sum(q for q in probs if q<=obs+1e-15))

def robustness_20(rows):
    vals=[r['signed_20d'] for r in rows if r.get('signed_20d') is not None]
    if not vals:return {}
    n=len(vals); k=sum(v>0 for v in vals); rng=random.Random(3356)
    boot=[]
    for _ in range(10000):
        s=[vals[rng.randrange(n)] for __ in range(n)]
        boot.append(sum(s)/n)
    boot.sort(); ci=[boot[int(.025*(len(boot)-1))],boot[int(.975*(len(boot)-1))]]
    perm=[]
    rng2=random.Random(3356)
    absvals=[abs(v) for v in vals]; obs=abs(sum(vals)/n)
    for _ in range(20000):
        perm.append(abs(sum(a*(1 if rng2.random()>.5 else -1) for a in absvals)/n))
    p_perm=(1+sum(x>=obs for x in perm))/(1+len(perm))
    loo=[]
    for i in range(n):
        v=vals[:i]+vals[i+1:]
        loo.append({'mean':sum(v)/len(v),'hit_rate':sum(x>0 for x in v)/len(v)})
    abs_total=sum(abs(v) for v in vals)
    top3=sum(sorted((abs(v) for v in vals),reverse=True)[:3])
    return {
        'n':n,'positive':k,'sign_test_p_two_sided':binom_two_sided(k,n),
        'bootstrap_mean_95pct_ci':ci,'random_sign_permutation_p_two_sided':p_perm,
        'leave_one_out_mean_range':[min(x['mean'] for x in loo),max(x['mean'] for x in loo)],
        'leave_one_out_hit_rate_range':[min(x['hit_rate'] for x in loo),max(x['hit_rate'] for x in loo)],
        'top3_absolute_contribution_share':top3/abs_total if abs_total else None
    }

def load_inputs():
    with WAGES.open(newline='',encoding='utf-8-sig') as f:w=list(csv.DictReader(f))
    with CPI.open(newline='',encoding='utf-8-sig') as f:c=list(csv.DictReader(f))
    wages=[{'release_date':r['release_date'],'value':float(r['scheduled_cash_earnings_yoy_pct'])} for r in w]
    head=[{'release_date':r['release_date'],'value':float(r['headline_cpi_yoy_pct'])} for r in c]
    core=[{'release_date':r['release_date'],'value':float(r['core_cpi_yoy_pct'])} for r in c]
    return wages,head,core

def build_signal_events():
    wages,head,core=load_inputs(); cps=sorted(set([r['release_date'] for r in wages+head]))
    out=[]
    for cp in cps:
        wv=[r['value'] for r in wages if r['release_date']<=cp]; hv=[r['value'] for r in head if r['release_date']<=cp]; cv=[r['value'] for r in core if r['release_date']<=cp]
        wi=impulse(wv); hi=impulse(hv); ci=impulse(cv); ii=med([x for x in (hi,ci) if x is not None])
        wp,ip=pol(wi),pol(ii)
        combo=wp if wp!=0 and wp==ip else 0
        out.append({'checkpoint':cp,'wages_impulse':wi,'inflation_impulse':ii,'wages_polarity':wp,'inflation_polarity':ip,'combined_polarity':combo})
    return out

def attach_returns(events,signal_key):
    with FX.open(newline='',encoding='utf-8') as f:fx=list(csv.DictReader(f))
    dates=[r['date'] for r in fx]; rows=[]
    for e in events:
        s=e[signal_key]
        if s not in (-1,1):continue
        ix=bisect_right(dates,e['checkpoint'])
        if ix>=len(fx):continue
        z=dict(e); z['signal']=signal_key; z['signal_polarity']=s; z['entry_date']=dates[ix]
        for h in H:
            if ix+h>=len(fx):continue
            rel=[math.log(pair_value(fx[ix+h],'JPY',o)/pair_value(fx[ix],'JPY',o)) for o in CCY if o!='JPY']
            basket=sum(rel)/len(rel); z[f'basket_log_return_{h}d']=basket; z[f'signed_{h}d']=s*basket
        rows.append(z)
    return rows

def main():
    frozen=json.loads(REPLAY.read_text(encoding='utf-8'))
    assert frozen['engine']['rules_fingerprint']=='3356baf0'
    assert frozen['engine']['threshold_direction']==TH
    events=build_signal_events()
    variants={}
    for name,key in [('wages_only','wages_polarity'),('inflation_only','inflation_polarity'),('wages_cpi_agreement','combined_polarity')]:
        rows=attach_returns(events,key); wf=walk(rows); pooled=wf.pop('pooled_rows')
        variants[name]={'full_sample':summarize(rows),'walkforward':wf,'robustness_20d_oos':robustness_20(pooled),'oos_event_dates':[r['checkpoint'] for r in pooled]}
    agree=[e for e in events if e['wages_polarity']!=0 and e['wages_polarity']==e['inflation_polarity']]
    conflict=[e for e in events if e['wages_polarity']!=0 and e['inflation_polarity']!=0 and e['wages_polarity']==-e['inflation_polarity']]
    payload={
        'schema':'GMFQ_JPY_REACTION_ROBUSTNESS_ATTRIBUTION_V1','status':'PASS_DIAGNOSTIC_NOT_PROMOTED','created_at':'2026-10-07',
        'source_replay':str(REPLAY),'engine_frozen_commit':frozen['engine']['frozen_commit'],'rules_fingerprint':'3356baf0',
        'method':{'threshold_direction':TH,'minimum_observations':MINOBS,'rolling_scale_window':WIN,'walkforward':'40/20/20/20 chronological expanding cohorts per variant','robustness':'OOS only; 10k bootstrap mean CI; 20k random-sign permutation; exact binomial sign test; leave-one-event-out; top-3 concentration'},
        'event_structure':{'all_checkpoints':len(events),'agreement_directional':len(agree),'conflicting_directional':len(conflict)},
        'variants':variants,
        'interpretation_guardrail':'Attribution variants are diagnostics, not new candidate rules. No threshold/weight/horizon tuning and no production promotion.',
        'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False
    }
    OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':payload['status'],'event_structure':payload['event_structure'],'variants':{k:{'oos':v['walkforward']['pooled_oos'],'robustness20':v['robustness_20d_oos']} for k,v in variants.items()}},indent=2))

if __name__=='__main__':main()
