from __future__ import annotations
import hashlib, io, json, re
from pathlib import Path
import requests
from pypdf import PdfReader

SRC=Path('validation/JPY_WAGES_CPI_SOURCE_PROBE_V1_2026-10-06.json')
OUT=Path('validation/JPY_WAGES_CPI_PDF_TEXT_INSPECTION_V1_2026-10-06.json')
MONTHS=['2018-01','2019-03','2021-07','2023-07']
UA={'User-Agent':'GMFQ-PIT-parser-inspection/1.1'}

def dl(url):
 r=requests.get(url,headers=UA,timeout=30); r.raise_for_status(); return r.content,r.headers.get('content-type','')
def pdf_text(b):
 try:
  rd=PdfReader(io.BytesIO(b)); return '\n'.join((p.extract_text() or '') for p in rd.pages)
 except Exception as e:return f'__PDF_ERROR__ {e}'
def snippets(txt,terms,span=700):
 out={}; compact=re.sub(r'\s+',' ',txt)
 for t in terms:
  hits=[]
  for m in re.finditer(re.escape(t),compact,re.I):
   hits.append(compact[max(0,m.start()-span):min(len(compact),m.end()+span)])
   if len(hits)>=8:break
  out[t]=hits
 return out

def choose_wage(z):
 docs=z.get('document_candidates',[])
 for key in ('houdou','pdf'):
  for d in docs:
   if key in d['url'].lower() and d['url'].lower().endswith('.pdf'):return d['url']
 return next((d['url'] for d in docs if d['url'].lower().endswith('.pdf')),None)
def choose_cpi(z):
 docs=z.get('pdf_candidates',[])
 return docs[0]['url'] if docs else None

def inspect(url,terms):
 if not url:return {'url':None,'error':'no_candidate'}
 try:
  b,ct=dl(url); txt=pdf_text(b)
  return {'url':url,'content_type':ct,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'text_length':len(txt),'text_head':re.sub(r'\s+',' ',txt[:5000]),'snippets':snippets(txt,terms)}
 except Exception as e:return {'url':url,'error':str(e)}

def main():
 src=json.loads(SRC.read_text(encoding='utf-8'))
 out={'schema':'GMFQ_JPY_WAGES_CPI_PDF_TEXT_INSPECTION_V1','created_at':'2026-10-06','months':{}}
 for ym in MONTHS:
  wz=src['wages_mhlw_preliminary']['months_found'][ym]
  cz=src['cpi_statistics_bureau_first_release']['months_found'][ym]
  out['months'][ym]={
   'wages':inspect(choose_wage(wz),['きまって支給する給与','決まって支給する給与','現金給与総額','前年同月比','前年比']),
   'cpi':inspect(choose_cpi(cz),['生鮮','生鮮食品','生鮮食品を除く','総合','総合指数','前年同月比','前年同月'])
  }
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({m:{k:{'error':v.get('error'),'text_length':v.get('text_length')} for k,v in z.items()} for m,z in out['months'].items()},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
