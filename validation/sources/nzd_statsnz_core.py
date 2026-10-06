#!/usr/bin/env python3
from __future__ import annotations
import argparse, html, io, json, re, urllib.request
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
 'labour':'https://www.stats.govt.nz/assets/Uploads/Labour-market-statistics/Labour-market-statistics-June-2026-quarter/Download-data/labour-market-statistics-june-2026-quarter-summary-diagrams.pdf',
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
def html_text(raw):
 p=T();p.feed(raw);return re.sub(r'\s+',' ',html.unescape(' '.join(p.p))).strip()
def load(p): return json.loads(p.read_text())
def fetch_bytes(url):
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=45) as r:return r.read()
def fetch_html_text(url): return html_text(fetch_bytes(url).decode('utf-8',errors='replace'))
def fetch_pdf_text(url):
 try:
  from pypdf import PdfReader
 except ImportError as exc:
  raise RuntimeError('pypdf is required for Stats NZ labour PDF retrieval') from exc
 raw=fetch_bytes(url)
 if not raw.startswith(b'%PDF-'): raise ValueError('Stats NZ labour retrieval did not return a PDF')
 reader=PdfReader(io.BytesIO(raw))
 text=' '.join((page.extract_text() or '') for page in reader.pages)
 text=re.sub(r'\s+',' ',text).strip()
 if not text: raise ValueError('Stats NZ labour PDF has no extractable text')
 return text
def period(t):
 m=re.search(r'(March|June|September|December)\s+(20\d{2})\s+quarter',t,re.I)
 if not m: m=re.search(r'(March|June|September|December)\s+(20\d{2})',t,re.I)
 if not m: raise ValueError('cannot parse Stats NZ quarter')
 return int(m.group(2)),MONTHS[m.group(1).lower()]
def parse_value(dim,t):
 if dim=='inflation':
  patterns=[r'Annual inflation at\s+([0-9]+(?:\.[0-9]+)?)\s+percent',r'CPI\)?\s+increased\s+([0-9]+(?:\.[0-9]+)?)\s+percent in the 12 months',r'([0-9]+(?:\.[0-9]+)?)\s+percent increase follows']
 else:
  patterns=[r'Unemployment rate\s*[:]?\s*([0-9]+(?:\.[0-9]+)?)\s*%',r'Unemployment rate\s*[:]?\s*([0-9]+(?:\.[0-9]+)?)\s+percent',r'The unemployment rate was\s+([0-9]+(?:\.[0-9]+)?)\s+percent',r'seasonally adjusted unemployment rate was\s+([0-9]+(?:\.[0-9]+)?)\s+percent']
 hits=[]
 for p in patterns: hits.extend(float(m.group(1)) for m in re.finditer(p,t,re.I|re.S))
 uniq=sorted(set(hits))
 if len(uniq)==1:return uniq[0]
 if not uniq:raise ValueError(f'cannot parse Stats NZ {dim} value')
 raise ValueError(f'ambiguous Stats NZ {dim} values: {uniq}')
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
  f=load(fixture);date=f['observation_date'];value=float(f['value']);source_url=f.get('source_url') or SOURCE_URLS[dim];retrieval_url=source_url;mode='fixture'
 else:
  source_url=SOURCE_URLS[dim];retrieval_url=RETRIEVAL_URLS[dim]
  t=fetch_pdf_text(retrieval_url) if dim=='labour' else fetch_html_text(retrieval_url)
  y,m=period(t);date=f'{y:04d}-{m:02d}-01';value=parse_value(dim,t);mode='live'
 cand={'currency':'NZD','dimension':dim,'macro_series_id':target,'observation_date':date,'value':value,'source':SOURCE,'source_url':source_url,'series_id':c['series_id'],'frequency':c['frequency'],'transformation':c['transformation'],'unit':c['unit']}
 audit={'candidate_only':True,'live_data_written':False,'mode':mode,'source_url':source_url,'retrieval_url':retrieval_url,'observation_date':date,'value':value}
 return cand,audit
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--dimension',choices=CONFIG,required=True);ap.add_argument('--fixture',type=Path);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--audit-output',type=Path);a=ap.parse_args();c,u=build(a.dimension,a.fixture);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(c,indent=2)+'\n')
 if a.audit_output:a.audit_output.parent.mkdir(parents=True,exist_ok=True);a.audit_output.write_text(json.dumps(u,indent=2)+'\n')
 print(json.dumps({'status':'PASS','candidate':c,'audit':u},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())