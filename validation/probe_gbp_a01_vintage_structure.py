#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

PAGE='https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/datasets/summaryoflabourmarketstatistics/current'
UA='global-macro-fx-quant/1.0 (+read-only PIT vintage validation)'
OUT=Path('/tmp/gmfq-gbp-ons-pit/a01_vintage_structure_probe.json')
TARGETS=['2021-05-18','2024-02-13','2026-02-17']

def parse_dt(s):
    s=' '.join(s.split())
    for fmt in ('%d %B %Y %H:%M','%d %B %Y'):
        try:return datetime.strptime(s,fmt)
        except ValueError:pass
    return None

def versions():
    r=requests.get(PAGE,headers={'User-Agent':UA},timeout=60);r.raise_for_status()
    soup=BeautifulSoup(r.text,'html.parser')
    out=[]
    for tr in soup.find_all('tr'):
        a=tr.find('a',href=True)
        if not a:continue
        cells=[' '.join(td.get_text(' ',strip=True).split()) for td in tr.find_all(['td','th'])]
        if not cells:continue
        dt=None
        for c in reversed(cells):
            dt=parse_dt(c)
            if dt:break
        if not dt:continue
        href=urljoin(PAGE,a['href'])
        if not re.search(r'\.xlsx?(?:\?|$)',href,re.I):continue
        out.append({'superseded_at':dt.isoformat(),'url':href,'cells':cells})
    out.sort(key=lambda x:x['superseded_at'])
    return out

def first_snapshot_after(vs,target):
    target_date=datetime.fromisoformat(target).date()
    for v in vs:
        if datetime.fromisoformat(v['superseded_at']).date()>target_date:
            return v
    return None

def nonempty_row(row,limit=60):
    vals=[str(x).strip() if pd.notna(x) else '' for x in row.tolist()]
    return [{'col':j,'value':v} for j,v in enumerate(vals) if v][:limit]

def is_period_like(v):
    if isinstance(v,(datetime,pd.Timestamp)): return True
    s=str(v).strip()
    pats=[r'^\d{4}\s+[A-Z][a-z]{2}-[A-Z][a-z]{2}$',r'^[A-Z][a-z]{2}-[A-Z][a-z]{2}\s+\d{4}$',r'^\d{4}\s+Q[1-4]$',r'^[A-Z][a-z]{2}\s+\d{4}$']
    return any(re.match(p,s) for p in pats)

def probe_book(url,target):
    rr=requests.get(url,headers={'User-Agent':UA},timeout=120);rr.raise_for_status()
    ext='.xlsx' if '.xlsx' in url.lower() else '.xls'
    path=Path(f'/tmp/gmfq-gbp-ons-pit/a01_{target}{ext}')
    path.write_bytes(rr.content)
    xf=pd.ExcelFile(path)
    hits=[]
    patterns=('employment rate','unemployment rate','employment aged','unemployment aged')
    for sheet in xf.sheet_names:
        try:df=pd.read_excel(path,sheet_name=sheet,header=None,dtype=object)
        except Exception as e:
            hits.append({'sheet':sheet,'read_error':repr(e)});continue
        for i,row in df.iterrows():
            vals=[str(x).strip() if pd.notna(x) else '' for x in row.tolist()]
            joined=' | '.join(vals).lower()
            if any(p in joined for p in patterns):
                hits.append({'sheet':sheet,'row':int(i),'cells':nonempty_row(row)})
                if len(hits)>=80:break
        if len(hits)>=80:break
    df1=pd.read_excel(path,sheet_name='1',header=None,dtype=object)
    header_rows=[{'row':i,'cells':nonempty_row(df1.iloc[i])} for i in range(min(10,len(df1))) if nonempty_row(df1.iloc[i])]
    period_rows=[]
    for i in range(7,len(df1)):
        row=df1.iloc[i]
        vals=row.tolist()
        if any(is_period_like(v) for v in vals[:4] if pd.notna(v)):
            period_rows.append({'row':int(i),'cells':nonempty_row(row)})
    data_tail=period_rows[-8:]
    return {'downloaded_bytes':len(rr.content),'sheet_names':xf.sheet_names,'candidate_rows':hits,'header_rows':header_rows,'data_tail':data_tail,'period_row_count':len(period_rows)}

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    vs=versions();rows=[]
    for target in TARGETS:
        snap=first_snapshot_after(vs,target)
        if not snap:
            rows.append({'target_release':target,'status':'NO_SNAPSHOT'});continue
        probe=probe_book(snap['url'],target)
        rows.append({'target_release':target,'status':'PASS','selected_snapshot':snap,**probe})
    ok=all(r.get('status')=='PASS' and r.get('header_rows') and r.get('data_tail') for r in rows)
    out={'schema':'GMFQ_GBP_ONS_A01_VINTAGE_STRUCTURE_PROBE_V3','status':'PASS' if ok else 'FAIL',
         'selection_rule':'For release date D select the first archived A01 workbook whose calendar superseded date is strictly later than D. The selected file is therefore the vintage available after D until its first later replacement/correction.',
         'versions_discovered':len(vs),'targets':rows,
         'guardrails':{'read_only':True,'live_data_modified':False,'model_rules_modified':False,'uses_current_revised_timeseries_for_values':False,'rules_fingerprint_expected_unchanged':'3356baf0'}}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(out,indent=2,ensure_ascii=False))
    if not ok:raise SystemExit(1)
if __name__=='__main__':main()
