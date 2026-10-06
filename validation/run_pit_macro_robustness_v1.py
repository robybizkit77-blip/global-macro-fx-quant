#!/usr/bin/env python3
from __future__ import annotations
import json, math, random, statistics
from collections import defaultdict
from pathlib import Path

SRC=Path('validation/PIT_MACRO_G8_BASKET_BACKTEST_V1_2026-10-06.json')
OUT=Path('validation/PIT_MACRO_ROBUSTNESS_V1_2026-10-06.json')
H=['5d','20d','60d']
SEED=3356
B=20000


def pct(x): return None if not x else sum(v>0 for v in x)/len(x)
def mean(x): return None if not x else statistics.fmean(x)
def med(x): return None if not x else statistics.median(x)
def quantile(xs,q):
    if not xs:return None
    ys=sorted(xs); p=(len(ys)-1)*q; lo=math.floor(p); hi=math.ceil(p)
    if lo==hi:return ys[lo]
    return ys[lo]*(hi-p)+ys[hi]*(p-lo)
def bootstrap(vals, seed):
    if not vals:return {'n':0}
    r=random.Random(seed); n=len(vals); hits=[]; means=[]
    for _ in range(B):
        s=[vals[r.randrange(n)] for __ in range(n)]
        hits.append(sum(v>0 for v in s)/n); means.append(statistics.fmean(s))
    return {'n':n,'hit_rate':pct(vals),'mean':mean(vals),'median':med(vals),
            'hit_rate_ci95':[quantile(hits,.025),quantile(hits,.975)],
            'mean_ci95':[quantile(means,.025),quantile(means,.975)]}
def wilson(k,n,z=1.959963984540054):
    if n==0:return [None,None]
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,c-h),min(1,c+h)]
def summarize(vals):
    if not vals:return {'n':0}
    k=sum(v>0 for v in vals); return {'n':len(vals),'hit_rate':k/len(vals),'hit_rate_wilson95':wilson(k,len(vals)),'mean':mean(vals),'median':med(vals)}
def trim_one_each_tail(vals):
    if len(vals)<=2:return vals
    ys=sorted(vals); return ys[1:-1]
def jackknife_hit(vals):
    if len(vals)<=1:return []
    return [pct(vals[:i]+vals[i+1:]) for i in range(len(vals))]


data=json.loads(SRC.read_text())
out={'schema':'GMFQ_PIT_MACRO_ROBUSTNESS_V1','status':'PASS','created_at':'2026-10-06','source':str(SRC),
     'engine':data['engine'],'method':{'bootstrap_resamples':B,'bootstrap_seed':SEED,'primary_sample':'regime entries only','no_threshold_tuning':True},'currencies':{}}

for ci,(cc,c) in enumerate(data['currencies'].items()):
    entries=c.get('regime_entry_samples') or c.get('regime_entries_samples') or c.get('regime_entry_records') or []
    # artifact stores full signals but not explicit regime-entry samples in some builds: reconstruct by polarity transitions.
    if not entries:
        sig=c.get('signals',[]); prev=0; entries=[]
        for s in sig:
            p=s['polarity']
            if p!=prev:
                entries.append(s)
            prev=p
    co={'regime_entry_count':len(entries),'horizons':{},'by_year':{},'first_half_vs_second_half':{}}
    years=defaultdict(list)
    for e in entries: years[int(e['checkpoint'][:4])].append(e)
    for h in H:
        key='signed_'+h
        vals=[e[key] for e in entries if e.get(key) is not None]
        boot=bootstrap(vals, SEED+ci*100+H.index(h))
        jk=jackknife_hit(vals)
        co['horizons'][h]={**boot,'wilson95':wilson(sum(v>0 for v in vals),len(vals)),
                           'trim_one_each_tail':summarize(trim_one_each_tail(vals)),
                           'jackknife_hit_rate_range':[min(jk),max(jk)] if jk else [None,None],
                           'positive_mean_after_trim': mean(trim_one_each_tail(vals))>0 if trim_one_each_tail(vals) else None,
                           'bootstrap_mean_ci_excludes_zero': bool(boot.get('mean_ci95') and (boot['mean_ci95'][0]>0 or boot['mean_ci95'][1]<0)),
                           'bootstrap_hit_ci_above_50': bool(boot.get('hit_rate_ci95') and boot['hit_rate_ci95'][0]>.5)}
    for y,es in sorted(years.items()):
        co['by_year'][str(y)]={h:summarize([e['signed_'+h] for e in es if e.get('signed_'+h) is not None]) for h in H}
    ordered=sorted(entries,key=lambda e:e['checkpoint']); cut=len(ordered)//2
    for name,es in [('first_half',ordered[:cut]),('second_half',ordered[cut:])]:
        co['first_half_vs_second_half'][name]={h:summarize([e['signed_'+h] for e in es if e.get('signed_'+h) is not None]) for h in H}
    out['currencies'][cc]=co

# conservative verdict, fixed ex ante for this audit: descriptive robustness only; no promotion based on passing thresholds.
for cc,c in out['currencies'].items():
    c['assessment']='DESCRIPTIVE_SIGNAL_NOT_STATISTICALLY_LOCKED'
    if all(c['horizons'][h]['n']>=20 for h in H):
        c['sample_size_gate']='PASS'
    else:c['sample_size_gate']='LIMITED'

OUT.write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps({cc:{h:{k:v for k,v in d['horizons'][h].items() if k in ('n','hit_rate','hit_rate_ci95','mean','mean_ci95','bootstrap_hit_ci_above_50','bootstrap_mean_ci_excludes_zero')} for h in H} for cc,d in out['currencies'].items()},indent=2))
