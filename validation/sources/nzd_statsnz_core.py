#!/usr/bin/env python3
from __future__ import annotations
import argparse, html, json, re, urllib.request
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SERIES=ROOT/'live_data/sections/MACRO_SERIES.json'
HEAT=ROOT/'live_data/sections/MACRO_THERMOMETER_DATA.json'
SOURCE='Stats NZ'
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)'}
URLS={
 'inflation':'https://www.stats.govt.nz/information-releases/consumers-price-index-june-2026-quarter/',
 'labour':'https://www.stats.govt.nz/information-releases/labour-market-statistics-june-2026-quarter/',
}
CONFIG={
 'inflation':{'series_id':'NZ_CPI_HEADLINE_YOY','macro_series_id':'NZ_CPI_HEADLINE_YOY_history_value','frequency':'Q','transformation':'reported_yoy_rate','unit':'% YoY'},
 'labour':{'series_id':'NZ_UNEMP_RATE','macro_series_id':'NZ_UNEMP_RATE_history_value','frequency':'Q','transformation':'level','unit':'%'},
}
MONTHS={'march':3,'june':6,'september':9,'december':12}
class T(HTMLParser):
 def __init__(self): super().__init__(); self.p=[]
 def handle_data(self,d):
  if d.strip(): self.p.append(d.strip())
def text(raw):
 p=T();p.feed(raw);return re.sub(r'\s+',' ',html.unescape(' '.join(p.p))).strip()
def load(p): return json.loads(p.read_text())
def fetch(url):
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=45) as r:return r.read().decode('utf-8',errors='replace')
def period(t):
 m=re.search(r'(March|June|September|December)\s+(20\d{2})\s+quarter',t,re.I)
 if not m: raise ValueError('cannot parse Stats NZ quarter')
 return int(m.group(2)),MONTHS[m.group(1).lower()]
def parse_value(dim,t):
 if dim=='inflation':
  patterns=[
   (r'([0-9]+(?:\.[0-9]+)?)\s*percent increase in the CPI in the 12 months',1),
   (r'CPI all groups\s+([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]+)?)',2),
   (r'(?:CPI|consumers price index).*?(?:increased|rose)\s+([0-9]+(?:\.[0-9]+)?)\s*percent\s+in the 12 months',1),
  ]
 else:
  patterns=[
   (r'(?:seasonally adjusted )?unemployment rate (?:was|at|increased to|rose to)\s+([0-9]+(?:\.[0-9]+)?)\s*percent',1),
   (r'Unemployment rate.*?([0-9]+(?:\.[0-9]+)?)\s*%',1),
  ]
 for p,g in patterns:
  m=re.search(p,t,re.I|re.S)
  if m:return float(m.group(g))
 raise ValueError(f'cannot parse Stats NZ {dim} value')
def contract(dim):
 h=load(HEAT)['currencies']['NZD'][dim];c=CONFIG[dim]
 got=(h.get('series_id'),h.get('frequency'),h.get('transformation'));exp=(c['series_id'],c['frequency'],c['transformation'])
 if got!=exp: raise ValueError(f'NZD {dim} frozen contract changed: {got} != {exp}')
 rows=load(SERIES)['NZD'];hits=[r for r in rows if isinstance(r,dict) and r.get('id')==c['macro_series_id']]
 if len(hits)!=1: raise ValueError(f'NZD {dim} canonical target count={len(hits)}')
 return c['macro_series_id']
def build(dim,fixture=None):
 c=CONFIG[dim];target=contract(dim)
 if fixture:
  f=load(fixture);date=f['observation_date'];value=float(f['value']);url=f.get('source_url') or URLS[dim];mode='fixture'
 else:
  url=URLS[dim];t=text(fetch(url));y,m=period(t);date=f'{y:04d}-{m:02d}-01';value=parse_value(dim,t);mode='live'
 cand={'currency':'NZD','dimension':dim,'macro_series_id':target,'observation_date':date,'value':value,'source':SOURCE,'source_url':url,'series_id':c['series_id'],'frequency':c['frequency'],'transformation':c['transformation'],'unit':c['unit']}
 audit={'candidate_only':True,'live_data_written':False,'mode':mode,'source_url':url,'observation_date':date,'value':value}
 return cand,audit
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--dimension',choices=CONFIG,required=True);ap.add_argument('--fixture',type=Path);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--audit-output',type=Path);a=ap.parse_args();c,u=build(a.dimension,a.fixture);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(c,indent=2)+'\n')
 if a.audit_output:a.audit_output.parent.mkdir(parents=True,exist_ok=True);a.audit_output.write_text(json.dumps(u,indent=2)+'\n')
 print(json.dumps({'status':'PASS','candidate':c,'audit':u},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
