#!/usr/bin/env python3
import argparse,csv,hashlib,html,io,json,re,time
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from pypdf import PdfReader

START=(2018,1); LEGACY_END=(2023,7); ESTAT_START=(2023,8); END=(2026,8)
LEGACY='https://www.stat.go.jp/data/roudou/rireki/tsuki/pdf/{yyyymm}.pdf'
BASE='https://www.e-stat.go.jp'
UA='GMFQ-Strict-PIT-validation/2.3'
QCODE={1:'110103',2:'120406',3:'230709',4:'241012'}

def months(a,b):
 out=[];y,m=a
 while (y,m)<=b:
  out.append(f'{y:04d}-{m:02d}');m+=1
  if m==13:y+=1;m=1
 return out

def get(url):
 req=Request(url,headers={'User-Agent':UA,'Accept-Language':'ja,en;q=0.8'})
 with urlopen(req,timeout=45) as r:return r.read(),r.headers.get('Content-Type',''),r.geturl()

def pdf_text(raw):return '\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(raw)).pages[:10])

def era_to_iso(era,y,m,d):
 yy=1 if y=='元' else int(y); year=(1988+yy) if era=='平成' else (2018+yy)
 return date(year,int(m),int(d)).isoformat()

def parse_release_date(text,required=True):
 # Older releases use Japanese era notation; newer layouts may use Gregorian year notation.
 m=re.search(r'(平成|令和)\s*(元|\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日',text)
 if m:return era_to_iso(*m.groups())
 g=re.search(r'(?<!\d)(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',text)
 if g:return date(int(g.group(1)),int(g.group(2)),int(g.group(3))).isoformat()
 if required:raise ValueError('release date not found in PDF')
 return None

def parse_values(text):
 sec=text
 for marker in ('季節調整値でみた結果の概要','季節調整値でみた結果','季節調整値'):
  i=text.find(marker)
  if i>=0: sec=text[i:];break
 ur=None
 pats=[r'完全失業率(?:（季節調整値）)?\s*(?:は|：|:)\s*([0-9]+(?:\.[0-9]+)?)\s*[％%]',r'完全失業率[^\n]{0,120}?([0-9]+(?:\.[0-9]+)?)\s*[％%]']
 for p in pats:
  q=re.search(p,sec)
  if q: ur=float(q.group(1));break
 if ur is None: raise ValueError('SA unemployment rate not found')
 emp=None
 for p in [r'就業者数\s*(?:は|：|:)\s*([0-9]{4})\s*万人',r'就業者[^\n]{0,60}?([0-9]{4})\s*万人']:
  q=re.search(p,text)
  if q: emp=int(q.group(1));break
 return ur,emp

def legacy(month):
 url=LEGACY.format(yyyymm=month.replace('-',''));raw,ct,final=get(url);txt=pdf_text(raw)
 rd=parse_release_date(txt,required=True);ur,emp=parse_values(txt)
 return {'reference_month':month,'release_date':rd,'release_time_jst':'08:30','availability_timestamp_jst':rd+'T08:30:00+09:00','unemployment_rate_sa_pct':ur,'employed_10k_context':emp,'source_route':'STATGO_LEGACY_IMMUTABLE_MONTHLY_PDF','source_url':final,'metadata_url':'','stat_inf_id':'','pdf_release_date_crosscheck':rd,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'content_type':ct,'pit_status':'STRICT_FIRST_RELEASE'}

def month_code(m):return QCODE[(m-1)//3+1]+f'{m:02d}'

def exact_estat_record(month):
 y,ms=month.split('-');m=int(ms)
 params={'cycle':'1','layout':'datalist','month':month_code(m),'page':'1','result_back':'1','tclass1':'000001226833','tclass2':'000001226834','tclass3val':'0','toukei':'00200531','tstat':'000001226583','year':f'{y}0'}
 surl=BASE+'/stat-search/files?'+urlencode(params);raw,_,_=get(surl);text=html.unescape(raw.decode('utf-8','replace'))
 ids=[]
 for hit in re.finditer(r'(?:stat_infid|statInfId)=(\d+)',text,re.I):
  w=html.unescape(text[max(0,hit.start()-1200):hit.end()+1200])
  if '結果の概要' in w: ids.append(hit.group(1))
 ids=list(dict.fromkeys(ids)); exact=[]
 for sid in ids:
  murl=BASE+'/stat-search/files?'+urlencode({'stat_infid':sid});mraw,_,mfinal=get(murl)
  t=html.unescape(mraw.decode('utf-8','replace'));plain=re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',t))
  if not all(x in plain for x in ['労働力調査','基本集計','結果の概要']):continue
  if not re.search(rf'調査年月\s*{y}年\s*{m}月',plain):continue
  if re.search(r'統計表名\s*結果の概要',plain) is None and '結果の概要 月次' not in plain:continue
  pub=re.search(r'公開年月日時分\s*(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2})',plain)
  if not pub:continue
  durl=BASE+'/stat-search/file-download?'+urlencode({'fileKind':'2','statInfId':sid});draw,ct,dfinal=get(durl)
  if not draw.startswith(b'%PDF'):continue
  exact.append((sid,pub.group(1),pub.group(2),mfinal,dfinal,draw,ct))
 uniq={hashlib.sha256(x[5]).hexdigest():x for x in exact}
 if len(uniq)!=1:raise ValueError(f'e-Stat exact result-summary ambiguity {month}: {len(uniq)}')
 return next(iter(uniq.values()))

def estat(month):
 sid,rd,rt,meta,final,raw,ct=exact_estat_record(month);txt=pdf_text(raw);ur,emp=parse_values(txt)
 if rt!='08:30':raise ValueError(f'unexpected official publication time {month}: {rt}')
 # e-Stat metadata is the mandatory publication-time authority. PDF date is an additional
 # consistency check when the current PDF layout exposes a parseable date.
 pdf_rd=parse_release_date(txt,required=False)
 if pdf_rd is not None and pdf_rd!=rd:raise ValueError(f'PDF/metadata release-date mismatch {month}: {pdf_rd}!={rd}')
 return {'reference_month':month,'release_date':rd,'release_time_jst':rt,'availability_timestamp_jst':rd+'T'+rt+':00+09:00','unemployment_rate_sa_pct':ur,'employed_10k_context':emp,'source_route':'ESTAT_PERIOD_SPECIFIC_RESULT_SUMMARY','source_url':final,'metadata_url':meta,'stat_inf_id':sid,'pdf_release_date_crosscheck':pdf_rd or 'NOT_EXPOSED_IN_PARSEABLE_PDF_TEXT','sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'content_type':ct,'pit_status':'STRICT_FIRST_RELEASE'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--csv',required=True);ap.add_argument('--evidence',required=True);args=ap.parse_args()
 target=months(START,END);rows=[];errors=[]
 for i,m in enumerate(target):
  try: rows.append(legacy(m) if m<=f'{LEGACY_END[0]:04d}-{LEGACY_END[1]:02d}' else estat(m))
  except Exception as e: errors.append({'reference_month':m,'error':repr(e)})
  time.sleep(.03)
 got=[r['reference_month'] for r in rows];missing=sorted(set(target)-set(got));dups=sorted({x for x in got if got.count(x)>1})
 hashes=[r['sha256'] for r in rows];hash_dups=len(hashes)!=len(set(hashes))
 continuity=(not missing and not dups and len(rows)==len(target)==104)
 fallback=False
 status='PASS' if continuity and not errors and not hash_dups and not fallback else 'FAIL'
 ev={'schema':'GMFQ_JPY_LABOUR_STRICT_PIT_EVIDENCE_V2','status':status,'target':'JPY.labour','evidence_class':'STRICT_DIRECT_ARCHIVAL_PIT','coverage':{'start':target[0],'end':target[-1],'expected_months':104,'materialized_months':len(rows),'legacy_months':len([r for r in rows if r['source_route'].startswith('STATGO')]),'estat_months':len([r for r in rows if r['source_route'].startswith('ESTAT')])},'strict_rules':{'official_publisher_only':True,'period_specific_release_artifact_required':True,'publication_timestamp_required':True,'publication_timestamp_authority':'OFFICIAL_ESTAT_METADATA_FOR_ESTAT_ROUTE__PDF_CROSSCHECK_WHEN_PARSEABLE','sha256_required':True,'current_revised_history_forbidden':True,'revised_history_fallback_used':False},'missing':missing,'duplicates':dups,'duplicate_pdf_hashes':hash_dups,'errors':errors,'route_transition':{'legacy_end':'2023-07','estat_start':'2023-08'},'changes_live_data':False,'changes_engine_rules':False}
 Path(args.evidence).write_text(json.dumps(ev,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 if status!='PASS':print(json.dumps(ev,ensure_ascii=False,indent=2));raise SystemExit(1)
 Path(args.csv).parent.mkdir(parents=True,exist_ok=True)
 with open(args.csv,'w',newline='',encoding='utf-8') as f:
  fields=list(rows[0]);w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 print(json.dumps(ev,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
