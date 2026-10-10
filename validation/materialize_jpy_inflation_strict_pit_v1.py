#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, html, io, json, re, time
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pypdf import PdfReader

START=(2018,1); END=(2026,8); EXPECTED_MONTHS=104
BASE='https://www.e-stat.go.jp'
SCHEMA='GMFQ_JPY_INFLATION_STRICT_PIT_EVIDENCE_V1_RUNTIME'
SERIES_ID='JP_CPI_HEADLINE_YOY'; MACRO_SERIES_ID='JP_CPI_HEADLINE_YOY_history_value'
AUTHORITY='Statistics Bureau of Japan'; SOURCE='Statistics Bureau of Japan / e-Stat period-specific CPI release PDFs'
UA='GMFQ-Strict-PIT-validation/1.1'
QCODE={1:'110103',2:'120406',3:'230709',4:'241012'}


def iter_months(a,b):
 y,m=a
 while (y,m)<=b:
  yield y,m
  if m==12:y,m=y+1,1
  else:m+=1


def get(url):
 req=Request(url,headers={'User-Agent':UA,'Accept-Language':'ja,en;q=0.8'})
 last=None
 for attempt in range(6):
  try:
   with urlopen(req,timeout=45) as r:return r.read(),r.headers.get('Content-Type',''),r.geturl()
  except Exception as e:
   last=e; time.sleep(1.5*(attempt+1))
 raise last


def pdf_text(raw):
 text='\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(raw)).pages[:4])
 return re.sub(r'[ \t]+',' ',text.replace('\u3000',' ').replace('−','-').replace('－','-'))


def era_year(era,n): return (1988+n) if era=='平成' else (2018+n)


def parse_release_date(text, required=True):
 g=re.search(r'(?<!\d)(20\d{2})\s*年\s*(1[0-2]|0?[1-9])\s*月\s*([0-3]?\d)\s*日',text)
 if g:return f'{int(g.group(1)):04d}-{int(g.group(2)):02d}-{int(g.group(3)):02d}'
 e=re.search(r'(平成|令和)\s*([0-9０-９]+|元)\s*年\s*([0-9０-９]{1,2})\s*月\s*([0-9０-９]{1,2})\s*日',text)
 if e:
  tr=str.maketrans('０１２３４５６７８９','0123456789'); ey=1 if e.group(2)=='元' else int(e.group(2).translate(tr))
  return f'{era_year(e.group(1),ey):04d}-{int(e.group(3).translate(tr)):02d}-{int(e.group(4).translate(tr)):02d}'
 if required: raise ValueError('release date not found in CPI release PDF')
 return None


def parse_headline_yoy(text):
 c=re.sub(r'\s+','',text)
 for p in [r'総合指数.*?前年同月比は([0-9]+(?:\.[0-9]+)?)[％%]の(上昇|下落)',r'総合.*?前年同月比は([0-9]+(?:\.[0-9]+)?)[％%]の(上昇|下落)']:
  m=re.search(p,c,re.S)
  if m:return float(m.group(1)) if m.group(2)=='上昇' else -float(m.group(1))
 if re.search(r'総合指数.*?前年同月比は0(?:\.0+)?[％%].*?(同水準|横ばい)',c,re.S): return 0.0
 raise ValueError('national all-items CPI YoY not found')


def parse_period_title(text):
 c=re.sub(r'\s+','',text); tr=str.maketrans('０１２３４５６７８９','0123456789')
 g=re.search(r'全国.*?(20\d{2})年.*?([0-9]{1,2})月分',c)
 if g:return int(g.group(1)),int(g.group(2))
 e=re.search(r'全国.*?(平成|令和)([0-9０-９]+|元)年.*?([0-9０-９]{1,2})月分',c)
 if e:
  ey=1 if e.group(2)=='元' else int(e.group(2).translate(tr)); return era_year(e.group(1),ey),int(e.group(3).translate(tr))
 return None


def month_code(m): return QCODE[(m-1)//3+1]+f'{m:02d}'


def collection(y,m):
 if (y,m)<=(2021,6):
  return {'tclass1':'000001085955','tstat':'000001084976','label':'ESTAT_CPI_2015_BASE'}
 return {'tclass1':'000001150149','tstat':'000001150147','label':'ESTAT_CPI_2020_BASE'}


def exact_estat_record(y,m):
 cfg=collection(y,m)
 params={'cycle':'1','layout':'datalist','month':month_code(m),'page':'1','result_back':'1','tclass1':cfg['tclass1'],'toukei':'00200573','tstat':cfg['tstat'],'year':f'{y}0'}
 surl=BASE+'/stat-search/files?'+urlencode(params)
 raw,_,_=get(surl); txt=html.unescape(raw.decode('utf-8','replace'))
 ids=[]
 for hit in re.finditer(r'(?:stat_infid|statInfId)=(\d+)',txt,re.I):
  window=html.unescape(txt[max(0,hit.start()-1400):hit.end()+1400])
  if '全国' in window and ('結果概要' in window or '月報' in window): ids.append(hit.group(1))
 ids=list(dict.fromkeys(ids)); candidates=[]
 for sid in ids:
  murl=BASE+'/stat-search/files?'+urlencode({'stat_infid':sid}); mraw,_,mfinal=get(murl)
  plain=re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',html.unescape(mraw.decode('utf-8','replace'))))
  if '消費者物価指数' not in plain or '全国' not in plain: continue
  if not (re.search(rf'{y}年\s*{m}月',plain) or re.search(rf'{y}年.*?{m}月分',plain)): continue
  pub=re.search(r'公開年月日時分\s*(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2})',plain)
  if not pub: continue
  durl=BASE+'/stat-search/file-download?'+urlencode({'fileKind':'2','statInfId':sid}); draw,ct,dfinal=get(durl)
  if not draw.startswith(b'%PDF'): continue
  ptxt=pdf_text(draw)
  period=parse_period_title(ptxt)
  if period is not None and period!=(y,m): continue
  try: value=parse_headline_yoy(ptxt)
  except Exception: continue
  candidates.append({'sid':sid,'release_date':pub.group(1),'release_time':pub.group(2),'metadata_url':mfinal,'source_url':dfinal,'raw':draw,'content_type':ct,'value':value,'pdf_date':parse_release_date(ptxt,required=False),'route':cfg['label']})
 uniq={hashlib.sha256(x['raw']).hexdigest():x for x in candidates}
 if len(uniq)!=1: raise ValueError(f'e-Stat CPI exact-release ambiguity {y:04d}-{m:02d}: {len(uniq)} unique compatible PDFs from {len(ids)} ids')
 return next(iter(uniq.values()))


def semantic_hash(rows):
 p=json.dumps([{k:r[k] for k in ('observation_date','value','release_date','source_sha256')} for r in rows],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
 return hashlib.sha256(p).hexdigest()


def replay(captured):
 out=[]
 for item in captured:
  raw=bytes.fromhex(item['source_hex']); text=pdf_text(raw); y,m=map(int,item['observation_date'].split('-')); period=parse_period_title(text)
  if period is not None and period!=(y,m): raise ValueError(f"replay period mismatch {item['observation_date']}: {period}")
  out.append({'observation_date':item['observation_date'],'value':parse_headline_yoy(text),'release_date':item['release_date'],'release_time_jst':item['release_time_jst'],'source_url':item['source_url'],'metadata_url':item['metadata_url'],'stat_inf_id':item['stat_inf_id'],'source_route':item['source_route'],'source_sha256':hashlib.sha256(raw).hexdigest()})
 return out


def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,required=True); args=ap.parse_args()
 months=list(iter_months(START,END)); rows=[]; captured=[]
 if len(months)!=EXPECTED_MONTHS: raise ValueError('contract month count mismatch')
 for idx,(y,m) in enumerate(months,1):
  rec=exact_estat_record(y,m); obs=f'{y:04d}-{m:02d}'; digest=hashlib.sha256(rec['raw']).hexdigest()
  if rec['pdf_date'] is not None and rec['pdf_date']!=rec['release_date']: raise ValueError(f"PDF/e-Stat date mismatch {obs}: {rec['pdf_date']} != {rec['release_date']}")
  row={'observation_date':obs,'value':rec['value'],'release_date':rec['release_date'],'release_time_jst':rec['release_time'],'source_url':rec['source_url'],'metadata_url':rec['metadata_url'],'stat_inf_id':rec['sid'],'source_route':rec['route'],'source_sha256':digest}
  rows.append(row); captured.append({**row,'source_hex':rec['raw'].hex()})
  print(f"[capture {idx:03d}/{EXPECTED_MONTHS}] {obs} CPI_YOY={rec['value']} release={rec['release_date']} sid={rec['sid']} sha={digest[:12]}",flush=True)
  time.sleep(.08)
 if len({r['source_sha256'] for r in rows})!=EXPECTED_MONTHS: raise ValueError('expected one unique PDF hash per month')
 for r in rows:
  if date.fromisoformat(r['release_date'])<=date.fromisoformat(r['observation_date']+'-01'): raise ValueError(f'implausible release chronology {r}')
 r1=replay(captured); r2=replay(captured)
 if r1!=rows or r2!=rows or r1!=r2: raise ValueError('deterministic replay mismatch')
 sh=semantic_hash(rows)
 ev={'schema':SCHEMA,'target':{'currency':'JPY','dimension':'inflation','macro_series_id':MACRO_SERIES_ID},'series_id':SERIES_ID,'authority':AUTHORITY,'source':SOURCE,'evidence_class':'STRICT_DIRECT_ARCHIVAL_PIT','verdict':'STRICT_DIRECT_ARCHIVAL_PIT_CERTIFIABLE','frequency':'M','transformation':'reported_yoy_rate','coverage':{'start':'2018-01','end':'2026-08','expected':EXPECTED_MONTHS,'observed':len(rows)},'unique_source_hashes':len({r['source_sha256'] for r in rows}),'network_capture_count':EXPECTED_MONTHS,'replay_count':2,'replay_equal':True,'publication_timestamp_authority':'OFFICIAL_ESTAT_METADATA__PDF_DATE_CROSSCHECK_WHEN_PARSEABLE','current_revised_history_used':False,'revised_fallback_used':False,'semantic_rowset_sha256':sh,'anchors':{'2026-07':next(r for r in rows if r['observation_date']=='2026-07'),'2026-08':next(r for r in rows if r['observation_date']=='2026-08')},'rows':rows}
 args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(ev,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'status':'PASS','coverage':ev['coverage'],'unique_source_hashes':ev['unique_source_hashes'],'semantic_rowset_sha256':sh,'replay_equal':True},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
