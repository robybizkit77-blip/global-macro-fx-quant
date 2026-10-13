#!/usr/bin/env python3
from __future__ import annotations
import argparse,io,json,urllib.request,zipfile,xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
URL='https://www.federalreserve.gov/datadownload/Output.aspx?filetype=zip&rel=H8'
SERIES='B1001NCBA'; SCALE=0.001

def day(v):
 s=str(v or '').strip()
 for fmt in ('%Y-%m-%d','%d/%m/%Y'):
  try:return datetime.strptime(s,fmt).strftime('%Y-%m-%d')
  except ValueError:pass
 raise SystemExit(f'invalid USD.credit date {v!r}')

def fetch():
 req=urllib.request.Request(URL,headers={'User-Agent':'GMFQ-validation/1.0','Accept':'application/zip,application/octet-stream,*/*'})
 with urllib.request.urlopen(req,timeout=120) as r: body=r.read()
 if len(body)<1_000_000: raise SystemExit(f'H8 ZIP unexpectedly small: {len(body)}')
 return body

def source(body):
 with zipfile.ZipFile(io.BytesIO(body)) as zf: raw=zf.read('H8_data.xml')
 vals={}; meta=None; active=False
 for event,elem in ET.iterparse(io.BytesIO(raw),events=('start','end')):
  tag=elem.tag.rsplit('}',1)[-1]
  if event=='start' and tag=='Series':
   active=elem.attrib.get('SERIES_NAME')==SERIES
   if active: meta=dict(elem.attrib)
  elif event=='end' and active and tag=='Obs':
   d=elem.attrib.get('TIME_PERIOD'); v=elem.attrib.get('OBS_VALUE')
   if d and v not in (None,''): vals[day(d)]=float(v)*SCALE
   elem.clear()
  elif event=='end' and tag=='Series':
   if active: break
   active=False; elem.clear()
  elif event=='end' and not active: elem.clear()
 if meta is None or not vals: raise SystemExit('Fed H8 target series missing')
 if meta.get('FREQ')!='19' or meta.get('SA')!='SA' or meta.get('ITEM')!='1001': raise SystemExit(f'unexpected H8 metadata {meta}')
 return meta,vals

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--out',required=True); a=ap.parse_args()
 p=json.loads(RUNTIME.read_text()); lane=p['USD']['credit']; dates=[day(x) for x in lane['dates']]; values=[float(x) for x in lane['values']]
 if len(dates)!=len(values) or not dates: raise SystemExit('invalid USD.credit runtime')
 meta,off=source(fetch()); rt=dict(zip(dates,values)); overlap=sorted(set(rt)&set(off))
 if len(overlap)<52: raise SystemExit(f'insufficient H8 overlap: {len(overlap)}')
 exact=sum(abs(rt[d]-off[d])<=1e-6 for d in overlap)
 last=dates[-1]; new=[{'date':d,'value':off[d]} for d in sorted(off) if d>last]
 out={'schema':'GMFQ_LIQUIDITY_USD_BANK_CREDIT_REVISION_AWARE_CANDIDATE_V1','status':'GREEN_SOURCE_CANDIDATE_ONLY','source':{'publisher':'Federal Reserve Board','release':'H.8 Assets and Liabilities of Commercial Banks in the United States','series_id':SERIES,'url':URL,'frequency':'WEEKLY','seasonal_adjustment':'SA','official_value_unit':'USD million','runtime_value_unit':'USD billion','raw_to_runtime_scale':SCALE},'runtime':{'lane':'USD.credit','count':len(dates),'last_date':last,'last_value':values[-1]},'proof':{'overlap_count':len(overlap),'current_vintage_exact_match_count':exact,'current_vintage_mismatch_count':len(overlap)-exact,'revision_aware_append_only':True,'historical_runtime_values_frozen':True,'new_observation_transform':'SCALE_0.001','series_metadata':{'FREQ':meta.get('FREQ'),'SA':meta.get('SA'),'ITEM':meta.get('ITEM')}},'latest_date':max(off),'latest_value':off[max(off)],'candidate_update_available':bool(new),'new_observations':new,'runtime_mutated':False,'publication_performed':False}
 Path(a.out).write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2))
if __name__=='__main__': main()
