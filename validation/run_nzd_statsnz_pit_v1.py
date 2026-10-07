#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re,urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT_CPI=ROOT/'history/pit_v1/NZD_CPI_HEADLINE_FIRST_RELEASE_2019_2026.csv'
OUT_LAB=ROOT/'history/pit_v1/NZD_UNEMPLOYMENT_FIRST_RELEASE_2019_2026.csv'
EVID=ROOT/'validation/NZD_STATSNZ_PIT_V1_2026-10-07.json'
BASE='https://www.stats.govt.nz/information-releases'
UA={'User-Agent':'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)'}
MONTHS={3:'march',6:'june',9:'september',12:'december'}
QNO={3:1,6:2,9:3,12:4}

class P(HTMLParser):
    def __init__(self): super().__init__(); self.t=[]
    def handle_data(self,d):
        s=d.strip()
        if s:self.t.append(s)

def visible(raw):
    p=P(); p.feed(raw); return re.sub(r'\s+',' ',' '.join(p.t)).strip()

def fetch(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=30) as r:return r.read().decode('utf-8',errors='replace')

def release_date(t):
    m=re.search(r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2}),\s*\d{1,2}:\d{2}(?:am|pm)',t,re.I)
    if not m:return None
    return datetime.strptime(f'{m.group(1)} {m.group(2)} {m.group(3)}','%d %B %Y').date().isoformat()

def cpi_value(t,y,m):
    pats=[
      r'annual inflation rate was\s+(-?\d+(?:\.\d+)?)\s+percent',
      r'CPI inflation rate was\s+(-?\d+(?:\.\d+)?)\s+percent',
      r'consumer price index.*?increased\s+(-?\d+(?:\.\d+)?)\s+percent in the 12 months',
      r'Annual inflation at\s+(-?\d+(?:\.\d+)?)\s+percent'
    ]
    for p in pats:
        z=re.search(p,t,re.I|re.S)
        if z:return float(z.group(1))
    return None

def labour_value(t):
    pats=[
      r'Unemployment rate (?:fell|rose|increased|decreased|remained|was).*?\b(?:to|at|was)\s+([0-9]+(?:\.\d+)?)\s+percent',
      r'unemployment rate was\s+([0-9]+(?:\.\d+)?)\s+percent',
      r'unemployment rate.*?\b([0-9]+(?:\.\d+)?)\s+percent'
    ]
    for p in pats:
        z=re.search(p,t,re.I|re.S)
        if z:return float(z.group(1))
    return None

def qiter():
    for y in range(2019,2027):
        for m in (3,6,9,12):
            if (y,m)<(2019,12) or (y,m)>(2026,6):continue
            yield y,m

def main():
    cpi=[]; lab=[]; failures=[]
    for y,m in qiter():
        mon=MONTHS[m]; ref=f'{y}-Q{QNO[m]}'
        specs=[('cpi',f'{BASE}/consumers-price-index-{mon}-{y}-quarter/'),('lab',f'{BASE}/labour-market-statistics-{mon}-{y}-quarter/')]
        for kind,url in specs:
            try:
                t=visible(fetch(url)); rd=release_date(t)
                if not rd:raise RuntimeError('release_date_missing')
                if kind=='cpi':
                    v=cpi_value(t,y,m)
                    if v is None:raise RuntimeError('cpi_parse_none')
                    cpi.append({'reference_quarter':ref,'release_date':rd,'headline_cpi_yoy_pct':v,'source_url':url})
                else:
                    v=labour_value(t)
                    if v is None:raise RuntimeError('labour_parse_none')
                    lab.append({'reference_quarter':ref,'release_date':rd,'unemployment_rate_sa_pct':v,'source_url':url})
            except Exception as e:failures.append({'kind':kind,'reference_quarter':ref,'url':url,'error':str(e)})
    dc={r['reference_quarter']:r for r in cpi}; dl={r['reference_quarter']:r for r in lab}
    anchors_cpi={'2021-Q3':(4.9,'2021-10-18')}
    anchors_lab={'2021-Q3':(3.4,'2021-11-03')}
    for k,(v,d) in anchors_cpi.items():
        assert k in dc,(k,'missing CPI'); assert abs(dc[k]['headline_cpi_yoy_pct']-v)<1e-12,(k,dc[k]); assert dc[k]['release_date']==d,(k,dc[k])
    for k,(v,d) in anchors_lab.items():
        assert k in dl,(k,'missing labour'); assert abs(dl[k]['unemployment_rate_sa_pct']-v)<1e-12,(k,dl[k]); assert dl[k]['release_date']==d,(k,dl[k])
    if len(cpi)<20 or len(lab)<20: raise RuntimeError(f'insufficient coverage cpi={len(cpi)} labour={len(lab)} failures={failures[:12]}')
    OUT_CPI.parent.mkdir(parents=True,exist_ok=True)
    with OUT_CPI.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['reference_quarter','release_date','headline_cpi_yoy_pct','source_url']);w.writeheader();w.writerows(sorted(cpi,key=lambda x:x['reference_quarter']))
    with OUT_LAB.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['reference_quarter','release_date','unemployment_rate_sa_pct','source_url']);w.writeheader();w.writerows(sorted(lab,key=lambda x:x['reference_quarter']))
    payload={'schema':'GMFQ_NZD_STATSNZ_PIT_V1','status':'PASS','created_at':'2026-10-07','source':'Stats NZ archived information releases','coverage':{'cpi_n':len(cpi),'labour_n':len(lab),'first_cpi':min(dc),'last_cpi':max(dc),'first_labour':min(dl),'last_labour':max(dl),'failures_n':len(failures)},'anchors':{'cpi':{k:dc[k] for k in anchors_cpi},'labour':{k:dl[k] for k in anchors_lab}},'failures':failures,'first_release_policy':'archived release-page value and release timestamp only; no current revised-history substitution','changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
    EVID.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8');print(json.dumps(payload,indent=2))
if __name__=='__main__':main()
