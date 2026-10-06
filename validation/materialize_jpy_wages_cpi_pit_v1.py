#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, io, json, re, unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

SRC=Path('validation/JPY_WAGES_CPI_SOURCE_PROBE_V1_2026-10-06.json')
ROOT=Path('history/pit_v1')
WOUT=ROOT/'JPY_WAGES_SCHEDULED_CASH_EARNINGS_FIRST_RELEASE_2018_2023_07.csv'
COUT=ROOT/'JPY_CPI_HEADLINE_CORE_FIRST_RELEASE_2018_2023_07.csv'
EVID=Path('validation/JPY_WAGES_CPI_PIT_MATERIALIZATION_V1_2026-10-06.json')
UA={'User-Agent':'GMFQ-PIT-materializer/1.1'}

def norm(s):return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',s or '')).strip()
def get(url):
 r=requests.get(url,headers=UA,timeout=30); r.raise_for_status();
 if 'text' in r.headers.get('content-type','') or 'html' in r.headers.get('content-type',''):r.encoding=r.apparent_encoding or r.encoding
 return r
def download(url):
 r=get(url); return r.content,r.headers.get('content-type','')
def ptext(b):return norm('\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(b)).pages))
def parse_date_any(txt):
 t=norm(txt)
 pats=[r'(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?',r'(平成|令和)\s*(\d+)年\s*(\d{1,2})月\s*(\d{1,2})日']
 m=re.search(pats[0],t)
 if m:return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
 m=re.search(pats[1],t)
 if not m:return None
 era,y,mo,d=m.groups(); gy=(1988+int(y)) if era=='平成' else (2018+int(y))
 return f'{gy:04d}-{int(mo):02d}-{int(d):02d}'
def after_reference_month(ym,ds,max_days=90):
 if not ds:return False
 y,m=map(int,ym.split('-')); d=date.fromisoformat(ds)
 return d > date(y,m,1) and (d.year>y or d.month>m)
def page_release_date(url,ym):
 r=get(url); soup=BeautifulSoup(r.text,'html.parser'); text=norm(soup.get_text(' ',strip=True))
 # Prefer explicit page publication labels when present.
 candidates=[]
 for pat in [r'(?:公表日|公開(?:更新)?日|掲載日|発表日)[^0-9平成令和]{0,30}((?:20\d{2})[-/.年]\d{1,2}[-/.月]\d{1,2}日?|(?:平成|令和)\s*\d+年\s*\d{1,2}月\s*\d{1,2}日)',
             r'((?:20\d{2})年\d{1,2}月\d{1,2}日|(?:平成|令和)\s*\d+年\s*\d{1,2}月\s*\d{1,2}日)']:
  for m in re.finditer(pat,text):
   raw=m.group(1); ds=parse_date_any(raw)
   if ds and after_reference_month(ym,ds):candidates.append(ds)
  if candidates:break
 return min(candidates) if candidates else None

def estat_release_date(month_url,ym):
 r=get(month_url); soup=BeautifulSoup(r.text,'html.parser')
 # Find the result-overview national row/container and bind the date to that semantic row.
 targets=soup.find_all(string=lambda s:s and '結果の概要' in s and '全国' in s)
 for node in targets:
  for par in [node.parent]+list(node.parents)[:8]:
   text=norm(par.get_text(' ',strip=True))
   # Explicit e-Stat label preferred.
   m=re.search(r'(?:公開(?:更新)?日|公開年月日時分)[^0-9]{0,20}(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})',text)
   if m:
    ds=f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    if after_reference_month(ym,ds):return ds
   # Month rows often display a bare publication date next to the file title.
   for m in re.finditer(r'(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})',text):
    ds=f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    if after_reference_month(ym,ds):return ds
 # Fallback over page text, but only dates AFTER reference month; choose earliest eligible publication date.
 text=norm(soup.get_text(' ',strip=True)); cand=[]
 for m in re.finditer(r'(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})',text):
  ds=f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
  if after_reference_month(ym,ds):cand.append(ds)
 return min(cand) if cand else None

def signed(v,word):
 x=float(v); return -x if word in ('減','下落') else x

def parse_wage(txt):
 t=norm(txt).replace(' ','')
 for p in [r'きまって支給する給与は([0-9]+(?:\.[0-9]+)?)%(増|減)',r'決まって支給する給与は([0-9]+(?:\.[0-9]+)?)%(増|減)',r'きまって支給する給与[^。]{0,80}?([0-9]+(?:\.[0-9]+)?)%(増|減)']:
  m=re.search(p,t)
  if m:return signed(m.group(1),m.group(2))
 if re.search(r'きまって支給する給与[^。]{0,80}?前年同月と同水準',t):return 0.0
 return None

def yoy_after(segment,label):
 m=re.search(label+r'.{0,220}?前年同月比は([0-9]+(?:\.[0-9]+)?)%の?(上昇|下落)',segment)
 if m:return signed(m.group(1),m.group(2))
 m=re.search(label+r'.{0,220}?前年同月比[^0-9-]{0,20}(-?[0-9]+(?:\.[0-9]+)?)%',segment)
 if m:return float(m.group(1))
 # Explicit unchanged wording.
 if re.search(label+r'.{0,220}?前年同月(?:と同水準|比は0(?:\.0)?%)',segment):return 0.0
 return None
def parse_cpi(txt):
 # Remove extraction-induced spaces inside Japanese labels while preserving punctuation/numbers.
 seg=norm(txt[:8000]).replace(' ','')
 headline=yoy_after(seg,r'(?:\(1\))?総合指数')
 core=yoy_after(seg,r'(?:\(2\))?生鮮食品を除く総合指数')
 return headline,core

def wage_candidates(z):
 ds=z.get('document_candidates',[]); ordered=[]
 for key in ('houdou','pdf'):
  ordered += [d['url'] for d in ds if key in d['url'].lower() and d['url'].lower().endswith('.pdf')]
 return list(dict.fromkeys(ordered))
def cpi_candidates(z):return [d['url'] for d in z.get('pdf_candidates',[])]

def one_wage(ym,z):
 errs=[]
 try: rd=page_release_date(z['page_url'],ym)
 except Exception as e: rd=None; errs.append({'url':z.get('page_url'),'error':f'page_date:{e}'})
 for u in wage_candidates(z):
  try:
   b,_=download(u); val=parse_wage(ptext(b))
   if val is None or rd is None:errs.append({'url':u,'error':'parse_value_or_page_date','value':val,'page_date':rd});continue
   return {'reference_month':ym,'release_date':rd,'pit_status':'GREEN_FIRST_RELEASE','document_url':u,'document_sha256':hashlib.sha256(b).hexdigest(),'scheduled_cash_earnings_yoy_pct':val,'source_agency':'MHLW','source_document_type':'Monthly Labour Survey preliminary press release'},None
  except Exception as e:errs.append({'url':u,'error':str(e)})
 return None,errs

def one_cpi(ym,z):
 errs=[]
 try: rd=estat_release_date(z['e_stat_month_url'],ym)
 except Exception as e: rd=None; errs.append({'url':z.get('e_stat_month_url'),'error':f'estat_date:{e}'})
 for u in cpi_candidates(z):
  try:
   b,_=download(u); h,c=parse_cpi(ptext(b))
   if h is None or c is None or rd is None:errs.append({'url':u,'error':'parse_values_or_estat_date','headline':h,'core':c,'estat_date':rd});continue
   return {'reference_month':ym,'release_date':rd,'pit_status':'GREEN_FIRST_RELEASE','document_url':u,'document_sha256':hashlib.sha256(b).hexdigest(),'headline_cpi_yoy_pct':h,'core_cpi_yoy_pct':c,'cpi_base':z.get('base'),'source_agency':'Statistics Bureau of Japan / e-Stat','source_document_type':'National CPI first-release result overview'},None
  except Exception as e:errs.append({'url':u,'error':str(e)})
 return None,errs

def write_csv(path,rows,fields):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def dates_sane(rows):
 return all(after_reference_month(r['reference_month'],r['release_date']) for r in rows)
def main():
 src=json.loads(SRC.read_text(encoding='utf-8'))
 wm=src['wages_mhlw_preliminary']['months_found']; cm=src['cpi_statistics_bureau_first_release']['months_found']
 wrows=[];crows=[];werr={};cerr={}
 with ThreadPoolExecutor(max_workers=10) as ex:
  fut={ex.submit(one_wage,ym,z):('w',ym) for ym,z in wm.items()}; fut.update({ex.submit(one_cpi,ym,z):('c',ym) for ym,z in cm.items()})
  for f in as_completed(fut):
   typ,ym=fut[f]; row,err=f.result()
   if typ=='w':
    if row:wrows.append(row)
    else:werr[ym]=err
   else:
    if row:crows.append(row)
    else:cerr[ym]=err
 wrows.sort(key=lambda x:x['reference_month']);crows.sort(key=lambda x:x['reference_month'])
 sane=dates_sane(wrows) and dates_sane(crows)
 green=(len(wrows)==67 and len(crows)==67 and not werr and not cerr and sane)
 if green:
  write_csv(WOUT,wrows,['reference_month','release_date','pit_status','document_url','document_sha256','scheduled_cash_earnings_yoy_pct','source_agency','source_document_type'])
  write_csv(COUT,crows,['reference_month','release_date','pit_status','document_url','document_sha256','headline_cpi_yoy_pct','core_cpi_yoy_pct','cpi_base','source_agency','source_document_type'])
 else:
  for p in (WOUT,COUT):
   if p.exists():p.unlink()
 ev={'schema':'GMFQ_JPY_WAGES_CPI_PIT_MATERIALIZATION_V1','materializer_revision':'1.1','created_at':'2026-10-06','status':'PASS_67_67_GREEN' if green else 'WITHHELD_INCOMPLETE_PARSE',
     'release_date_policy':{'wages':'MHLW month-specific preliminary result page','cpi':'e-Stat month-specific dataset metadata; never arbitrary date inside PDF','sanity':'release date must fall after reference month'},
     'wages':{'rows':len(wrows),'errors':werr,'output':str(WOUT) if green else None,'first':wrows[:2],'last':wrows[-2:]},
     'cpi':{'rows':len(crows),'errors':cerr,'output':str(COUT) if green else None,'first':crows[:2],'last':crows[-2:]},
     'date_sanity_pass':sane,'guardrails':['first-release documents only','document SHA256 per observation','no revised-history fallback','no manual value imputation','no engine/live/OOS changes'],
     'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
 EVID.write_text(json.dumps(ev,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'status':ev['status'],'wages_rows':len(wrows),'cpi_rows':len(crows),'wage_errors':len(werr),'cpi_errors':len(cerr),'date_sanity':sane},ensure_ascii=False))
if __name__=='__main__':main()
