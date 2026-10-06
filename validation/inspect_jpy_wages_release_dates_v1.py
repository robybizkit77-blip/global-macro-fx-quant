from __future__ import annotations
import hashlib, io, json, re
from pathlib import Path
import requests
from pypdf import PdfReader

OUT=Path('validation/JPY_WAGES_RELEASE_DATE_INSPECTION_V1_2026-10-06.json')
S=requests.Session();S.headers.update({'User-Agent':'GMFQ-PIT-wages-date-inspection/1.0'})
P={
 '2018-01':'https://www.mhlw.go.jp/toukei/itiran/roudou/monthly/30/3001p/dl/houdou3001p.pdf',
 '2023-07':'https://www.mhlw.go.jp/toukei/itiran/roudou/monthly/r05/2307p/dl/houdou2307p.pdf'}

def jpdate(text):
    t=text.replace(' ','').replace('\u3000','')
    pats=[
      (r'平成(\d+)年(\d{1,2})月(\d{1,2})日',lambda y,m,d:(1988+int(y),int(m),int(d))),
      (r'令和(元|\d+)年(\d{1,2})月(\d{1,2})日',lambda y,m,d:(2019 if y=='元' else 2018+int(y),int(m),int(d))),
      (r'(20\d{2})年(\d{1,2})月(\d{1,2})日',lambda y,m,d:(int(y),int(m),int(d))),
    ]
    for p,fn in pats:
      mm=re.search(p,t)
      if mm:
        y,m,d=fn(*mm.groups()); return f'{y:04d}-{m:02d}-{d:02d}',mm.group(0)
    return None,None

def inspect(url):
    r=S.get(url,timeout=45);r.raise_for_status();b=r.content
    rd=PdfReader(io.BytesIO(b)); txt='\n'.join((p.extract_text() or '') for p in rd.pages[:3])
    dt,raw=jpdate(txt[:8000])
    return {'url':url,'status':r.status_code,'sha256':hashlib.sha256(b).hexdigest(),'pages':len(rd.pages),'release_date':dt,'matched_date_text':raw,'first_text':txt[:2500]}

def main():
    out={'schema':'GMFQ_JPY_WAGES_RELEASE_DATE_INSPECTION_V1','created_at':'2026-10-06','samples':{}}
    for k,u in P.items():
      try:out['samples'][k]=inspect(u)
      except Exception as e:out['samples'][k]={'error':type(e).__name__+': '+str(e)}
    out.update(changes_engine_rules=False,changes_live_data=False,changes_oos_baseline=False)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:{'date':v.get('release_date'),'error':v.get('error')} for k,v in out['samples'].items()},ensure_ascii=False))
if __name__=='__main__':main()
