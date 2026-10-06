from __future__ import annotations
import hashlib,io,json,re
from pathlib import Path
import requests
from pypdf import PdfReader
OUT=Path('validation/JPY_CPI_PDF_TEXT_INSPECTION_V1_2026-10-06.json')
S=requests.Session();S.headers.update({'User-Agent':'GMFQ-PIT-cpi-pdf-inspection/1.0'})
P={
'2018-01':'https://www.e-stat.go.jp/stat-search/file-download?statInfId=000031673550&fileKind=2',
'2023-07':'https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040087883&fileKind=2'}
KEYS=['総合','生鮮食品を除く総合','前年同月比','前年同月','上昇','下落']
def inspect(url):
 r=S.get(url,timeout=45);r.raise_for_status();b=r.content
 reader=PdfReader(io.BytesIO(b));texts=[]
 for i,p in enumerate(reader.pages[:8]):
  try:t=p.extract_text() or ''
  except Exception:t=''
  texts.append(t)
 full='\n'.join(texts);compact=re.sub(r'[ \t]+',' ',full)
 snippets=[]
 for key in KEYS:
  start=0
  for _ in range(8):
   pos=compact.find(key,start)
   if pos<0:break
   snippets.append({'key':key,'text':compact[max(0,pos-220):pos+520]})
   start=pos+len(key)
 return {'url':url,'status':r.status_code,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'pages':len(reader.pages),'text_chars':len(full),'snippets':snippets[:50],'first_text':compact[:5000]}
def main():
 o={'schema':'GMFQ_JPY_CPI_PDF_TEXT_INSPECTION_V1','created_at':'2026-10-06','samples':{}}
 for k,u in P.items():
  try:o['samples'][k]=inspect(u)
  except Exception as e:o['samples'][k]={'error':type(e).__name__+': '+str(e)}
 o.update(changes_engine_rules=False,changes_live_data=False,changes_oos_baseline=False)
 OUT.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:{'text_chars':v.get('text_chars'),'snips':len(v.get('snippets',[])),'error':v.get('error')} for k,v in o['samples'].items()},ensure_ascii=False))
if __name__=='__main__':main()
