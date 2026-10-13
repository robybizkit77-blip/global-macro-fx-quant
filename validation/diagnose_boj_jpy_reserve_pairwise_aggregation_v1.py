#!/usr/bin/env python3
from __future__ import annotations
import itertools,json,urllib.parse,urllib.request
from pathlib import Path
RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
BASE='https://www.stat-search.boj.or.jp/api/v1'; DB='MD08'; UA='global-macro-fx-quant/1.0'

def get(endpoint,params):
 url=BASE+'/'+endpoint+'?'+urllib.parse.urlencode(params)
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=60) as r: return json.loads(r.read().decode('utf-8-sig'))

def walk(x):
 if isinstance(x,dict):
  yield x
  for v in x.values(): yield from walk(v)
 elif isinstance(x,list):
  for v in x: yield from walk(v)

def candidates():
 o=get('getMetadata',{'format':'json','lang':'en','db':DB}); found={}
 for row in walk(o):
  code=next((str(row[k]) for k in ('SERIES_CODE','seriesCode','series_code','CODE','code') if row.get(k)),None)
  if not code: continue
  text=' '.join(str(v) for v in row.values() if isinstance(v,(str,int,float)))
  low=text.lower(); score=sum(t in low for t in ('current account','balance','reserve','sector','boj'))
  if score>=2 and (code not in found or score>found[code]['score']): found[code]={'code':code,'score':score,'metadata':text[:1200]}
 return sorted(found.values(),key=lambda x:(-x['score'],x['code']))[:120]

def series(code):
 o=get('getDataCode',{'format':'json','lang':'en','db':DB,'startDate':'201601','endDate':'202612','code':code})
 rs=o.get('RESULTSET') or []
 if o.get('STATUS')!=200 or len(rs)!=1:return None
 row=rs[0]; vals=row.get('VALUES') or {}; out={}
 for d,v in zip(vals.get('SURVEY_DATES') or [],vals.get('VALUES') or []):
  if v is None:continue
  s=str(d)
  if len(s)>=6:
   try:out[s[:4]+'-'+s[4:6]]=float(v)
   except:pass
 return {'code':code,'name':row.get('NAME_OF_TIME_SERIES'),'unit':row.get('UNIT'),'frequency':row.get('FREQUENCY'),'values':out}

def runtime():
 r=json.loads(RUNTIME.read_text())['JPY']['liquidity']; return {str(d)[:7]:float(v) for d,v in zip(r['dates'],r['values'])}

def score(rt,a,b,sign):
 common=sorted(set(rt)&set(a)&set(b))
 if len(common)<24:return None
 diffs=[rt[m]-(a[m]+sign*b[m]) for m in common]
 exact=sum(abs(x)<=1e-6 for x in diffs)
 rounded=sum(abs(x)<=0.5 for x in diffs)
 return {'overlap':len(common),'exact':exact,'exact_ratio':exact/len(common),'within_0_5':rounded,'within_0_5_ratio':rounded/len(common),'mae':sum(abs(x) for x in diffs)/len(diffs),'max_abs_diff':max(abs(x) for x in diffs),'last_month':common[-1],'runtime_last':rt[common[-1]],'combo_last':a[common[-1]]+sign*b[common[-1]]}

def main():
 rt=runtime(); meta=candidates(); fetched=[]
 for c in meta:
  try:s=series(c['code'])
  except Exception:continue
  if s and len(set(rt)&set(s['values']))>=24:fetched.append(s)
 results=[]
 for x,y in itertools.combinations(fetched,2):
  for sign in (1,-1):
   sc=score(rt,x['values'],y['values'],sign)
   if sc:results.append({'left':{'code':x['code'],'name':x['name'],'unit':x['unit']},'op':'+' if sign==1 else '-','right':{'code':y['code'],'name':y['name'],'unit':y['unit']},'score':sc})
 results.sort(key=lambda z:(-z['score']['exact_ratio'],-z['score']['within_0_5_ratio'],z['score']['mae']))
 best=results[0] if results else None
 proven=bool(best and best['score']['overlap']>=24 and best['score']['exact_ratio']==1.0)
 out={'schema':'GMFQ_LIQUIDITY_JPY_RESERVE_PAIRWISE_AGGREGATION_DIAGNOSTIC_V1','status':'EXACT_PAIRWISE_AGGREGATION_PROVEN' if proven else 'WITHHELD_NO_EXACT_PAIRWISE_AGGREGATION','database':DB,'candidate_series_fetched':len(fetched),'pairwise_tests':len(results),'best_candidate':best,'top_candidates':results[:20],'promotion_eligible':proven,'runtime_mutated':False,'publication_performed':False}
 print(json.dumps(out,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
