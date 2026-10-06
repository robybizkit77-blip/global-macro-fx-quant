#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, io, json, re, unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
import requests
from pypdf import PdfReader

SRC=Path('validation/JPY_WAGES_CPI_SOURCE_PROBE_V1_2026-10-06.json')
ROOT=Path('history/pit_v1')
WOUT=ROOT/'JPY_WAGES_SCHEDULED_CASH_EARNINGS_FIRST_RELEASE_2018_2023_07.csv'
COUT=ROOT/'JPY_CPI_HEADLINE_CORE_FIRST_RELEASE_2018_2023_07.csv'
EVID=Path('validation/JPY_WAGES_CPI_PIT_MATERIALIZATION_V1_2026-10-06.json')
UA={'User-Agent':'GMFQ-PIT-materializer/1.0'}

def norm(s):return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',s or '')).strip()
def download(url):
 r=requests.get(url,headers=UA,timeout=30); r.raise_for_status(); return r.content,r.headers.get('content-type','')
def ptext(b):return norm('\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(b)).pages))
def jp_date(txt):
 t=norm(txt)
 m=re.search(r'(20\d{2})年(\d{1,2})月(\d{1,2})日',t)
 if m:return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
 m=re.search(r'(平成|令和)\s*(\d+)年(\d{1,2})月(\d{1,2})日',t)
 if not m:return None
 era,y,mo,d=m.groups(); gy=(1988+int(y)) if era=='平成' else (2018+int(y))
 return f'{gy:04d}-{int(mo):02d}-{int(d):02d}'
def signed(v,word):
 x=float(v)
 return -x if word in ('減','下落') else x

def parse_wage(txt):
 t=norm(txt)
 # First occurrence is the all-worker result in the press-release key points.
 pats=[
  r'きまって支給する給与は\s*([0-9]+(?:\.[0-9]+)?)%\s*(増|減)',
  r'決まって支給する給与は\s*([0-9]+(?:\.[0-9]+)?)%\s*(増|減)',
  r'きまって支給する給与[^。]{0,80}?([0-9]+(?:\.[0-9]+)?)%\s*(増|減)',
 ]
 for p in pats:
  m=re.search(p,t)
  if m:return signed(m.group(1),m.group(2))
 # Explicit unchanged wording.
 if re.search(r'きまって支給する給与[^。]{0,80}?前年同月と同水準',t):return 0.0
 return None

def yoy_after(segment,label_pattern):
 m=re.search(label_pattern+r'.{0,180}?前年同月比は\s*([0-9]+(?:\.[0-9]+)?)%\s*の?\s*(上昇|下落)',segment)
 if m:return signed(m.group(1),m.group(2))
 m=re.search(label_pattern+r'.{0,180}?前年同月比[^0-9-]{0,20}(-?[0-9]+(?:\.[0-9]+)?)%',segment)
 if m:return float(m.group(1))
 return None
def parse_cpi(txt):
 t=norm(txt)
 # Restrict to the overview before tables where possible.
 seg=t[:5000]
 headline=yoy_after(seg,r'(?:\(1\)\s*)?総合指数')
 core=yoy_after(seg,r'(?:\(2\)\s*)?生鮮食品を除く総合指数')
 return headline,core

def wage_candidates(z):
 ds=z.get('document_candidates',[])
 ordered=[]
 for key in ('houdou','pdf'):
  ordered += [d['url'] for d in ds if key in d['url'].lower() and d['url'].lower().endswith('.pdf')]
 return list(dict.fromkeys(ordered))
def cpi_candidates(z):return [d['url'] for d in z.get('pdf_candidates',[])]

def one_wage(ym,z):
 errs=[]
 for u in wage_candidates(z):
  try:
   b,ct=download(u); txt=ptext(b); val=parse_wage(txt); rd=jp_date(txt)
   if val is None or rd is None:errs.append({'url':u,'error':'parse_value_or_date','value':val,'date':rd});continue
   return {'reference_month':ym,'release_date':rd,'pit_status':'GREEN_FIRST_RELEASE','document_url':u,'document_sha256':hashlib.sha256(b).hexdigest(),'scheduled_cash_earnings_yoy_pct':val,'source_agency':'MHLW','source_document_type':'Monthly Labour Survey preliminary press release'},None
  except Exception as e:errs.append({'url':u,'error':str(e)})
 return None,errs
def one_cpi(ym,z):
 errs=[]
 for u in cpi_candidates(z):
  try:
   b,ct=download(u); txt=ptext(b); h,c=parse_cpi(txt); rd=jp_date(txt)
   if h is None or c is None or rd is None:errs.append({'url':u,'error':'parse_values_or_date','headline':h,'core':c,'date':rd});continue
   return {'reference_month':ym,'release_date':rd,'pit_status':'GREEN_FIRST_RELEASE','document_url':u,'document_sha256':hashlib.sha256(b).hexdigest(),'headline_cpi_yoy_pct':h,'core_cpi_yoy_pct':c,'cpi_base':z.get('base'),'source_agency':'Statistics Bureau of Japan / e-Stat','source_document_type':'National CPI first-release result overview'},None
  except Exception as e:errs.append({'url':u,'error':str(e)})
 return None,errs

def write_csv(path,rows,fields):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
 src=json.loads(SRC.read_text(encoding='utf-8'))
 wm=src['wages_mhlw_preliminary']['months_found']; cm=src['cpi_statistics_bureau_first_release']['months_found']
 wrows=[];crows=[];werr={};cerr={}
 with ThreadPoolExecutor(max_workers=10) as ex:
  fut={ex.submit(one_wage,ym,z):('w',ym) for ym,z in wm.items()}
  fut.update({ex.submit(one_cpi,ym,z):('c',ym) for ym,z in cm.items()})
  for f in as_completed(fut):
   typ,ym=fut[f];row,err=f.result()
   if typ=='w':
    if row:wrows.append(row)
    else:werr[ym]=err
   else:
    if row:crows.append(row)
    else:cerr[ym]=err
 wrows.sort(key=lambda x:x['reference_month']);crows.sort(key=lambda x:x['reference_month'])
 green=(len(wrows)==67 and len(crows)==67 and not werr and not cerr)
 if green:
  write_csv(WOUT,wrows,['reference_month','release_date','pit_status','document_url','document_sha256','scheduled_cash_earnings_yoy_pct','source_agency','source_document_type'])
  write_csv(COUT,crows,['reference_month','release_date','pit_status','document_url','document_sha256','headline_cpi_yoy_pct','core_cpi_yoy_pct','cpi_base','source_agency','source_document_type'])
 else:
  for p in (WOUT,COUT):
   if p.exists():p.unlink()
 ev={'schema':'GMFQ_JPY_WAGES_CPI_PIT_MATERIALIZATION_V1','created_at':'2026-10-06','status':'PASS_67_67_GREEN' if green else 'WITHHELD_INCOMPLETE_PARSE',
     'wages':{'rows':len(wrows),'errors':werr,'output':str(WOUT) if green else None,'first':wrows[:2],'last':wrows[-2:]},
     'cpi':{'rows':len(crows),'errors':cerr,'output':str(COUT) if green else None,'first':crows[:2],'last':crows[-2:]},
     'guardrails':['first-release documents only','document SHA256 per observation','no revised-history fallback','no manual value imputation','no engine/live/OOS changes'],
     'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
 EVID.write_text(json.dumps(ev,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'status':ev['status'],'wages_rows':len(wrows),'cpi_rows':len(crows),'wage_errors':len(werr),'cpi_errors':len(cerr)},ensure_ascii=False))
if __name__=='__main__':main()
