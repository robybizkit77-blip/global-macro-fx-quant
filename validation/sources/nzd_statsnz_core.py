#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, html, io, json, re, urllib.request, zipfile
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SERIES=ROOT/'live_data/sections/MACRO_SERIES.json'
HEAT=ROOT/'live_data/sections/MACRO_THERMOMETER_DATA.json'
SOURCE='Stats NZ'
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)'}
SOURCE_URLS={
 'inflation':'https://www.stats.govt.nz/news/annual-inflation-at-4-1-percent-in-june-2026/',
 'labour':'https://www.stats.govt.nz/information-releases/labour-market-statistics-june-2026-quarter/',
}
RETRIEVAL_URLS={
 'inflation':SOURCE_URLS['inflation'],
 'labour':'https://www.stats.govt.nz/assets/Uploads/Labour-market-statistics/Labour-market-statistics-June-2026-quarter/Download-data/labour-market-statistics-june-2026-quarter.zip',
}
LABOUR_ZIP_MEMBER='labour-market-statistics-june-2026/lms-jun26qtr-tables.csv'
LABOUR_SERIES_ID='HLFQ.S1F3S'
CONFIG={
 'inflation':{'series_id':'NZ_CPI_HEADLINE_YOY','macro_series_id':'NZ_CPI_HEADLINE_YOY_history_value','frequency':'Q','transformation':'reported_yoy_rate','unit':'% YoY'},
 'labour':{'series_id':'NZ_UNEMP_RATE','macro_series_id':'NZ_UNEMP_RATE_history_value','frequency':'Q','transformation':'level','unit':'%'},
}
MONTHS={'march':3,'june':6,'september':9,'december':12}
class T(HTMLParser):
 def __init__(self): super().__init__(); self.p=[]
 def handle_data(self,d):
  if d.strip(): self.p.append(d.strip())
def html_text(raw):
 p=T();p.feed(raw);return re.sub(r'\s+',' ',html.unescape(' '.join(p.p))).strip()
def load(p): return json.loads(p.read_text())
def fetch_bytes(url):
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=45) as r:return r.read()
def fetch_html_text(url): return html_text(fetch_bytes(url).decode('utf-8',errors='replace'))
def period(t):
 m=re.search(r'(March|June|September|December)\s+(20\d{2})\s+quarter',t,re.I)
 if not m: m=re.search(r'(March|June|September|December)\s+(20\d{2})',t,re.I)
 if not m: raise ValueError('cannot parse Stats NZ quarter')
 return int(m.group(2)),MONTHS[m.group(1).lower()]
def parse_inflation_value(t):
 patterns=[r'Annual inflation at\s+([0-9]+(?:\.[0-9]+)?)\s+percent',r'CPI\)?\s+increased\s+([0-9]+(?:\.[0-9]+)?)\s+percent in the 12 months',r'([0-9]+(?:\.[0-9]+)?)\s+percent increase follows']
 hits=[]
 for p in patterns: hits.extend(float(m.group(1)) for m in re.finditer(p,t,re.I|re.S))
 uniq=sorted(set(hits))
 if len(uniq)==1:return uniq[0]
 if not uniq:raise ValueError('cannot parse Stats NZ inflation value')
 raise ValueError(f'ambiguous Stats NZ inflation values: {uniq}')
def fetch_labour_csv_value(url):
 raw=fetch_bytes(url)
 if not raw.startswith(b'PK'):
  raise ValueError('Stats NZ labour retrieval did not return ZIP')
 z=zipfile.ZipFile(io.BytesIO(raw))
 if LABOUR_ZIP_MEMBER not in z.namelist():
  raise ValueError(f'expected Stats NZ labour member missing: {LABOUR_ZIP_MEMBER}')
 text=z.read(LABOUR_ZIP_MEMBER).decode('utf-8-sig')
 rows=[]
 for row in csv.reader(io.StringIO(text)):
  if not row or row[0].strip()!=LABOUR_SERIES_ID:
   continue
  if len(row)<10:
   raise ValueError(f'malformed Stats NZ labour row: {row!r}')
  period_code=row[1].strip(); raw_value=row[2].strip(); unit=row[4].strip(); survey=row[6].strip(); table=row[7].strip(); measure=row[8].strip(); sex=row[9].strip()
  if unit!='Percent' or 'Household Labour Force Survey' not in survey or table!='Labour Force Status by Sex: Seasonally Adjusted' or measure!='Unemployment Rate' or sex!='Total Both Sexes':
   raise ValueError(f'unexpected Stats NZ labour metadata for {period_code}: {row[:10]!r}')
  m=re.fullmatch(r'(20\d{2})\.(03|06|09|12)',period_code)
  if not m:
   continue
  rows.append((int(m.group(1)),int(m.group(2)),float(raw_value),period_code))
 if not rows:
  raise ValueError(f'{LABOUR_SERIES_ID} not found in official Stats NZ labour ZIP')
 by_period={}
 for y,m,v,p in rows:
  if (y,m) in by_period and abs(by_period[(y,m)]-v)>1e-12:
   raise ValueError(f'conflicting Stats NZ labour values for {p}')
  by_period[(y,m)]=v
 y,m=max(by_period)
 return y,m,by_period[(y,m)]
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
  f=load(fixture);date=f['observation_date'];value=float(f['value']);source_url=f.get('source_url') or SOURCE_URLS[dim];retrieval_url=source_url;mode='fixture';upstream_series_id=LABOUR_SERIES_ID if dim=='labour' else None
 else:
  source_url=SOURCE_URLS[dim];retrieval_url=RETRIEVAL_URLS[dim];mode='live';upstream_series_id=None
  if dim=='labour':
   y,m,value=fetch_labour_csv_value(retrieval_url);upstream_series_id=LABOUR_SERIES_ID
  else:
   t=fetch_html_text(retrieval_url);y,m=period(t);value=parse_inflation_value(t)
  date=f'{y:04d}-{m:02d}-01'
 cand={'currency':'NZD','dimension':dim,'macro_series_id':target,'observation_date':date,'value':value,'source':SOURCE,'source_url':source_url,'series_id':c['series_id'],'frequency':c['frequency'],'transformation':c['transformation'],'unit':c['unit']}
 audit={'candidate_only':True,'live_data_written':False,'mode':mode,'source_url':source_url,'retrieval_url':retrieval_url,'observation_date':date,'value':value,'upstream_series_id':upstream_series_id}
 return cand,audit
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--dimension',choices=CONFIG,required=True);ap.add_argument('--fixture',type=Path);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--audit-output',type=Path);a=ap.parse_args();c,u=build(a.dimension,a.fixture);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(c,indent=2)+'\n')
 if a.audit_output:a.audit_output.parent.mkdir(parents=True,exist_ok=True);a.audit_output.write_text(json.dumps(u,indent=2)+'\n')
 print(json.dumps({'status':'PASS','candidate':c,'audit':u},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())