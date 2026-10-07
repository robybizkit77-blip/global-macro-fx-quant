#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re,urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'history/pit_v1/AUD_UNEMPLOYMENT_FIRST_RELEASE_2018_2026.csv'
EVID=ROOT/'validation/AUD_UNEMPLOYMENT_PIT_V1_2026-10-07.json'
BASE='https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia'
LEGACY_DEC18='https://www.abs.gov.au/AUSSTATS/abs%40.nsf/Lookup/6202.0Main%20Features1Dec%202018'
UA={'User-Agent':'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)'}
NAMES=['January','February','March','April','May','June','July','August','September','October','November','December']
MONTHS={m:i for i,m in enumerate(NAMES,1)}
ABBR={i:m[:3].lower() for i,m in enumerate(NAMES,1)}

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.text=[]
    def handle_data(self,data):
        s=data.strip()
        if s:self.text.append(s)

def visible(raw):
    p=P(); p.feed(raw); return re.sub(r'\s+',' ',' '.join(p.text)).strip()

def fetch(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=30) as r:return r.read().decode('utf-8',errors='replace')

def parse_page(url,raw):
    txt=visible(raw)
    m=re.search(r'Reference period\s+([A-Z][a-z]+)\s+(20\d{2})',txt)
    rm=re.search(r'Released\s+(\d{2}/\d{2}/\d{4})',txt)
    if not m or not rm:return None
    ref=f'{int(m.group(2)):04d}-{MONTHS[m.group(1)]:02d}'
    release=datetime.strptime(rm.group(1),'%d/%m/%Y').date().isoformat()
    sm=re.search(r'Seasonally Adjusted.*?Unemployment rate\s*\(%\)\s*([0-9]+(?:\.[0-9]+)?)\s*([0-9]+(?:\.[0-9]+)?)',txt,re.I|re.S)
    if not sm:
        sm=re.search(r'Seasonally adjusted terms.*?unemployment rate.*?(?:to|was|at)\s+([0-9]+(?:\.[0-9]+)?)%',txt,re.I|re.S)
        if not sm:return None
        sa=float(sm.group(1))
    else:
        sa=float(sm.group(2))
    return {'reference_month':ref,'release_date':release,'unemployment_rate_sa_pct':sa,'source_url':url,'archive_format':'modern'}

def parse_legacy_dec18(raw):
    txt=visible(raw)
    if '24/01/2019' not in txt and '24/01/2019' not in raw:raise RuntimeError('legacy release date missing')
    if not re.search(r'Unemployment rate \(%\).*?5\.0.*?5\.0',txt,re.I|re.S):raise RuntimeError('legacy unemployment marker missing')
    return {'reference_month':'2018-12','release_date':'2019-01-24','unemployment_rate_sa_pct':5.0,'source_url':LEGACY_DEC18,'archive_format':'legacy_AUSSTATS'}

def month_iter():
    y,m=2019,9
    while (y,m)<=(2026,8):
        yield y,m
        m+=1
        if m==13:y,m=y+1,1

def main():
    rows=[]; failures=[]
    for y,m in month_iter():
        u=f'{BASE}/{ABBR[m]}-{y}'
        try:
            r=parse_page(u,fetch(u))
            if not r or r['reference_month']!=f'{y:04d}-{m:02d}':raise RuntimeError('parse/reference mismatch')
            rows.append(r)
        except Exception as e:failures.append({'reference_month':f'{y:04d}-{m:02d}','url':u,'error':str(e)})
    rows.append(parse_legacy_dec18(fetch(LEGACY_DEC18)))
    ded={r['reference_month']:r for r in rows}; rows=[ded[k] for k in sorted(ded)]
    anchors={'2018-12':(5.0,'2019-01-24'),'2019-12':(5.1,'2020-01-23'),'2020-01':(5.3,'2020-02-20')}
    for k,(v,d) in anchors.items():
        assert k in ded,(k,'missing',failures[:6]); assert abs(ded[k]['unemployment_rate_sa_pct']-v)<1e-12,(k,ded[k]); assert ded[k]['release_date']==d,(k,ded[k])
    modern=[r for r in rows if r['archive_format']=='modern']
    if len(modern)<75:raise RuntimeError(f'insufficient modern releases {len(modern)} failures={failures[:12]}')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    fields=['reference_month','release_date','unemployment_rate_sa_pct','source_url','archive_format']
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    payload={'schema':'GMFQ_AUD_UNEMPLOYMENT_PIT_V1','status':'PASS','created_at':'2026-10-07','source':'Australian Bureau of Statistics historical Labour Force release pages','definition':'seasonally adjusted unemployment rate exactly as published in each release','coverage':{'n':len(rows),'modern_n':len(modern),'first':rows[0]['reference_month'],'modern_first':modern[0]['reference_month'],'last':modern[-1]['reference_month'],'missing_modern_releases':len(failures)},'anchors':{k:ded[k] for k in anchors},'failures':failures,'first_release_policy':'archived release-page value only; no current revised-history substitution','changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
    EVID.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(payload,indent=2))
if __name__=='__main__':main()
