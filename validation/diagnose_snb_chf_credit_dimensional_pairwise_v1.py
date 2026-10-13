#!/usr/bin/env python3
import csv,io,json,urllib.request
from collections import defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path

RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
URL='https://data.snb.ch/api/cube/bakredinausbm/data/csv/en?fromDate=2016-01&toDate=2026-12'
SCALES=(1.0,1e-3,1e3,1e-6,1e6)

def fetch():
 req=urllib.request.Request(URL,headers={'User-Agent':'GMFQ-validation/1.0','Accept':'text/csv'})
 with urllib.request.urlopen(req,timeout=90) as r:return r.read().decode('utf-8-sig')
def month(v):
 s=str(v or '').strip()
 for f in ('%Y-%m','%Y-%m-%d','%d.%m.%Y','%d/%m/%Y'):
  try:return datetime.strptime(s,f).strftime('%Y-%m')
  except ValueError:pass
 return None
def n(v):
 s=str(v or '').strip().replace("'",'').replace(' ','')
 if not s:return None
 if s.count(',')==1 and '.' not in s:s=s.replace(',','.')
 try:return float(s)
 except ValueError:return None
def runtime():
 d=json.loads(RUNTIME.read_text(encoding='utf-8'))['CHF']['credit']
 return {month(x):float(v) for x,v in zip(d['dates'],d['values']) if month(x)}
def parse(text):
 try:d=csv.Sniffer().sniff(text[:8192],delimiters=';,\t')
 except csv.Error:d=csv.excel; d.delimiter=';'
 rows=list(csv.reader(io.StringIO(text),dialect=d)); width=max(len(r) for r in rows); rows=[r+['']*(width-len(r)) for r in rows]
 hi=next((i for i,r in enumerate(rows) if [str(x).strip() for x in r[:6]]==['Date','D0','D1','D2','D3','Value']),None)
 if hi is None:raise SystemExit('SNB long-format header Date,D0,D1,D2,D3,Value not found')
 g=defaultdict(dict)
 for r in rows[hi+1:]:
  m=month(r[0]); v=n(r[5])
  if not m or v is None:continue
  key=tuple(str(x).strip() for x in r[1:5]); g[key][m]=v
 return g
def best_score(rt,src):
 common=sorted(set(rt)&set(src)); best=None
 for scale in SCALES:
  diffs=[rt[m]-src[m]*scale for m in common]; exact=sum(abs(x)<=1e-9 for x in diffs); mae=sum(abs(x) for x in diffs)/len(diffs) if diffs else 1e99
  row={'scale':scale,'overlap':len(common),'exact':exact,'exact_ratio':exact/len(common) if common else 0.0,'mae':mae}
  rank=(row['exact_ratio'],exact,-mae)
  if best is None or rank>best[0]:best=(rank,row)
 return best[1]
def main():
 rt=runtime(); all_series=parse(fetch()); singles=[]
 for k,s in all_series.items():
  sc=best_score(rt,s)
  if sc['overlap']>=12:singles.append({'key':k,'series':s,**sc})
 singles.sort(key=lambda x:(x['exact_ratio'],x['exact'],-x['mae']),reverse=True)
 shortlist=singles[:30]; pairs=[]
 for a,b in combinations(shortlist,2):
  common=set(a['series'])&set(b['series'])
  if len(common)<12:continue
  for op in ('SUM','A_MINUS_B','B_MINUS_A'):
   if op=='SUM':s={m:a['series'][m]+b['series'][m] for m in common}
   elif op=='A_MINUS_B':s={m:a['series'][m]-b['series'][m] for m in common}
   else:s={m:b['series'][m]-a['series'][m] for m in common}
   sc=best_score(rt,s); pairs.append({'a':a['key'],'b':b['key'],'op':op,**sc})
 pairs.sort(key=lambda x:(x['exact_ratio'],x['exact'],-x['mae']),reverse=True)
 def clean(x):return {k:v for k,v in x.items() if k!='series'}
 out={'schema':'GMFQ_SNB_CHF_CREDIT_DIMENSIONAL_PAIRWISE_V1','source':{'publisher':'Swiss National Bank','cube':'bakredinausbm','url':URL},'runtime_count':len(rt),'parsed_series_count':len(all_series),'eligible_single_series_count':len(singles),'shortlist_count':len(shortlist),'pairwise_test_count':len(pairs),'top_single':[clean(x) for x in singles[:20]],'top_pairwise':pairs[:25],'exact_single_match':next((clean(x) for x in singles if x['exact_ratio']==1.0),None),'exact_pairwise_match':next((x for x in pairs if x['exact_ratio']==1.0),None),'promotion_eligible':False,'runtime_mutated':False,'publication_performed':False}
 print(json.dumps(out,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
