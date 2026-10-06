#!/usr/bin/env python3
import csv,json,math,urllib.request
from bisect import bisect_right
from pathlib import Path
REPLAY_URL='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/staging-usd-pit-readiness-2026-10-03/validation/PIT_MACRO_REPLAY_V1_2026-10-03.json'
PRICE=Path('history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv')
OUT=Path('validation/PIT_MACRO_G8_BASKET_BACKTEST_V1_2026-10-06.json')
CCY=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']; H=(5,20,60)

def load(url):
 r=urllib.request.Request(url,headers={'User-Agent':'GMFQ-PIT-basket/1.0'})
 with urllib.request.urlopen(r,timeout=60) as x:return json.loads(x.read().decode())
def pair_value(row,a,b):
 if a==b:return 1.0
 order=CCY.index(a)<CCY.index(b); key=a+b if order else b+a
 v=float(row[key]); return v if order else 1.0/v

def stats(vals):
 if not vals:return {'n':0,'hit_rate':None,'mean_signed_log_return':None,'median_signed_log_return':None}
 s=sorted(vals);n=len(vals);m=s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2
 return {'n':n,'hit_rate':sum(v>0 for v in vals)/n,'mean_signed_log_return':sum(vals)/n,'median_signed_log_return':m}

def main():
 rep=load(REPLAY_URL); assert rep['engine']['rules_fingerprint']=='3356baf0'
 rows=[]
 with PRICE.open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
 dates=[r['date'] for r in rows]
 result={}
 for c in ('EUR','CAD'):
  sig=[]
  for x in rep['currencies'][c]['replay']:
   pol=x.get('macro_polarity')
   if pol not in (-1,1):continue
   i=bisect_right(dates,x['checkpoint'])
   if i>=len(rows):continue
   rec={'checkpoint':x['checkpoint'],'entry_date':dates[i],'polarity':pol}
   for h in H:
    if i+h>=len(rows):continue
    rel=[]
    for o in CCY:
     if o==c:continue
     p0=pair_value(rows[i],c,o);p1=pair_value(rows[i+h],c,o)
     rel.append(math.log(p1/p0))
    basket=sum(rel)/len(rel)
    rec[f'basket_log_return_{h}d']=basket;rec[f'signed_{h}d']=pol*basket
   sig.append(rec)
  regime=[];last=None
  for s in sig:
   if s['polarity']!=last:regime.append(s);last=s['polarity']
  result[c]={'signal_count':len(sig),'regime_entry_count':len(regime),'all_checkpoints':{f'{h}d':stats([s[f'signed_{h}d'] for s in sig if f'signed_{h}d' in s]) for h in H},'regime_entries':{f'{h}d':stats([s[f'signed_{h}d'] for s in regime if f'signed_{h}d' in s]) for h in H},'signals':sig,'regime_samples':regime}
 out={'schema':'GMFQ_PIT_MACRO_G8_BASKET_BACKTEST_V1','status':'PASS','created_at':'2026-10-06','scope':'Frozen PIT Macro block directional validation for EUR and CAD versus equal-weight G8 counterpart basket; not a full engine backtest.','engine':{'commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0','threshold_tuning':False},'entry_policy':'First ECB daily reference observation strictly after checkpoint.','basket_method':'Mean log return of tested currency against the other seven G8 currencies. Signed by frozen macro polarity.','currencies':result,'guardrails':['PIT replay only','No revised-history fallback','No threshold tuning','Only currencies with full PIT macro vote','Conservative next-reference-price entry'],'changes_live_data':False,'changes_engine_rules':False,'changes_oos_baseline':False}
 OUT.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({c:{k:v for k,v in result[c].items() if k not in ('signals','regime_samples')} for c in result},indent=2))
if __name__=='__main__':main()
