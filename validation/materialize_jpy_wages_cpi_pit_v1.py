#!/usr/bin/env python3
from __future__ import annotations
import calendar,csv,hashlib,io,json,re,unicodedata
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date,timedelta
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

SRC=Path('validation/JPY_WAGES_CPI_SOURCE_PROBE_V1_2026-10-06.json'); ROOT=Path('history/pit_v1')
WOUT=ROOT/'JPY_WAGES_SCHEDULED_CASH_EARNINGS_FIRST_RELEASE_2018_2023_07.csv'; COUT=ROOT/'JPY_CPI_HEADLINE_CORE_FIRST_RELEASE_2018_2023_07.csv'
EVID=Path('validation/JPY_WAGES_CPI_PIT_MATERIALIZATION_V1_2026-10-06.json'); UA={'User-Agent':'GMFQ-PIT-materializer/1.3'}

def norm(s):return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',s or '')).strip()
def get(url):
 r=requests.get(url,headers=UA,timeout=30);r.raise_for_status()
 if 'html' in r.headers.get('content-type','') or 'text' in r.headers.get('content-type',''):r.encoding=r.apparent_encoding or r.encoding
 return r
def download(url):r=get(url);return r.content,r.headers.get('content-type','')
def ptext(b):return norm('\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(b)).pages))
def parse_date_any(txt):
 t=norm(txt);m=re.search(r'(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?',t)
 if m:return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
 m=re.search(r'(平成|令和)\s*(\d+)年\s*(\d{1,2})月\s*(\d{1,2})日',t)
 if not m:return None
 era,y,mo,d=m.groups();gy=1988+int(y) if era=='平成' else 2018+int(y);return f'{gy:04d}-{int(mo):02d}-{int(d):02d}'
def month_end(ym):
 y,m=map(int,ym.split('-'));return date(y,m,calendar.monthrange(y,m)[1])
def sane_date(ym,ds,max_days=95):
 if not ds:return False
 d=date.fromisoformat(ds);e=month_end(ym);return e<d<=e+timedelta(days=max_days)
def page_release_date(url,ym):
 soup=BeautifulSoup(get(url).text,'html.parser');text=norm(soup.get_text(' ',strip=True));cand=[]
 pats=[r'(?:公表日|公開(?:更新)?日|掲載日|発表日)[^0-9平成令和]{0,30}((?:20\d{2})[-/.年]\d{1,2}[-/.月]\d{1,2}日?|(?:平成|令和)\s*\d+年\s*\d{1,2}月\s*\d{1,2}日)',r'((?:20\d{2})年\d{1,2}月\d{1,2}日|(?:平成|令和)\s*\d+年\s*\d{1,2}月\s*\d{1,2}日)']
 for pat in pats:
  for m in re.finditer(pat,text):
   ds=parse_date_any(m.group(1))
   if sane_date(ym,ds):cand.append(ds)
  if cand:break
 return min(cand) if cand else None
def previous_month(ym):
 y,m=map(int,ym.split('-'));m-=1
 if m==0:y-=1;m=12
 return f'{y:04d}-{m:02d}'
def resolve_md_after_month(ym,mo,day):
 e=month_end(ym);c=[]
 for y in (e.year,e.year+1):
  try:d=date(y,int(mo),int(day))
  except ValueError:continue
  if e<d<=e+timedelta(days=95):c.append(d)
 return min(c).isoformat() if c else None
def announced_wage_date_from_prior(ym,all_months):
 prev=previous_month(ym);z=all_months.get(prev)
 if not z:return None
 docs=z.get('document_candidates',[]);urls=[]
 for key in ('pdf','houdou'):urls += [d['url'] for d in docs if key in d['url'].lower() and d['url'].lower().endswith('.pdf')]
 target_m=int(ym.split('-')[1])
 for u in dict.fromkeys(urls):
  try:
   txt=norm(ptext(download(u)[0])).replace(' ','');p=txt.find(f'{target_m}月分')
   if p<0:continue
   seg=txt[p:p+220];m=re.search(r'(\d{1,2})月(\d{1,2})日',seg)
   if m:
    ds=resolve_md_after_month(ym,m.group(1),m.group(2))
    if ds:return ds
  except Exception:pass
 return None
def estat_release_date(month_url,ym):
 soup=BeautifulSoup(get(month_url).text,'html.parser');targets=soup.find_all(string=lambda s:s and '結果の概要' in s and '全国' in s)
 for node in targets:
  for par in [node.parent]+list(node.parents)[:8]:
   text=norm(par.get_text(' ',strip=True))
   for pat in [r'(?:公開(?:更新)?日|公開年月日時分)[^0-9]{0,20}(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})',r'(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})']:
    for m in re.finditer(pat,text):
     ds=f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
     if sane_date(ym,ds,60):return ds
 text=norm(soup.get_text(' ',strip=True));cand=[]
 for m in re.finditer(r'(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})',text):
  ds=f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
  if sane_date(ym,ds,60):cand.append(ds)
 return min(cand) if cand else None
def signed(v,w):return -float(v) if w in ('減','下落') else float(v)
def parse_wage(txt):
 t=norm(txt).replace(' ','')
 for p in [r'きまって支給する給与は([0-9]+(?:\.[0-9]+)?)%(増|減)',r'決まって支給する給与は([0-9]+(?:\.[0-9]+)?)%(増|減)',r'きまって支給する給与[^。]{0,80}?([0-9]+(?:\.[0-9]+)?)%(増|減)']:
  m=re.search(p,t)
  if m:return signed(m.group(1),m.group(2))
 if re.search(r'(?:きまって|決まって)支給する給与[^。]{0,100}?前年同月と同水準',t):return 0.0
 return None

def semantic_cpi_value(seg,label,current_month):
 # Highest-confidence form used in the official narrative: previous month X% -> current month Y%.
 arrow_patterns=[
  label+r'.{0,220}?前年同月比.{0,180}?\([^)]*?→'+str(current_month)+r'月(-?[0-9]+(?:\.[0-9]+)?)%\)',
  label+r'.{0,260}?前年同月比.{0,220}?'+str(current_month)+r'月(-?[0-9]+(?:\.[0-9]+)?)%'
 ]
 for p in arrow_patterns:
  m=re.search(p,seg)
  if m:return float(m.group(1)),'EXPLICIT_CURRENT_MONTH_COMPARISON'
 # Direct prose form only when the value immediately follows 前年同月比, avoiding phrases about widening/narrowing.
 for p in [
  label+r'.{0,90}?前年同月比(?:は|が|、)?(-?[0-9]+(?:\.[0-9]+)?)%(上昇|下落)?',
  label+r'.{0,90}?前年同月比(?:は|が|、)?(-?[0-9]+(?:\.[0-9]+)?)%'
 ]:
  m=re.search(p,seg)
  if m:
   between=m.group(0)
   if '上昇幅' in between or '下落幅' in between or 'ポイント' in between:continue
   val=float(m.group(1)); direction=m.group(2) if m.lastindex and m.lastindex>=2 else None
   if direction=='下落':val=-abs(val)
   return val,'DIRECT_YOY_PROSE'
 return None,None

def parse_cpi(txt,ym):
 seg=norm(txt[:18000]).replace(' ','');cm=int(ym.split('-')[1])
 headline,hm=semantic_cpi_value(seg,r'(?:\(1\))?総合(?:指数)?',cm)
 core,cmeth=semantic_cpi_value(seg,r'(?:\(2\))?生鮮食品を除く総合(?:指数)?',cm)
 return headline,core,hm,cmeth

def wage_candidates(z):
 ds=z.get('document_candidates',[]);ordered=[]
 for key in ('houdou','pdf'):ordered += [d['url'] for d in ds if key in d['url'].lower() and d['url'].lower().endswith('.pdf')]
 return list(dict.fromkeys(ordered))
def cpi_candidates(z):return [d['url'] for d in z.get('pdf_candidates',[])]
def one_wage(ym,z,all_months):
 errs=[]
 try:rd=page_release_date(z['page_url'],ym)
 except Exception as e:rd=None;errs.append({'url':z.get('page_url'),'error':f'page_date:{e}'})
 date_source='MHLW month-specific preliminary page'
 if not rd:
  rd=announced_wage_date_from_prior(ym,all_months);date_source='MHLW prior-month official future-publication schedule'
 for u in wage_candidates(z):
  try:
   b,_=download(u);val=parse_wage(ptext(b))
   if val is None or not sane_date(ym,rd):errs.append({'url':u,'error':'parse_value_or_official_date','value':val,'date':rd});continue
   return {'reference_month':ym,'release_date':rd,'pit_status':'GREEN_FIRST_RELEASE','document_url':u,'document_sha256':hashlib.sha256(b).hexdigest(),'scheduled_cash_earnings_yoy_pct':val,'source_agency':'MHLW','source_document_type':'Monthly Labour Survey preliminary press release','release_date_source':date_source},None
  except Exception as e:errs.append({'url':u,'error':str(e)})
 return None,errs
def one_cpi(ym,z):
 errs=[]
 try:rd=estat_release_date(z['e_stat_month_url'],ym)
 except Exception as e:rd=None;errs.append({'url':z.get('e_stat_month_url'),'error':f'estat_date:{e}'})
 for u in cpi_candidates(z):
  try:
   b,_=download(u);h,c,hm,cm=parse_cpi(ptext(b),ym)
   if h is None or c is None or not sane_date(ym,rd,60):errs.append({'url':u,'error':'parse_values_or_estat_date','headline':h,'core':c,'headline_method':hm,'core_method':cm,'estat_date':rd});continue
   return {'reference_month':ym,'release_date':rd,'pit_status':'GREEN_FIRST_RELEASE','document_url':u,'document_sha256':hashlib.sha256(b).hexdigest(),'headline_cpi_yoy_pct':h,'core_cpi_yoy_pct':c,'cpi_base':z.get('base'),'source_agency':'Statistics Bureau of Japan / e-Stat','source_document_type':'National CPI first-release result overview','release_date_source':'e-Stat month-specific dataset metadata','headline_extraction_method':hm,'core_extraction_method':cm},None
  except Exception as e:errs.append({'url':u,'error':str(e)})
 return None,errs
def write_csv(path,rows,fields):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
 src=json.loads(SRC.read_text(encoding='utf-8'));wm=src['wages_mhlw_preliminary']['months_found'];cm=src['cpi_statistics_bureau_first_release']['months_found'];wrows=[];crows=[];werr={};cerr={}
 with ThreadPoolExecutor(max_workers=10) as ex:
  fut={ex.submit(one_wage,ym,z,wm):('w',ym) for ym,z in wm.items()};fut.update({ex.submit(one_cpi,ym,z):('c',ym) for ym,z in cm.items()})
  for f in as_completed(fut):
   typ,ym=fut[f];row,err=f.result()
   if typ=='w':(wrows.append(row) if row else werr.__setitem__(ym,err))
   else:(crows.append(row) if row else cerr.__setitem__(ym,err))
 wrows.sort(key=lambda x:x['reference_month']);crows.sort(key=lambda x:x['reference_month']);sane=all(sane_date(r['reference_month'],r['release_date']) for r in wrows) and all(sane_date(r['reference_month'],r['release_date'],60) for r in crows)
 green=len(wrows)==67 and len(crows)==67 and not werr and not cerr and sane
 if green:
  write_csv(WOUT,wrows,['reference_month','release_date','pit_status','document_url','document_sha256','scheduled_cash_earnings_yoy_pct','source_agency','source_document_type','release_date_source'])
  write_csv(COUT,crows,['reference_month','release_date','pit_status','document_url','document_sha256','headline_cpi_yoy_pct','core_cpi_yoy_pct','cpi_base','source_agency','source_document_type','release_date_source','headline_extraction_method','core_extraction_method'])
 else:
  for p in (WOUT,COUT):
   if p.exists():p.unlink()
 methods={}
 for r in crows:
  k=f"{r['headline_extraction_method']}|{r['core_extraction_method']}";methods[k]=methods.get(k,0)+1
 ev={'schema':'GMFQ_JPY_WAGES_CPI_PIT_MATERIALIZATION_V1','materializer_revision':'1.3','created_at':'2026-10-06','status':'PASS_67_67_GREEN' if green else 'WITHHELD_INCOMPLETE_PARSE','release_date_policy':{'wages':'month page; official prior-month future-publication schedule as deterministic fallback','cpi':'e-Stat month-specific dataset metadata','sanity':'strictly after reference month'},'cpi_extraction_policy':'Prefer explicit current-month comparison prose (prev X -> current Y); direct YoY prose only if no widening/narrowing/points language intervenes. No broad table-neighborhood matching.','wages':{'rows':len(wrows),'errors':werr,'output':str(WOUT) if green else None,'first':wrows[:2],'last':wrows[-2:]},'cpi':{'rows':len(crows),'errors':cerr,'output':str(COUT) if green else None,'extraction_methods':methods,'first':crows[:2],'last':crows[-2:]},'date_sanity_pass':sane,'guardrails':['first-release documents only','document SHA256 per observation','no revised-history fallback','no manual value imputation','no engine/live/OOS changes'],'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
 EVID.write_text(json.dumps(ev,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':ev['status'],'wages_rows':len(wrows),'cpi_rows':len(crows),'wage_errors':len(werr),'cpi_errors':len(cerr),'date_sanity':sane,'methods':methods},ensure_ascii=False))
if __name__=='__main__':main()
