#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,math
from bisect import bisect_right
from datetime import date
from pathlib import Path

ALPHA=10.0; MIN_TRAIN=36
BLOCKS=[('2021-03_to_2022-12','2021-03-10','2022-12-10'),('2023_to_2024','2023-01-10','2024-12-10'),('2025_to_2026-07','2025-01-10','2026-07-10')]
MODELS={
 'OLD_EQUAL_MANDATE':['inflation','unemployment','yield_2y','yield_10y','curve_bp'],
 'ECB_PRICE_STABILITY_FIRST':['inflation','yield_2y','yield_10y','curve_bp'],
}

def mean(x): return sum(x)/len(x)
def sd(x):
 m=mean(x); return math.sqrt(sum((v-m)**2 for v in x)/(len(x)-1)) if len(x)>1 else 0.0
def sharpe(x):
 s=sd(x); return None if s<=1e-12 else mean(x)/s*math.sqrt(12)
def mdd(x):
 w=p=1.0; d=0.0
 for r in x:
  w*=math.exp(r); p=max(p,w); d=min(d,w/p-1)
 return d
def solve(a,b):
 n=len(b); z=[a[i][:]+[b[i]] for i in range(n)]
 for c in range(n):
  q=max(range(c,n),key=lambda r:abs(z[r][c])); z[c],z[q]=z[q],z[c]
  k=z[c][c]
  if abs(k)<1e-12: raise RuntimeError('singular')
  z[c]=[v/k for v in z[c]]
  for r in range(n):
   if r==c: continue
   k=z[r][c]
   if k: z[r]=[z[r][j]-k*z[c][j] for j in range(n+1)]
 return [z[i][-1] for i in range(n)]
def fit(x,y):
 p=len(x[0]); mu=[mean([r[j] for r in x]) for j in range(p)]; s=[sd([r[j] for r in x]) or 1 for j in range(p)]
 z=[[1]+[(r[j]-mu[j])/s[j] for j in range(p)] for r in x]; k=p+1; xtx=[[0.0]*k for _ in range(k)]; xty=[0.0]*k
 for row,t in zip(z,y):
  for i in range(k):
   xty[i]+=row[i]*t
   for j in range(k): xtx[i][j]+=row[i]*row[j]
 for i in range(1,k): xtx[i][i]+=ALPHA
 return solve(xtx,xty),mu,s
def pred(beta,mu,s,x): return beta[0]+sum(beta[j+1]*(x[j]-mu[j])/s[j] for j in range(len(x)))

def load_macro(path,value_col):
 out=[]
 with path.open(newline='',encoding='utf-8-sig') as f:
  for r in csv.DictReader(f): out.append({'ref':r['reference_month'],'release':r['release_date'],'value':float(r[value_col])})
 return out
def load_rates(path):
 out=[]
 with path.open(newline='',encoding='utf-8-sig') as f:
  for r in csv.DictReader(f): out.append({'obs':r['observation_date'],'eligible':r['first_eligible_decision_date'],'y2':float(r['yield_2y']),'y10':float(r['yield_10y'])})
 return out
def latest_macro(rows,dp): return max((r for r in rows if r['release']<dp),key=lambda r:(r['release'],r['ref']))
def latest_rates(rows,dp): return max((r for r in rows if r['eligible']<=dp and r['obs']<dp),key=lambda r:r['obs'])
def grid():
 out=[]; y,m=2018,3
 while (y,m)<=(2026,8): out.append(f'{y:04d}-{m:02d}-10'); y,m=(y+1,1) if m==12 else (y,m+1)
 return out
def prices(path):
 d={}
 with path.open(newline='',encoding='utf-8-sig') as f:
  rd=csv.DictReader(f); fs=rd.fieldnames or []; dk=next(k for k in ['TIME_PERIOD','TIME PERIOD','Date','DATE'] if k in fs); vk=next(k for k in ['OBS_VALUE','OBS VALUE','Value','VALUE'] if k in fs)
  for r in rd:
   ds=(r.get(dk) or '')[:10]; vs=(r.get(vk) or '').strip()
   try: date.fromisoformat(ds); v=float(vs)
   except: continue
   if v>0: d[ds]=v
 return sorted(d),d
def first_after(dp,ds,p):
 i=bisect_right(ds,dp)
 if i>=len(ds): raise RuntimeError('missing price')
 return p[ds[i]]
def metrics(rows):
 a=[r['actual'] for r in rows]; p=[r['prediction'] for r in rows]; s=[r['strategy'] for r in rows]
 return {'observations':len(rows),'directional_accuracy':sum(1 for x,y in zip(p,a) if x*y>0)/len(rows),'strategy_total_return':math.exp(sum(s))-1,'strategy_annualized_sharpe':sharpe(s),'strategy_max_drawdown':mdd(s)}
def run(labelled,features):
 out=[]
 for t in range(MIN_TRAIN,len(labelled)):
  tr=labelled[:t]; b,mu,s=fit([[r[f] for f in features] for r in tr],[r['ret'] for r in tr]); pr=pred(b,mu,s,[labelled[t][f] for f in features]); a=labelled[t]['ret']; sig=1 if pr>0 else -1 if pr<0 else 0
  out.append({'dp':labelled[t]['dp'],'prediction':pr,'actual':a,'strategy':sig*a})
 blocks={name:metrics([r for r in out if lo<=r['dp']<=hi]) for name,lo,hi in BLOCKS}
 return {'features':features,'overall':metrics(out),'time_blocks':blocks}

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--inflation',type=Path,required=True); ap.add_argument('--labour',type=Path,required=True); ap.add_argument('--rates',type=Path,required=True); ap.add_argument('--ecb',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
 inf=load_macro(a.inflation,'headline_hicp_yoy_pct'); lab=load_macro(a.labour,'unemployment_rate_pct'); rates=load_rates(a.rates); ds,px=prices(a.ecb)
 rows=[]
 for dp in grid():
  i=latest_macro(inf,dp); l=latest_macro(lab,dp); r=latest_rates(rates,dp); p=first_after(dp,ds,px)
  rows.append({'dp':dp,'price':p,'inflation':i['value'],'unemployment':l['value'],'yield_2y':r['y2'],'yield_10y':r['y10'],'curve_bp':(r['y10']-r['y2'])*100})
 labelled=[]
 for i in range(len(rows)-1):
  r=dict(rows[i]); r['ret']=math.log(rows[i+1]['price']/r['price']); labelled.append(r)
 models={k:run(labelled,v) for k,v in MODELS.items()}
 old=models['OLD_EQUAL_MANDATE']['overall']; new=models['ECB_PRICE_STABILITY_FIRST']['overall']
 out={'schema':'GMFQ_ECB_MANDATE_SENSITIVITY_V1','status':'DIAGNOSTIC_COMPLETE','scope':{'instrument':'EURUSD','eur_only':True,'snapshot_count':len(rows),'oos_predictions':new['observations'],'full_fed_vs_ecb_test_possible':False,'blocker':'USD inflation/labour strict-PIT history not certified'},'method':{'old_logic':'EUR inflation and unemployment both enter as direct macro features','new_logic':'ECB price-stability-first: inflation remains direct macro feature; unemployment is removed as an equal mandate feature while Rates remain unchanged','ridge_alpha_fixed':ALPHA,'minimum_training_months':MIN_TRAIN,'hyperparameter_tuning':False},'models':models,'comparison':{'new_minus_old_hit_rate':new['directional_accuracy']-old['directional_accuracy'],'new_minus_old_sharpe':new['strategy_annualized_sharpe']-old['strategy_annualized_sharpe'],'new_minus_old_total_return':new['strategy_total_return']-old['strategy_total_return']},'policy':{'diagnostic_only':True,'production_signal_authorized':False,'full_dual_mandate_conclusion_authorized':False}}
 a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
 print(json.dumps(out,indent=2,sort_keys=True))
if __name__=='__main__': main()
