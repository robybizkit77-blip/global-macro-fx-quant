#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import urllib.request
from datetime import datetime
from pathlib import Path

RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
OUT=Path('validation/liquidity-chf-sight-deposits-diagnostic.json')
CANDIDATES={
 'A40':{
   'series_key':'BSTA@SNB.MONA_U.BIL.AKT.FMI.GGU{U,T,CHF,A40}',
   'url':'https://data.snb.ch/api/warehouse/cube/BSTA.SNB.MONA_U.BIL.AKT.FMI.GGU/data/csv/en?dimSel=KONSOLIDIERUNGSSTUFE(U),INLANDAUSLAND(T),WAEHRUNG(CHF),BANKENGRUPPE(A40)&fromDate=2015-01&toDate=2026-12'
 },
 'A50':{
   'series_key':'BSTA@SNB.MIRE_U.MIR.AAK.GGU{U,T,CHF,A50}',
   'url':'https://data.snb.ch/api/warehouse/cube/BSTA.SNB.MIRE_U.MIR.AAK.GGU/data/csv/en?dimSel=KONSOLIDIERUNGSSTUFE(U),INLANDAUSLAND(T),WAEHRUNG(CHF),BANKENGRUPPE(A50)&fromDate=2015-01&toDate=2026-12'
 }
}

def try_month(v):
 s=str(v).strip()
 for fmt in ('%Y-%m','%Y-%m-%d','%d %b %Y','%d %B %Y'):
  try:return datetime.strptime(s,fmt).strftime('%Y-%m')
  except ValueError:pass
 return None

def month(v):
 m=try_month(v)
 if m is None: raise SystemExit(f'unparseable CHF date {v!r}')
 return m

def runtime():
 d=json.loads(RUNTIME.read_text(encoding='utf-8'))['CHF']['liquidity']
 return d,{month(k):float(v) for k,v in zip(d['dates'],d['values'])}

def fetch_text(url):
 req=urllib.request.Request(url,headers={'User-Agent':'GMFQ-validation/1.0','Accept':'text/csv'})
 with urllib.request.urlopen(req,timeout=60) as r:return r.read().decode('utf-8-sig')

def parse_csv(text):
 sample=text[:8000]
 try: dialect=csv.Sniffer().sniff(sample,delimiters=',;\t')
 except csv.Error: dialect=csv.excel
 raw=list(csv.reader(io.StringIO(text),dialect=dialect))
 header_idx=None
 for i,row in enumerate(raw[:50]):
  cells=[str(x).strip().lower() for x in row]
  if any(x in {'date','datum','period','time','period from','from'} for x in cells) and any(x in {'value','wert','value in chf','obs_value'} for x in cells):
   header_idx=i; break
 if header_idx is None:
  # Fallback: use the first row that is followed by at least one date-looking row.
  for i,row in enumerate(raw[:-1][:50]):
   if any(try_month(x) for x in raw[i+1]):
    header_idx=i; break
 if header_idx is None:
  return [], raw[:10]
 header=raw[header_idx]
 rows=[]
 for vals in raw[header_idx+1:]:
  if not vals: continue
  padded=vals+['']*max(0,len(header)-len(vals))
  rows.append({header[j]:padded[j] for j in range(len(header))})
 return rows, raw[:min(len(raw),10)]

def pick(obj,names):
 lowered={str(k).strip().lower():v for k,v in obj.items()}
 for name in names:
  if name in lowered and lowered[name] not in (None,''):return lowered[name]
 return None

def parse_rows(rows):
 out={}; examples=[]
 for r in rows:
  if len(examples)<3:examples.append(r)
  raw_date=pick(r,('date','datum','period','time','period from','from'))
  raw_value=pick(r,('value','wert','value in chf','obs_value'))
  if raw_date is None:
   raw_date=next((v for v in r.values() if try_month(v)),None)
  if raw_value is None:
   numeric=[]
   for v in r.values():
    if v is None: continue
    s=str(v).strip().replace("'",'').replace(' ','')
    try:numeric.append((v,float(s)))
    except ValueError:pass
   if numeric: raw_value=numeric[-1][0]
  if raw_date is None or raw_value is None:continue
  m=try_month(raw_date)
  if m is None:continue
  try: val=float(str(raw_value).strip().replace("'",'').replace(' ',''))
  except ValueError:continue
  out[m]=val
 return out,examples

def main():
 row,rt=runtime(); results={}
 for name,c in CANDIDATES.items():
  try:
   text=fetch_text(c['url']); rows,raw_head=parse_csv(text); src,examples=parse_rows(rows)
   overlap=sorted(set(rt)&set(src))
   scales={}
   for factor in (1.0,0.001,0.000001,1000.0):
    exact=sum(1 for m in overlap if abs(rt[m]-src[m]*factor)<=1e-6)
    mae=(sum(abs(rt[m]-src[m]*factor) for m in overlap)/len(overlap)) if overlap else None
    scales[str(factor)]={'exact':exact,'overlap':len(overlap),'exact_ratio':exact/len(overlap) if overlap else 0.0,'mae':mae}
   best_factor,best=max(scales.items(),key=lambda kv:(kv[1]['exact_ratio'],-(kv[1]['mae'] if kv[1]['mae'] is not None else 1e99)))
   mism=[]
   factor=float(best_factor)
   for m in overlap:
    scaled=src[m]*factor
    if abs(rt[m]-scaled)>1e-6:mism.append({'date':m,'runtime':rt[m],'source_raw':src[m],'source_scaled':scaled,'diff':rt[m]-scaled})
   results[name]={'series_key':c['series_key'],'url':c['url'],'row_count':len(rows),'parsed_count':len(src),'raw_head':raw_head,'first_examples':examples,'overlap':len(overlap),'best_scale_factor':factor,'best_score':best,'mismatch_count_at_best_scale':len(mism),'first_mismatches':mism[:20],'runtime_last_month':max(rt),'runtime_last_value':rt[max(rt)],'source_raw_on_runtime_last_month':src.get(max(rt)),'source_scaled_on_runtime_last_month':src.get(max(rt))*factor if src.get(max(rt)) is not None else None}
  except Exception as exc:results[name]={'series_key':c['series_key'],'url':c['url'],'error':repr(exc)}
 rep={'schema':'GMFQ_LIQUIDITY_CHF_SIGHT_DEPOSITS_DIAGNOSTIC_V1','status':'DIAGNOSTIC_ONLY_NO_PROMOTION','runtime':{'count':len(rt),'first_month':min(rt),'last_month':max(rt),'last_value':rt[max(rt)],'raw_last_date':row.get('last_date')},'results':results,'runtime_mutated':False,'publication_performed':False,'promotion_performed':False}
 OUT.write_text(json.dumps(rep,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps(rep,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
