#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,html,io,json,re,urllib.request,zipfile
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
SERIES_PATH=ROOT/'live_data/sections/MACRO_SERIES.json'
HEATMAP_PATH=ROOT/'live_data/sections/MACRO_THERMOMETER_DATA.json'
SOURCE='Statistics Canada'
STATIC_CSV='https://www150.statcan.gc.ca/n1/en/tbl/csv'
PRICE_PORTAL='https://www.statcan.gc.ca/en/subjects-start/prices_and_price_indexes'
HTTP_HEADERS={'User-Agent':'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)','Accept':'text/html,application/zip,application/octet-stream,*/*'}
CONFIG={
 'inflation':{'pid':'1810000402','download_pid':'18100004','unit':'% YoY','transformation':'reported_yoy_rate'},
 'labour':{'pid':'14100287','download_pid':'14100287','unit':'%','transformation':'level'},
}
MONTHS={m:i for i,m in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}

def load_json(p:Path)->Any:return json.loads(p.read_text(encoding='utf-8'))
def norm(s:Any)->str:return str(s or '').strip().lower()

def heat_contract(dim:str):
 h=load_json(HEATMAP_PATH)['currencies']['CAD'][dim]
 if h.get('frequency')!='M':raise ValueError(f'CAD {dim} frequency changed: {h.get("frequency")!r}')
 exp=CONFIG[dim]['transformation']
 if h.get('transformation')!=exp:raise ValueError(f'CAD {dim} transformation changed: {h.get("transformation")!r}; expected {exp!r}')
 return str(h.get('series_id')),str(h.get('frequency')),str(h.get('transformation'))

def resolve_macro_series_id(dim:str,heat_id:str)->str:
 rows=load_json(SERIES_PATH)['CAD'];by={str(r.get('id')):r for r in rows if isinstance(r,dict) and r.get('id') is not None}
 explicit={'CA_CPI_HEADLINE_YOY':'CA_CPI_HEADLINE_YOY_history_value','CA_UNEMP_RATE':'CA_UNEMP_RATE_history_value'}
 if heat_id in explicit:
  target=explicit[heat_id]
  if target not in by:raise ValueError(f'CAD canonical target missing for {heat_id}: {target}')
  return target
 direct=[heat_id,f'CA_{heat_id}_history_value',f'CAD_{heat_id}_history_value',f'CA_{heat_id}_history_{heat_id}'];hits=[x for x in dict.fromkeys(direct) if x in by]
 if len(hits)==1:return hits[0]
 if len(hits)>1:raise ValueError(f'ambiguous CAD {dim} canonical IDs: {hits}')
 raise ValueError(f'cannot resolve unique CAD {dim} MACRO_SERIES row; heatmap series_id={heat_id!r}')

def http_get_text(url:str)->str:
 req=urllib.request.Request(url,headers=HTTP_HEADERS)
 with urllib.request.urlopen(req,timeout=90) as r:return r.read().decode('utf-8','replace')

def download_csv(download_pid:str)->str:
 url=f'{STATIC_CSV}/{download_pid}-eng.zip';req=urllib.request.Request(url,headers=HTTP_HEADERS)
 with urllib.request.urlopen(req,timeout=90) as r:data=r.read()
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  names=[n for n in z.namelist() if n.lower().endswith('.csv') and 'meta' not in n.lower()]
  if not names:raise ValueError('StatCan ZIP contains no data CSV')
  return z.read(names[0]).decode('utf-8-sig')

def rows_from_text(text:str):return list(csv.DictReader(io.StringIO(text)))

def extract_fixture_inflation(rows):
 out={}
 for r in rows:
  if norm(r.get('GEO') or r.get('Geography'))!='canada':continue
  joined=' | '.join(norm(v) for v in r.values())
  if 'all-items' not in joined and 'all items' not in joined:continue
  if not any(token in joined for token in ('12-month','12 month','year-over-year','year over year')):continue
  d=r.get('REF_DATE') or r.get('Reference period');v=r.get('VALUE') or r.get('Value')
  if not d or v in (None,''):continue
  try:out[str(d)[:7]+'-01']=float(v)
  except:pass
 dates=sorted(out)
 if len(dates)<2:raise ValueError(f'need >=2 fixture CPI YoY observations; got {len(dates)}')
 return [(d,out[d]) for d in dates]

def extract_labour(rows):
 out={}
 for r in rows:
  if norm(r.get('GEO') or r.get('Geography'))!='canada':continue
  char=norm(r.get('Labour force characteristics'));sex=norm(r.get('Gender') or r.get('Sex'));age=norm(r.get('Age group'));stat=norm(r.get('Statistics'))
  if 'unemployment rate' not in char:continue
  if sex and 'both sexes' not in sex and 'total' not in sex:continue
  if age and '15 years and over' not in age:continue
  if stat and stat!='estimate':continue
  d=r.get('REF_DATE');v=r.get('VALUE')
  if not d or v in (None,''):continue
  try:out[str(d)[:7]+'-01']=float(v)
  except:pass
 dates=sorted(out)
 if len(dates)<2:raise ValueError(f'need >=2 monthly unemployment observations; got {len(dates)}')
 return [(d,out[d]) for d in dates]

def extract_live_headline_cpi(page_html:str)->tuple[str,float]:
 text=html.unescape(re.sub(r'<[^>]+>',' ',page_html));text=re.sub(r'\s+',' ',text)
 pattern=r'Consumer Price Index\s*-\s*Canada\s*\((January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\).*?(-?\d+(?:\.\d+)?)\s*%.*?\(12-month change\)'
 m=re.search(pattern,text,re.I)
 if not m:raise ValueError('could not parse official Statistics Canada headline CPI key indicator')
 month_name=m.group(1).capitalize();year=int(m.group(2));value=float(m.group(3));month=MONTHS[month_name]
 return f'{year:04d}-{month:02d}-01',value

def make_candidate(dim:str,latest:str,lv:float,source_url:str,audit_extra:dict[str,Any],prior:str|None=None,pv:float|None=None):
 hid,freq,tr=heat_contract(dim);mid=resolve_macro_series_id(dim,hid);cfg=CONFIG[dim]
 c={'currency':'CAD','dimension':dim,'macro_series_id':mid,'observation_date':latest,'value':lv,'source':SOURCE,'source_url':source_url,'series_id':hid,'frequency':freq,'transformation':tr,'unit':cfg['unit']}
 a={'product_id':cfg['pid'],'latest_period':latest,'latest_value':lv,'prior_period':prior,'prior_value':pv,'delta':(lv-pv if pv is not None else None),'candidate_only':True,'live_data_written':False,**audit_extra}
 return c,a

def build_fixture_candidate(dim:str,text:str):
 rows=rows_from_text(text);obs=extract_fixture_inflation(rows) if dim=='inflation' else extract_labour(rows);latest,lv=obs[-1];prior,pv=obs[-2];cfg=CONFIG[dim]
 return make_candidate(dim,latest,lv,f'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={cfg["pid"]}',{'transport':'deterministic_fixture'},prior,pv)

def build_live_candidate(dim:str):
 cfg=CONFIG[dim]
 if dim=='inflation':
  page=http_get_text(PRICE_PORTAL);latest,lv=extract_live_headline_cpi(page)
  return make_candidate(dim,latest,lv,PRICE_PORTAL,{'transport':'official_key_indicator_html','reported_measure':'12-month change'})
 text=download_csv(cfg['download_pid']);obs=extract_labour(rows_from_text(text));latest,lv=obs[-1];prior,pv=obs[-2]
 return make_candidate(dim,latest,lv,f'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={cfg["pid"]}',{'transport':'official_full_table_csv','download_pid':cfg['download_pid']},prior,pv)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--dimension',choices=CONFIG,required=True);ap.add_argument('--fixture',type=Path);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--audit-output',type=Path);args=ap.parse_args()
 if args.fixture:c,a=build_fixture_candidate(args.dimension,args.fixture.read_text(encoding='utf-8'));a['mode']='fixture'
 else:c,a=build_live_candidate(args.dimension);a['mode']='live'
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(c,indent=2)+'\n')
 if args.audit_output:args.audit_output.write_text(json.dumps(a,indent=2)+'\n')
 print(json.dumps({'status':'PASS','candidate':c,'audit':a},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
