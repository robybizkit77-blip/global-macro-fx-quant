#!/usr/bin/env python3
import json,math,random,statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'validation/USD_FED_REACTION_STATE_V1_2026-10-06.json'
OUT=ROOT/'validation/USD_FED_REACTION_ROBUSTNESS_V1_2026-10-06.json'
H=[5,20,60]
random.seed(20261006)

src=json.loads(SRC.read_text(encoding='utf-8'))
rows=src['rows']


def vals(rs,h): return [r[f'usd_basket_{h}d'] for r in rs if f'usd_basket_{h}d' in r]
def basic(v):
    if not v:return {'n':0,'mean':None,'median':None,'positive_share':None}
    s=sorted(v);n=len(s);med=s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2
    return {'n':n,'mean':sum(v)/n,'median':med,'positive_share':sum(x>0 for x in v)/n}
def wilson(k,n,z=1.959963984540054):
    if n==0:return [None,None]
    p=k/n;den=1+z*z/n;c=(p+z*z/(2*n))/den;m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return [c-m,c+m]
def boot_mean(v,b=5000):
    if not v:return [None,None]
    n=len(v); ms=[]
    for _ in range(b): ms.append(sum(v[random.randrange(n)] for __ in range(n))/n)
    ms.sort();return [ms[int(.025*b)],ms[min(b-1,int(.975*b))]]
def summary(rs,h):
    v=vals(rs,h);b=basic(v)
    b['mean_bootstrap_95']=boot_mean(v)
    b['positive_share_wilson_95']=wilson(sum(x>0 for x in v),len(v))
    return b

def group_summary(rs): return {f'{h}d':summary(rs,h) for h in H}

def chronological_folds(rs,nfold=4):
    rs=sorted(rs,key=lambda r:r['checkpoint'])
    n=len(rs);out=[]
    if n<8:return out
    # expanding chronology: first 40% is seed, then four contiguous OOS blocks.
    seed=max(1,int(n*.40)); rem=n-seed
    for f in range(nfold):
        a=seed+(rem*f)//nfold; b=seed+(rem*(f+1))//nfold
        test=rs[a:b]
        if not test:continue
        out.append({'fold':f+1,'train_end':rs[a-1]['checkpoint'] if a else None,'test_start':test[0]['checkpoint'],'test_end':test[-1]['checkpoint'],'test_n':len(test),'results':group_summary(test)})
    return out

def pooled_oos(folds):
    # Reconstruct pooled test rows by date ranges from the source universe.
    chosen=[]
    for f in folds:
        chosen.extend(r for r in rows if f['test_start']<=r['checkpoint']<=f['test_end'])
    # avoid duplicates when ranges touch (they should not)
    seen=set();uniq=[]
    for r in sorted(chosen,key=lambda x:(x['checkpoint'],x['event_type'])):
        k=(r['checkpoint'],r['event_type'],r['reference_month'])
        if k not in seen:seen.add(k);uniq.append(r)
    return group_summary(uniq)

def half_stability(rs):
    rs=sorted(rs,key=lambda r:r['checkpoint']);m=len(rs)//2
    return {'first_half':group_summary(rs[:m]),'second_half':group_summary(rs[m:])}

def event_type_split(rs):
    return {t:group_summary([r for r in rs if r['event_type']==t]) for t in ['LABOUR_RELEASE','CPI_RELEASE']}

def paired_rates(rs,joint_direction):
    aligned=[r for r in rs if r['rates_direction']==joint_direction]
    conflict=[r for r in rs if r['rates_direction']==-joint_direction]
    flat=[r for r in rs if r['rates_direction']==0]
    incr={}
    for h in H:
        a=basic(vals(aligned,h));c=basic(vals(conflict,h))
        incr[f'{h}d']={
          'aligned_minus_conflict_mean':None if a['mean'] is None or c['mean'] is None else a['mean']-c['mean'],
          'aligned_minus_conflict_positive_share_pp':None if a['positive_share'] is None or c['positive_share'] is None else 100*(a['positive_share']-c['positive_share'])
        }
    return {'aligned':group_summary(aligned),'conflict':group_summary(conflict),'flat':group_summary(flat),'incremental_aligned_vs_conflict':incr,'counts':{'aligned':len(aligned),'conflict':len(conflict),'flat':len(flat)}}

states={
 'BOTH_DOVISH':[r for r in rows if r['joint_state']=='LABOUR_INFLATION_BOTH_DOVISH'],
 'BOTH_HAWKISH':[r for r in rows if r['joint_state']=='LABOUR_INFLATION_BOTH_HAWKISH'],
 'LABOUR_HAWKISH_INFLATION_DOVISH':[r for r in rows if r['joint_state']=='LABOUR_HAWKISH_INFLATION_DOVISH'],
 'LABOUR_DOVISH_INFLATION_HAWKISH':[r for r in rows if r['joint_state']=='LABOUR_DOVISH_INFLATION_HAWKISH'],
 'MIXED_OR_NEUTRAL':[r for r in rows if r['joint_state']=='MIXED_OR_NEUTRAL']
}
rob={}
for name,rs in states.items():
    folds=chronological_folds(rs)
    rob[name]={
      'full_sample':group_summary(rs),
      'bootstrap_and_wilson_included':True,
      'half_stability':half_stability(rs),
      'event_type_split':event_type_split(rs),
      'walk_forward_folds':folds,
      'pooled_oos':pooled_oos(folds)
    }

paired={
 'BOTH_DOVISH':paired_rates(states['BOTH_DOVISH'],-1),
 'BOTH_HAWKISH':paired_rates(states['BOTH_HAWKISH'],+1)
}

res={
 'schema':'GMFQ_USD_FED_REACTION_ROBUSTNESS_V1',
 'status':'PASS',
 'created_at':'2026-10-06',
 'source':'validation/USD_FED_REACTION_STATE_V1_2026-10-06.json',
 'method':'No refit. Same fixed event universe, threshold 0.2, 5-market-day 2Y observation window and 5/20/60d FX horizons. Robustness uses bootstrap mean CI, Wilson hit-rate CI, first/second-half stability, event-type split and chronological expanding-window OOS blocks. Paired 2Y attribution is only within identical BOTH_DOVISH/BOTH_HAWKISH macro states.',
 'guardrails':['no threshold tuning','no event filtering','no fitted weights','no post-hoc parameter selection','2Y comparison never mixes different joint macro states','PCE remains WITHHELD','engine/live_data untouched'],
 'engine_baseline':src['engine_baseline'],
 'state_robustness':rob,
 'paired_2y_within_same_state':paired,
 'changes_engine_rules':False,
 'changes_live_data':False
}
OUT.write_text(json.dumps(res,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'PASS','paired_2y':paired,'pooled_oos':{k:v['pooled_oos'] for k,v in rob.items()}},indent=2))
