#!/usr/bin/env python3
import csv,json,math,random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WAGES=ROOT/'history/pit_v1/EUR_NEGOTIATED_WAGES_CERTIFIED_VINTAGES_SEED.csv'
RATES=ROOT/'history/pit_v1/EUR_RATES_2Y_10Y_ECB_SAME_BASIS_2016_2026.csv'
FX=ROOT/'history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv'
OUT=ROOT/'validation/EUR_REACTION_FUNCTION_DIAGNOSTIC_V2_2026-10-06.json'
H=[5,20,60]; G8=['USD','GBP','JPY','CHF','CAD','AUD','NZD']; WIN=5
random.seed(20261006)

def median(xs):
 s=sorted(xs);n=len(s);return s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2

def stats(rs):
 out={}
 for h in H:
  xs=[r[f'signed_{h}d'] for r in rs if r.get(f'signed_{h}d') is not None]
  out[f'{h}d']={'n':len(xs),'hit_rate':sum(x>0 for x in xs)/len(xs) if xs else None,'mean':sum(xs)/len(xs) if xs else None,'median':median(xs) if xs else None}
 return out

def boot(rs,h,b=5000):
 xs=[r[f'signed_{h}d'] for r in rs if r.get(f'signed_{h}d') is not None]
 if not xs:return [None,None]
 ms=[];n=len(xs)
 for _ in range(b):ms.append(sum(xs[random.randrange(n)] for __ in range(n))/n)
 ms.sort();return [ms[int(.025*b)],ms[min(b-1,int(.975*b))]]

fx=list(csv.DictReader(FX.open(encoding='utf-8'))); rates=list(csv.DictReader(RATES.open(encoding='utf-8')))

def idx_after(rows,d):
 for i,r in enumerate(rows):
  if r['date']>d:return i
 return None

def idx_on_after(rows,d):
 for i,r in enumerate(rows):
  if r['date']>=d:return i
 return None

def eurret(i,h):
 if i is None or i+h>=len(fx):return None
 vals=[]
 for c in G8:
  col='EUR'+c
  try:a=float(fx[i][col]);b=float(fx[i+h][col]);vals.append(math.log(b/a))
  except:pass
 return sum(vals)/len(vals) if vals else None

# Same actionable wage history as V1.
wr=list(csv.DictReader(WAGES.open(encoding='utf-8'))); by={}
for r in wr:
 d=r['certified_available_date']
 if not d:continue
 if d not in by or r['reference_quarter']>by[d]['reference_quarter']:by[d]=r
act=[by[d] for d in sorted(by)]
points=[];prev=None
for r in act:
 v=float(r['annual_growth_pct'])
 if prev is not None: points.append((r['certified_available_date'],v-prev,r['reference_quarter']))
 prev=v
# Exact base cohort: new-sign regime entries only, as V1 wages standalone.
base=[]; prevsig=0
for d,delta,q in points:
 sig=1 if delta>0 else -1 if delta<0 else 0
 if sig==0 or sig==prevsig: continue
 prevsig=sig
 base.append({'wage_checkpoint':d,'signal':sig,'reference_quarter':q})

rows=[]
for e in base:
 i=idx_on_after(rates,e['wage_checkpoint'])
 if i is None or i+WIN>=len(rates):continue
 r0=float(rates[i]['eur_2y_pct']);r1=float(rates[i+WIN]['eur_2y_pct']);dr=r1-r0
 rs=1 if dr>0 else -1 if dr<0 else 0
 conf=rates[i+WIN]['date']; j=idx_after(fx,conf)
 if j is None:continue
 z=dict(e);z.update({'rate_start_date':rates[i]['date'],'confirmation_date':conf,'eur_2y_change_pp':dr,'rate_signal':rs,'rate_state':'ALIGNED' if rs==e['signal'] else 'CONFLICT' if rs==-e['signal'] else 'FLAT','fx_entry_date':fx[j]['date']})
 for h in H:
  rr=eurret(j,h);z[f'signed_{h}d']=None if rr is None else e['signal']*rr
 rows.append(z)

aligned=[r for r in rows if r['rate_state']=='ALIGNED']; conflict=[r for r in rows if r['rate_state']=='CONFLICT']; flat=[r for r in rows if r['rate_state']=='FLAT']
# Chronological expanding OOS, preserving exact cohort.
def folds(rs,nf=4):
 rs=sorted(rs,key=lambda x:x['wage_checkpoint']);n=len(rs)
 if n<8:return []
 seed=max(1,int(.4*n));rem=n-seed;out=[]
 for f in range(nf):
  a=seed+(rem*f)//nf;b=seed+(rem*(f+1))//nf;t=rs[a:b]
  if t:out.append({'fold':f+1,'train_end':rs[a-1]['wage_checkpoint'],'test_start':t[0]['wage_checkpoint'],'test_end':t[-1]['wage_checkpoint'],'test_n':len(t),'stats':stats(t)})
 return out

def pooled(rs,fs):
 chosen=[]
 for f in fs: chosen += [r for r in rs if f['test_start']<=r['wage_checkpoint']<=f['test_end']]
 seen=set();u=[]
 for r in chosen:
  k=(r['wage_checkpoint'],r['reference_quarter'])
  if k not in seen:seen.add(k);u.append(r)
 return stats(u)
fs=folds(rows)
res={'schema':'GMFQ_EUR_REACTION_FUNCTION_DIAGNOSTIC_V2','status':'PASS','created_at':'2026-10-06','scope':'Exact same V1 negotiated-wage new-sign regime-entry cohort for ALL / EUR2Y aligned / EUR2Y conflict. Fixed 5-market-day 2Y observation window. FX entry for every group strictly after the identical confirmation checkpoint. Diagnostic only.','engine_baseline':{'commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0','modified':False},'guardrails':['exact same base cohort across rate states','fixed 5-market-day 2Y window','same FX timing for all groups','no threshold tuning','no fitted weights','no post-hoc filtering','conservative certified wage availability dates retained','engine/live_data untouched'],'counts':{'base_regime_entries':len(base),'paired':len(rows),'aligned':len(aligned),'conflict':len(conflict),'flat':len(flat)},'all_same_timing':{'stats':stats(rows),'bootstrap_mean_95':{f'{h}d':boot(rows,h) for h in H}},'aligned':{'stats':stats(aligned),'bootstrap_mean_95':{f'{h}d':boot(aligned,h) for h in H}},'conflict':{'stats':stats(conflict),'bootstrap_mean_95':{f'{h}d':boot(conflict,h) for h in H}},'flat':{'stats':stats(flat)},'incremental_aligned_vs_conflict':{f'{h}d':{'mean':(stats(aligned)[f'{h}d']['mean']-stats(conflict)[f'{h}d']['mean']) if stats(aligned)[f'{h}d']['mean'] is not None and stats(conflict)[f'{h}d']['mean'] is not None else None,'hit_rate_pp':100*(stats(aligned)[f'{h}d']['hit_rate']-stats(conflict)[f'{h}d']['hit_rate']) if stats(aligned)[f'{h}d']['hit_rate'] is not None and stats(conflict)[f'{h}d']['hit_rate'] is not None else None} for h in H},'walk_forward':{'folds':fs,'pooled_oos':pooled(rows,fs)},'rows':rows,'changes_engine_rules':False,'changes_live_data':False}
OUT.write_text(json.dumps(res,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:res[k] for k in ['counts','all_same_timing','aligned','conflict','incremental_aligned_vs_conflict','walk_forward']},indent=2))
