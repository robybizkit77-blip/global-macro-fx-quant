from __future__ import annotations
import hashlib,io,json,re
from pathlib import Path
from urllib.parse import urljoin
import requests,pandas as pd
from bs4 import BeautifulSoup
OUT=Path('validation/JPY_PARSER_STRUCTURE_V2_2026-10-06.json')
S=requests.Session();S.headers.update({'User-Agent':'GMFQ-PIT-parser-structure/2.0'})
W={
'2018-01':'https://www.mhlw.go.jp/toukei/itiran/roudou/monthly/30/3001p/xls/3001c01p.xls',
'2023-07':'https://www.mhlw.go.jp/toukei/itiran/roudou/monthly/r05/2307p/xls/2307c01p.xlsx'}
C={
'2018-01':'https://www.e-stat.go.jp/stat-search/files?cycle=1&layout=datalist&month=11010301&page=1&result_back=1&tclass1=000001085955&tclass2val=0&toukei=00200573&tstat=000001084976&year=20180',
'2023-07':'https://www.e-stat.go.jp/stat-search/files?cycle=1&layout=datalist&month=23070907&page=1&result_back=1&tclass1=000001150149&tclass2val=0&toukei=00200573&tstat=000001150147&year=20230'}
def nonempty_rows(url):
 r=S.get(url,timeout=40);r.raise_for_status();b=r.content;eng='xlrd' if url.endswith('.xls') else 'openpyxl';df=pd.read_excel(io.BytesIO(b),header=None,engine=eng,dtype=object)
 rows=[]
 for i,row in df.iterrows():
  cells=[]
  for j,x in enumerate(row.tolist()):
   if not pd.isna(x) and str(x).strip()!='':cells.append({'c':j,'v':str(x).strip()[:200]})
  if cells:rows.append({'r':int(i),'cells':cells[:30]})
 return {'url':url,'sha256':hashlib.sha256(b).hexdigest(),'shape':[int(df.shape[0]),int(df.shape[1])],'rows':rows[:80]}
def ancestor_context(a):
 node=a
 best=' '.join(a.stripped_strings)
 for _ in range(8):
  node=getattr(node,'parent',None)
  if node is None:break
  txt=' '.join(node.stripped_strings)
  if 80<=len(txt)<=1800:best=txt
  if any(k in txt for k in ['表番号','調査年月','公開（更新）日']):return txt[:1800]
 return best[:1800]
def cpi_entries(url):
 r=S.get(url,timeout=40);r.raise_for_status();s=BeautifulSoup(r.text,'html.parser');out=[];seen=set()
 for a in s.find_all('a',href=True):
  lab=' '.join(a.stripped_strings).upper();href=urljoin(r.url,a['href'])
  if lab not in {'PDF','EXCEL','CSV'}:continue
  if href in seen:continue
  seen.add(href);ctx=ancestor_context(a)
  out.append({'kind':lab,'url':href,'context':ctx})
 return {'url':url,'entries':out[:160]}
def main():
 o={'schema':'GMFQ_JPY_PARSER_STRUCTURE_V2','created_at':'2026-10-06','wages':{},'cpi':{}}
 for k,u in W.items():
  try:o['wages'][k]=nonempty_rows(u)
  except Exception as e:o['wages'][k]={'error':type(e).__name__+': '+str(e)}
 for k,u in C.items():
  try:o['cpi'][k]=cpi_entries(u)
  except Exception as e:o['cpi'][k]={'error':type(e).__name__+': '+str(e)}
 o.update(changes_engine_rules=False,changes_live_data=False,changes_oos_baseline=False)
 OUT.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'wages_shapes':{k:v.get('shape') for k,v in o['wages'].items()},'cpi_entries':{k:len(v.get('entries',[])) for k,v in o['cpi'].items()}},ensure_ascii=False))
if __name__=='__main__':main()
