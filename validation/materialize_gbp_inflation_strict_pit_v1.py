#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

START=(2018,1)
END=(2026,8)
MONTHS=['january','february','march','april','may','june','july','august','september','october','november','december']
BASE='https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/consumerpriceinflation'
ROW_KEYS=['reference_month','headline_cpi_yoy_pct','release_date','source_url','page_sha256','source_route','pit_status']
SEMANTIC_KEYS=['reference_month','headline_cpi_yoy_pct','release_date','source_route','pit_status']

class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]
    def handle_data(self,data):
        s=' '.join(data.split())
        if s:self.parts.append(s)

def text_from_html(raw:bytes)->str:
    p=Text(); p.feed(raw.decode('utf-8',errors='replace'))
    return html.unescape(' '.join(p.parts))

def months():
    y,m=START
    while (y,m)<=END:
        yield y,m
        m+=1
        if m==13:y+=1;m=1

def fetch(url:str)->bytes:
    last=None
    for attempt in range(5):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'global-macro-fx-quant/1.0 strict-pit'})
            with urllib.request.urlopen(req,timeout=45) as r:return r.read()
        except Exception as e:
            last=e
            code=getattr(e,'code',None)
            if code not in (429,500,502,503,504):raise
            time.sleep(2**attempt)
    raise last

def bulletin_url(y:int,m:int)->str:
    return f'{BASE}/{MONTHS[m-1]}{y}'

def release_date(text:str)->str:
    x=re.search(r'Release date:\s*(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})',text)
    if not x:
        x=re.search(r'Release date\s+(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})',text)
    if not x:raise ValueError('ONS release date not found')
    return datetime.strptime(x.group(1),'%d %B %Y').date().isoformat()

def headline(text:str,y:int,m:int)->float:
    month=MONTHS[m-1].capitalize(); period=f'{month} {y}'
    pats=[
        rf'The Consumer Prices Index \(CPI\) 12-month inflation rate was ([0-9]+(?:\.[0-9]+)?)% in {re.escape(period)}',
        rf'The Consumer Prices Index \(CPI\) 12-month rate was ([0-9]+(?:\.[0-9]+)?)% in {re.escape(period)}',
        rf'The Consumer Prices Index \(CPI\) rose by ([0-9]+(?:\.[0-9]+)?)% in the 12 months to {re.escape(period)}',
        rf'The Consumer Prices Index \(CPI\) fell by ([0-9]+(?:\.[0-9]+)?)% in the 12 months to {re.escape(period)}',
    ]
    vals=[]
    for i,p in enumerate(pats):
        for x in re.finditer(p,text,flags=re.I):
            v=float(x.group(1)); vals.append(-v if i==3 else v)
    uniq=[]
    for v in vals:
        if all(abs(v-u)>1e-12 for u in uniq):uniq.append(v)
    if len(uniq)!=1:raise ValueError(f'expected one explicit CPI headline for {period}, got {uniq}')
    return uniq[0]

def digest(rows:list[dict])->str:
    canon=[{k:r[k] for k in SEMANTIC_KEYS} for r in rows]
    return hashlib.sha256(json.dumps(canon,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def one(y:int,m:int)->dict:
    ref=f'{y:04d}-{m:02d}'; url=bulletin_url(y,m)
    raw=fetch(url); text=text_from_html(raw)
    title=f'Consumer price inflation, UK: {MONTHS[m-1].capitalize()} {y}'
    if title.lower() not in text.lower():raise ValueError(f'bulletin identity mismatch for {ref}')
    rd=release_date(text); value=headline(text,y,m)
    return {'reference_month':ref,'headline_cpi_yoy_pct':value,'release_date':rd,'source_url':url,'page_sha256':hashlib.sha256(raw).hexdigest(),'source_route':'ONS_CONSUMER_PRICE_INFLATION_BULLETIN','pit_status':'STRICT_FIRST_RELEASE'}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--csv',required=True); ap.add_argument('--evidence',required=True); a=ap.parse_args()
    rows=[]
    for i,(y,m) in enumerate(months(),1):
        r=one(y,m); rows.append(r)
        print(f'[{i:03d}/104] {r["reference_month"]} CPI={r["headline_cpi_yoy_pct"]} release={r["release_date"]}',flush=True)
        time.sleep(.03)
    assert len(rows)==104 and rows[0]['reference_month']=='2018-01' and rows[-1]['reference_month']=='2026-08'
    assert len({r['page_sha256'] for r in rows})==104
    by={r['reference_month']:r for r in rows}
    anchors={'2018-01':(3.0,'2018-02-13'),'2020-01':(1.8,'2020-02-19'),'2026-08':(3.1,'2026-09-16')}
    for k,(v,d) in anchors.items():
        assert abs(by[k]['headline_cpi_yoy_pct']-v)<1e-12 and by[k]['release_date']==d,(k,by[k])
    Path(a.csv).parent.mkdir(parents=True,exist_ok=True)
    with open(a.csv,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ROW_KEYS,lineterminator='\n');w.writeheader();w.writerows(rows)
    ev={
      'schema':'GMFQ_GBP_INFLATION_STRICT_PIT_EVIDENCE_V1_RUNTIME','status':'PASS','target':'GBP.inflation','evidence_class':'STRICT_DIRECT_ARCHIVAL_PIT','authority':'UK Office for National Statistics',
      'coverage':{'start':'2018-01','end':'2026-08','expected_months':104,'materialized_months':104},
      'series_contract':{'series_id':'D7G7','frequency':'M','transformation':'reported_yoy_rate','unit':'% YoY'},
      'route_counts':{'ONS_CONSUMER_PRICE_INFLATION_BULLETIN':104},'unique_page_hashes':104,'semantic_rowset_sha256':digest(rows),
      'semantic_fingerprint_fields':SEMANTIC_KEYS,
      'strict_rules':{'official_publisher_only':True,'period_specific_release_artifact_required':True,'publication_date_required':True,'url_and_sha256_required':True,'current_revised_history_forbidden':True,'revised_history_fallback_used':False},
      'anchor_checks':{k:{'rate':v,'release_date':d} for k,(v,d) in anchors.items()},'generated_at_utc':datetime.now(timezone.utc).isoformat()
    }
    Path(a.evidence).write_text(json.dumps(ev,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(ev,indent=2)); return 0

if __name__=='__main__':raise SystemExit(main())
