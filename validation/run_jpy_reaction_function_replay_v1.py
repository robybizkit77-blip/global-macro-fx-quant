#!/usr/bin/env python3
from __future__ import annotations
import csv, json, math, statistics
from bisect import bisect_right
from pathlib import Path

ROOT=Path('history/pit_v1')
FX=ROOT/'FX_G8_DAILY_ECB_2016_2026.csv'
BASELINE=Path('validation/JPY_FROZEN_MACRO_REPLAY_V1_2026-10-06.json')
OUT=Path('validation/JPY_REACTION_FUNCTION_REPLAY_V1_2026-10-06.json')
SPEC=Path('validation/JPY_REACTION_FUNCTION_V1_SPEC_2026-10-06.json')
CCY=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']; H=(5,20,60)
TH=0.20; MINOBS=8; WIN=80

ALIASES={
 'month':['reference_month','observation_month','ref_month'],
 'date':['release_date','first_release_date','publication_date'],
 'status':['pit_status','status','certification_status'],
 'url':['source_url','document_url','report_url','pdf_url','release_url'],
 'wage':['scheduled_cash_earnings_yoy_pct','scheduled_cash_earnings_yoy','scheduled_cash_earnings_pct_yoy','scheduled_cash_earnings_yoy_percent'],
 'headline':['headline_cpi_yoy_pct','cpi_headline_yoy_pct','all_items_yoy_pct','headline_yoy_pct','cpi_all_items_yoy_pct'],
 'core':['core_cpi_yoy_pct','cpi_core_yoy_pct','core_yoy_pct','cpi_ex_fresh_food_yoy_pct','core_ex_fresh_food_yoy_pct'],
}
BAD_STATUS=('UNCERT','WITHHELD','ERROR','FAIL','MISSING','REVISED','FALLBACK')

def pick(headers,names):
 hits=[x for x in names if x in headers]
 return hits[0] if len(hits)==1 else None

def months():
 out=[]; y,m=2018,1
 while (y,m)<=(2023,7):
  out.append(f'{y:04d}-{m:02d}'); m+=1
  if m==13:y+=1;m=1
 return out
EXPECTED=months()

def inspect(path,kind):
 try:
  with path.open(newline='',encoding='utf-8-sig') as f:
   reader=csv.DictReader(f)
   rows=list(reader)
   headers=reader.fieldnames or []
 except Exception as e:return {'path':str(path),'ok':False,'reason':f'read_error:{e}'}
 cols={k:pick(headers,ALIASES[k]) for k in ('month','date','status','url')}
 if kind=='wages': cols['value']=pick(headers,ALIASES['wage'])
 else:
  cols['headline']=pick(headers,ALIASES['headline']); cols['core']=pick(headers,ALIASES['core'])
 checks=[h for h in headers if ('sha256' in h.lower() or 'checksum' in h.lower())]
 required=list(cols.values())
 if any(x is None for x in required):return {'path':str(path),'ok':False,'reason':'ambiguous_or_missing_semantic_columns','headers':headers}
 if len(rows)!=67:return {'path':str(path),'ok':False,'reason':f'row_count_{len(rows)}','cols':cols}
 mm=[r[cols['month']].strip()[:7] for r in rows]
 if mm!=EXPECTED or len(set(mm))!=67:return {'path':str(path),'ok':False,'reason':'coverage_or_duplicate_failure','cols':cols}
 if not checks:return {'path':str(path),'ok':False,'reason':'checksum_column_missing','cols':cols}
 for r in rows:
  st=(r[cols['status']] or '').upper()
  if not st or any(x in st for x in BAD_STATUS):return {'path':str(path),'ok':False,'reason':'non_green_status','cols':cols}
  if not (r[cols['date']] or '').strip() or not (r[cols['url']] or '').strip():return {'path':str(path),'ok':False,'reason':'date_or_url_missing','cols':cols}
  if not any((r.get(c) or '').strip() for c in checks):return {'path':str(path),'ok':False,'reason':'checksum_missing','cols':cols}
  try:
   if kind=='wages': float(r[cols['value']])
   else: float(r[cols['headline']]); float(r[cols['core']])
  except Exception:return {'path':str(path),'ok':False,'reason':'numeric_value_failure','cols':cols}
 return {'path':str(path),'ok':True,'cols':cols,'checksum_cols':checks,'rows':rows}

def discover(kind):
 files=[]
 for p in ROOT.glob('*.csv'):
  n=p.name.upper()
  if 'JPY' not in n:continue
  if kind=='wages' and not any(x in n for x in ('WAGE','EARNING','MHLW')):continue
  if kind=='cpi' and 'CPI' not in n:continue
  z=inspect(p,kind); files.append(z)
 good=[x for x in files if x['ok']]
 return good,files

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

def cls(x):
 if x is None:return 'NEUTRAL_OR_PARTIAL'
 if x>=TH:return 'HAWKISH'
 if x<=-TH:return 'DOVISH'
 return 'NEUTRAL_OR_PARTIAL'

def state(w,i):
 if w=='HAWKISH' and i=='HAWKISH':return 'SUSTAINABLE_INFLATION_PRESSURE',1
 if w=='DOVISH' and i=='DOVISH':return 'DISINFLATION_NORMALIZATION_DELAY',-1
 if w=='HAWKISH' and i=='DOVISH':return 'MIXED_WAGES_UP_INFLATION_DOWN',0
 if w=='DOVISH' and i=='HAWKISH':return 'MIXED_WAGES_DOWN_INFLATION_UP',0
 return 'PARTIAL_NEUTRAL',0

def pair_value(row,a,b):
 if a==b:return 1.0
 ordered=CCY.index(a)<CCY.index(b); key=a+b if ordered else b+a
 v=float(row[key]); return v if ordered else 1.0/v

def stats(vals):
 if not vals:return {'n':0,'hit_rate':None,'mean_signed_log_return':None,'median_signed_log_return':None}
 return {'n':len(vals),'hit_rate':sum(x>0 for x in vals)/len(vals),'mean_signed_log_return':sum(vals)/len(vals),'median_signed_log_return':statistics.median(vals)}
def summarize(rows):return {f'{h}d':stats([r[f'signed_{h}d'] for r in rows if f'signed_{h}d' in r]) for h in H}
def walk(rows):
 n=len(rows); start=math.floor(n*.4); prev=start; folds=[]; pooled=[]
 for k,frac in enumerate((.6,.8,1.0),1):
  end=n if frac==1 else max(prev+1,math.floor(n*frac)); test=rows[prev:end]; pooled+=test
  folds.append({'fold':k,'train_event_count':prev,'test_event_count':len(test),'test_start':test[0]['checkpoint'] if test else None,'test_end':test[-1]['checkpoint'] if test else None,'stats':summarize(test)}); prev=end
 return {'initial_train_fraction':.4,'folds':folds,'pooled_oos_event_count':len(pooled),'pooled_oos':summarize(pooled)}

def withheld(reason,wscan,cscan):
 payload={'schema':'GMFQ_JPY_REACTION_FUNCTION_REPLAY_V1','status':'WITHHELD_NO_REPLAY_VOTE','created_at':'2026-10-06','reason':reason,'spec_file':str(SPEC),'engine':{'frozen_commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0'},'input_discovery':{'wages':[{k:v for k,v in x.items() if k!='rows'} for x in wscan],'cpi':[{k:v for k,v in x.items() if k!='rows'} for x in cscan]},'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
 OUT.write_text(json.dumps(payload,indent=2)+'\n'); print(json.dumps({'status':payload['status'],'reason':reason},indent=2))

def main():
 spec=json.loads(SPEC.read_text()); assert spec['engine']['rules_fingerprint']=='3356baf0'
 wg,ws=discover('wages'); cg,cs=discover('cpi')
 if len(wg)!=1 or len(cg)!=1:
  withheld(f'unique_green_panels_required:wages={len(wg)},cpi={len(cg)}',ws,cs); return
 w,c=wg[0],cg[0]; wc=w['cols']; cc=c['cols']
 wages=[{'release_date':r[wc['date']].strip(),'value':float(r[wc['value']])} for r in w['rows']]
 head=[{'release_date':r[cc['date']].strip(),'value':float(r[cc['headline']])} for r in c['rows']]
 core=[{'release_date':r[cc['date']].strip(),'value':float(r[cc['core']])} for r in c['rows']]
 cps=sorted(set([r['release_date'] for r in wages+head]))
 evidence=[]
 for cp in cps:
  wv=[r['value'] for r in wages if r['release_date']<=cp]; hv=[r['value'] for r in head if r['release_date']<=cp]; cv=[r['value'] for r in core if r['release_date']<=cp]
  wi=impulse(wv); hi=impulse(hv); ci=impulse(cv); ii=med([x for x in (hi,ci) if x is not None])
  wsx,isx=cls(wi),cls(ii); st,pol=state(wsx,isx)
  evidence.append({'checkpoint':cp,'wages_impulse':wi,'headline_impulse':hi,'core_impulse':ci,'inflation_impulse':ii,'wages_state':wsx,'inflation_state':isx,'boj_state':st,'jpy_polarity':pol})
 directional=[x for x in evidence if x['jpy_polarity'] in (-1,1)]
 with FX.open(newline='',encoding='utf-8') as f: fx=list(csv.DictReader(f))
 dates=[r['date'] for r in fx]; samples=[]
 for e in directional:
  ix=bisect_right(dates,e['checkpoint'])
  if ix>=len(fx):continue
  z=dict(e); z['entry_date']=dates[ix]
  for h in H:
   if ix+h>=len(fx):continue
   rel=[math.log(pair_value(fx[ix+h],'JPY',o)/pair_value(fx[ix],'JPY',o)) for o in CCY if o!='JPY']
   basket=sum(rel)/len(rel); z[f'basket_log_return_{h}d']=basket; z[f'signed_{h}d']=e['jpy_polarity']*basket
  samples.append(z)
 baseline=json.loads(BASELINE.read_text()) if BASELINE.exists() else None
 payload={'schema':'GMFQ_JPY_REACTION_FUNCTION_REPLAY_V1','status':'PASS_DIAGNOSTIC_NOT_PROMOTED','created_at':'2026-10-06','spec_file':str(SPEC),'engine':{'frozen_commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0','threshold_direction':TH,'minimum_observations':MINOBS,'threshold_tuning':False},'inputs':{'wages':w['path'],'cpi':c['path']},'event_universe':{'all_checkpoint_count':len(evidence),'directional_checkpoint_count':len(samples)},'full_sample':summarize(samples),'walkforward':walk(samples),'rates_layer':{'status':'WITHHELD','reason':'No certified historical JPY front-end/yield-differential series attached to this replay; rates do not gate events.'},'baseline_growth_labour':{'file':str(BASELINE),'pooled_oos':baseline.get('walkforward',{}).get('pooled_oos') if baseline else None},'state_evidence':evidence,'directional_samples':samples,'guardrails':spec['guardrails'],'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False,'adapter_fix':'csv.DictReader.fieldnames used for semantic header inspection; no frozen model logic changed'}
 OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); print(json.dumps({'status':payload['status'],'events':payload['event_universe'],'full_sample':payload['full_sample'],'pooled_oos':payload['walkforward']['pooled_oos']},indent=2))
if __name__=='__main__':main()
