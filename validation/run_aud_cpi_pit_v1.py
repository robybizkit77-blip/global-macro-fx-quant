#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re,urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'history/pit_v1/AUD_CPI_HEADLINE_FIRST_RELEASE_2018_2025Q3.csv'
EVID=ROOT/'validation/AUD_CPI_PIT_V1_2026-10-07.json'
BASE='https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia'
LEGACY_DEC18='https://www.abs.gov.au/AUSSTATS/abs%40.nsf/allprimarymainfeatures/97DE913203378356CA2583E5001D660C'
UA={'User-Agent':'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)'}
QMONTHS=(3,6,9,12)
ABBR={3:'mar',6:'jun',9:'sep',12:'dec'}
MONTH_NAMES={3:'March',6:'June',9:'September',12:'December'}

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.text=[]
    def handle_data(self,data):
        s=data.strip()
        if s:self.text.append(s)

def fetch(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=30) as r:return r.read().decode('utf-8',errors='replace')

def text(raw):
    p=P(); p.feed(raw); return re.sub(r'\s+',' ',' '.join(p.text)).strip()

def candidate_urls(y,m):
    a=ABBR[m]
    return [f'{BASE}/{a}-{y}',f'{BASE}/{a}-quarter-{y}']

def parse_modern(url,raw,y,m):
    t=text(raw)
    rm=re.search(r'Released\s+(\d{2}/\d{2}/\d{4})',t)
    if not rm:return None
    release=datetime.strptime(rm.group(1),'%d/%m/%Y').date().isoformat()
    month=MONTH_NAMES[m]
    patterns=[
      rf'Over the twelve months to the {month} {y} quarter,? the CPI rose\s+(-?\d+(?:\.\d+)?)%',
      rf'Over the twelve months to the {month} {y} quarter the CPI rose\s+(-?\d+(?:\.\d+)?)%',
      rf'Over the twelve months to the {month} {y} quarter.*?CPI rose\s+(-?\d+(?:\.\d+)?)%',
      rf'Annually, the CPI rose\s+(-?\d+(?:\.\d+)?)%'
    ]
    v=None
    for pat in patterns:
        mm=re.search(pat,t,re.I|re.S)
        if mm:
            v=float(mm.group(1)); break
    if v is None:return None
    ref=f'{y:04d}-Q{QMONTHS.index(m)+1}'
    return {'reference_quarter':ref,'release_date':release,'headline_cpi_yoy_pct':v,'source_url':url,'archive_format':'modern'}

def parse_legacy_dec18(raw):
    t=text(raw)
    if '30/01/2019' not in t and '30/01/2019' not in raw:
        if '30/01/2019' not in raw.replace(' ',''): raise RuntimeError('legacy CPI release date missing')
    mm=re.search(r'All groups CPI\s+0\.5\s+1\.8',t,re.I|re.S)
    if not mm: raise RuntimeError('legacy Dec 2018 CPI 1.8 marker missing')
    return {'reference_quarter':'2018-Q4','release_date':'2019-01-30','headline_cpi_yoy_pct':1.8,'source_url':LEGACY_DEC18,'archive_format':'legacy_AUSSTATS'}

def quarter_iter():
    y,m=2019,12
    while (y,m)<=(2025,9):
        yield y,m
        m+=3
        if m>12:y,m=y+1,3

def main():
    rows=[]; failures=[]
    for y,m in quarter_iter():
        got=None; errs=[]
        for u in candidate_urls(y,m):
            try:
                got=parse_modern(u,fetch(u),y,m)
                if got: break
                errs.append(f'{u}: parse_none')
            except Exception as e: errs.append(f'{u}: {e}')
        if got: rows.append(got)
        else: failures.append({'reference_quarter':f'{y:04d}-Q{QMONTHS.index(m)+1}','errors':errs})
    rows.append(parse_legacy_dec18(fetch(LEGACY_DEC18)))
    ded={r['reference_quarter']:r for r in rows}; rows=[ded[k] for k in sorted(ded)]
    anchors={'2018-Q4':(1.8,'2019-01-30'),'2019-Q4':(1.8,'2020-01-29'),'2020-Q1':(2.2,'2020-04-29')}
    for k,(v,d) in anchors.items():
        assert k in ded,(k,'missing')
        assert abs(ded[k]['headline_cpi_yoy_pct']-v)<1e-12,(k,ded[k])
        assert ded[k]['release_date']==d,(k,ded[k])
    modern=[r for r in rows if r['archive_format']=='modern']
    if len(modern)<22: raise RuntimeError(f'insufficient modern quarterly releases {len(modern)} failures={len(failures)}')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    fields=['reference_quarter','release_date','headline_cpi_yoy_pct','source_url','archive_format']
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    payload={'schema':'GMFQ_AUD_CPI_PIT_V1','status':'PASS','created_at':'2026-10-07','source':'Australian Bureau of Statistics historical CPI release pages','definition':'headline All groups CPI year-over-year rate exactly as published in each quarterly release','coverage':{'n':len(rows),'modern_n':len(modern),'first':rows[0]['reference_quarter'],'modern_first':modern[0]['reference_quarter'],'last':modern[-1]['reference_quarter'],'missing_modern_releases':len(failures)},'anchors':{k:ded[k] for k in anchors},'failures':failures,'frequency_policy':'quarterly CPI only through 2025-Q3; complete monthly CPI regime from Oct 2025 kept separate to avoid frequency break inside historical reaction test','first_release_policy':'archived release-page value only; no current revised-history substitution','changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
    EVID.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(payload,indent=2))
if __name__=='__main__':main()
