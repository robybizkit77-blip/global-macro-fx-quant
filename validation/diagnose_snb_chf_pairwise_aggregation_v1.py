#!/usr/bin/env python3
import csv, io, json, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path

RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
SIGHT_BASE='https://data.snb.ch/api/warehouse/cube/BSTA.SNB.MONA_U.BIL.AKT.FMI.GGU/data/csv/en'
SIGHT_VARIANTS={
 'U_T_T_A40':'KONSOLIDIERUNGSSTUFE(U),INLANDAUSLAND(T),WAEHRUNG(T),BANKENGRUPPE(A40)',
 'U_T_CHF_A40':'KONSOLIDIERUNGSSTUFE(U),INLANDAUSLAND(T),WAEHRUNG(CHF),BANKENGRUPPE(A40)',
 'U_I_T_A40':'KONSOLIDIERUNGSSTUFE(U),INLANDAUSLAND(I),WAEHRUNG(T),BANKENGRUPPE(A40)',
 'U_I_CHF_A40':'KONSOLIDIERUNGSSTUFE(U),INLANDAUSLAND(I),WAEHRUNG(CHF),BANKENGRUPPE(A40)',
}
CREDIT_URL='https://data.snb.ch/api/cube/bakredinausbm/data/csv/en'


def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'GMFQ-validation/1.0','Accept':'text/csv'})
 with urllib.request.urlopen(req,timeout=90) as r:return r.read().decode('utf-8-sig')

def norm(v):
 s=str(v or '').strip()
 for f in ('%Y-%m','%Y-%m-%d','%d.%m.%Y','%d/%m/%Y'):
  try:return datetime.strptime(s,f).strftime('%Y-%m')
  except ValueError:pass
 return None

def num(v):
 s=str(v or '').strip().replace("'",'').replace(' ','')
 if not s:return None
 if s.count(',')==1 and '.' not in s:s=s.replace(',','.')
 try:return float(s)
 except ValueError:return None

def runtime(key):
 ccy,name=key.split('.')
 d=json.loads(RUNTIME.read_text(encoding='utf-8'))[ccy][name]
 return {norm(x):float(v) for x,v in zip(d['dates'],d['values']) if norm(x)}

def parse_single(text):
 try:d=csv.Sniffer().sniff(text[:4096],delimiters=';,\t')
 except csv.Error:d=csv.excel; d.delimiter=';'
 rows=list(csv.reader(io.StringIO(text),dialect=d)); w=max(len(r) for r in rows); rows=[r+['']*(w-len(r)) for r in rows]
 start=next(i for i,r in enumerate(rows) if norm(r[0]))
 cols=[]
 for c in range(1,w):
  n=sum(1 for r in rows[start:] if norm(r[0]) and num(r[c]) is not None)
  if n:cols.append((n,c))
 c=max(cols)[1]; out={}
 for r in rows[start:]:
  m=norm(r[0]); v=num(r[c])
  if m and v is not None:out[m]=v
 return out

def parse_credit(text):
 try:d=csv.Sniffer().sniff(text[:8192],delimiters=';,\t')
 except csv.Error:d=csv.excel; d.delimiter=';'
 rows=list(csv.DictReader(io.StringIO(text),dialect=d)); fields=list(rows[0])
 date=next(f for f in fields if str(f).lower().strip() in {'date','datum','period'})
 value=next(f for f in fields if str(f).lower().strip() in {'value','wert','val'})
 dims=[f for f in fields if f not in {date,value}]
 grouped=defaultdict(dict)
 for r in rows:
  m=norm(r.get(date)); v=num(r.get(value))
  if not m or v is None:continue
  key='|'.join(f'{f}={str(r.get(f) or "").strip()}' for f in dims)
  grouped[key][m]=v
 return dict(grouped)

def score(rt,series):
 common=sorted(set(rt)&set(series)); best=None
 for scale in (1,1e-3,1e3,1e-6,1e6):
  diffs=[rt[m]-series[m]*scale for m in common]
  exact=sum(abs(x)<=1e-9 for x in diffs)
  mae=sum(abs(x) for x in diffs)/len(diffs) if diffs else 1e99
  row={'scale':scale,'overlap':len(common),'exact':exact,'exact_ratio':exact/len(common) if common else 0.0,'mae':mae}
  rank=(row['exact_ratio'],exact,-mae)
  if best is None or rank>best[0]:best=(rank,row)
 return best[1]
def pairwise(rt,series_map):
 out=[]; items=list(series_map.items())
 for (ka,a),(kb,b) in combinations(items,2):
  common=set(a)&set(b)
  if len(common)<12:continue
  for op in ('SUM','A_MINUS_B','B_MINUS_A'):
   if op=='SUM':c={m:a[m]+b[m] for m in common}
   elif op=='A_MINUS_B':c={m:a[m]-b[m] for m in common}
   else:c={m:b[m]-a[m] for m in common}
   s=score(rt,c); out.append({'a':ka,'b':kb,'op':op,**s})
 out.sort(key=lambda x:(x['exact_ratio'],x['exact'],-x['mae']),reverse=True)
 return out[:25]
def main():
 sight={}
 for name,dim in SIGHT_VARIANTS.items():
  url=SIGHT_BASE+'?'+urllib.parse.urlencode({'dimSel':dim,'fromDate':'2016-01','toDate':'2026-12'},safe='(),')
  sight[name]=parse_single(fetch(url))
 credit=parse_credit(fetch(CREDIT_URL))
 rs=pairwise(runtime('CHF.liquidity'),sight)
 rc=pairwise(runtime('CHF.credit'),credit)
 out={'schema':'GMFQ_SNB_CHF_PAIRWISE_AGGREGATION_DIAGNOSTIC_V1','status':'DIAGNOSTIC_ONLY','sight_candidate_count':len(sight),'credit_candidate_count':len(credit),'sight_top':rs,'credit_top':rc,'promotion_eligible':False,'runtime_mutated':False,'publication_performed':False}
 print(json.dumps(out,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
