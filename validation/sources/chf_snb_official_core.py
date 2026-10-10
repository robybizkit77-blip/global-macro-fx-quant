#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SERIES=ROOT/'live_data/sections/MACRO_SERIES.json'
HEAT=ROOT/'live_data/sections/MACRO_THERMOMETER_DATA.json'
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)'}
CONFIG={
 'inflation':{
  'series_id':'CH_CPI_HEADLINE_YOY','macro_series_id':'CH_CPI_HEADLINE_YOY_history_value',
  'frequency':'M','transformation':'reported_yoy_rate','unit':'Percent YoY',
  'source':'Swiss National Bank data portal / SFSO','cube':'plkopr',
  'series_label':'Change from the corresponding month of the previous year in %',
 },
 'labour':{
  'series_id':'CH_UNEMP_RATE','macro_series_id':'CH_UNEMP_RATE_history_value',
  'frequency':'M','transformation':'level','unit':'Percent',
  'source':'Swiss National Bank data portal / SECO','cube':'amarbma',
  'series_label':'Jobless rate - Seasonally adjusted',
 },
}
def load(p): return json.loads(p.read_text())
def api_url(cube): return f'https://data.snb.ch/api/cube/{cube}/data/json/en'
def fetch_json(url):
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=45) as r:
  if r.status!=200: raise ValueError(f'SNB API HTTP {r.status}')
  ctype=(r.headers.get('Content-Type') or '').lower()
  if 'json' not in ctype: raise ValueError(f'SNB API unexpected content-type: {ctype}')
  return json.load(r)
def header_label(ts):
 h=ts.get('header')
 if not isinstance(h,list) or len(h)!=1 or not isinstance(h[0],dict): return None
 if h[0].get('dim')!='Overview': return None
 return h[0].get('dimItem')
def select_series(obj,label):
 ts=obj.get('timeseries') if isinstance(obj,dict) else None
 if not isinstance(ts,list): raise ValueError('SNB API missing timeseries list')
 hits=[x for x in ts if isinstance(x,dict) and header_label(x)==label]
 if len(hits)!=1: raise ValueError(f'SNB exact series match count={len(hits)} for {label!r}')
 return hits[0]
def latest_value(ts):
 vals=ts.get('values')
 if not isinstance(vals,list): raise ValueError('SNB series missing values list')
 by_date={}
 for v in vals:
  if not isinstance(v,dict): continue
  d=v.get('date');x=v.get('value')
  if not isinstance(d,str) or not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',d): continue
  if isinstance(x,bool) or not isinstance(x,(int,float)): raise ValueError(f'SNB non-numeric value for {d}: {x!r}')
  x=float(x)
  if d in by_date and abs(by_date[d]-x)>1e-12: raise ValueError(f'SNB conflicting duplicate for {d}')
  by_date[d]=x
 if not by_date: raise ValueError('SNB series has no valid monthly observations')
 d=max(by_date)
 return d,by_date[d]
def contract(dim):
 c=CONFIG[dim];h=load(HEAT)['currencies']['CHF'][dim]
 got=(h.get('series_id'),h.get('frequency'),h.get('transformation'))
 exp=(c['series_id'],c['frequency'],c['transformation'])
 if got!=exp: raise ValueError(f'CHF {dim} frozen contract changed: {got} != {exp}')
 rows=load(SERIES)['CHF'];hits=[r for r in rows if isinstance(r,dict) and r.get('id')==c['macro_series_id']]
 if len(hits)!=1: raise ValueError(f'CHF {dim} canonical target count={len(hits)}')
 return c['macro_series_id']
def build(dim,fixture=None):
 c=CONFIG[dim];target=contract(dim);url=api_url(c['cube'])
 if fixture:
  f=load(fixture);date=f['observation_date'];raw=float(f.get('raw_value',f['value']));value=float(f['value']);mode='fixture';source_url=f.get('source_url') or url
 else:
  ts=select_series(fetch_json(url),c['series_label']);ym,raw=latest_value(ts);date=ym+'-01';mode='live';source_url=url
  value=round(raw,1)
 norm='round_to_1_decimal_official_reported_rate'
 cand={'currency':'CHF','dimension':dim,'macro_series_id':target,'observation_date':date,'value':value,'source':c['source'],'source_url':source_url,'series_id':c['series_id'],'frequency':c['frequency'],'transformation':c['transformation'],'unit':c['unit']}
 audit={'candidate_only':True,'live_data_written':False,'mode':mode,'source_url':source_url,'retrieval_url':url,'upstream_cube':c['cube'],'upstream_series_label':c['series_label'],'observation_date':date,'raw_value':raw,'value':value,'normalization':norm}
 return cand,audit
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--dimension',choices=CONFIG,required=True);ap.add_argument('--fixture',type=Path);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--audit-output',type=Path);a=ap.parse_args()
 c,u=build(a.dimension,a.fixture);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(c,indent=2)+'\n')
 if a.audit_output:a.audit_output.parent.mkdir(parents=True,exist_ok=True);a.audit_output.write_text(json.dumps(u,indent=2)+'\n')
 print(json.dumps({'status':'PASS','candidate':c,'audit':u},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
