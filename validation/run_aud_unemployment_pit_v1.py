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
        super().__init__(); self.text=[]; self.rows=[]; self.in_tr=False; self.in_cell=False; self.cells=[]; self.buf=[]
    def handle_starttag(self,tag,attrs):
        if tag=='tr': self.in_tr=True; self.cells=[]
        if self.in_tr and tag in ('td','th'): self.in_cell=True; self.buf=[]
    def handle_endtag(self,tag):
        if self.in_tr and tag in ('td','th') and self.in_cell:
            self.cells.append(re.sub(r'\s+',' ',' '.join(self.buf)).strip()); self.in_cell=False
        if tag=='tr' and self.in_tr:
            if self.cells:self.rows.append(self.cells[:])
            self.in_tr=False
    def handle_data(self,data):
        s=data.strip()
        if s:self.text.append(s)
        if self.in_cell and s:self.buf.append(s)

def fetch(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=30) as r:return r.read().decode('utf-8',errors='replace')

def parse_page(url,raw):
    p=P(); p.feed(raw); txt=' '.join(p.text)
    m=re.search(r'Reference period\s+([A-Z][a-z]+)\s+(20\d{2})',txt)
    rm=re.search(r'Released\s+(\d{2}/\d{2}/\d{4})',txt)
    if not m or not rm:return None
    ref=f'{int(m.group(2)):04d}-{MONTHS[m.group(1)]:02d}'
    release=datetime.strptime(rm.group(1),'%d/%m/%Y').date().isoformat()
    ur=[]
    for row in p.rows:
        if row and row[0].strip().lower().startswith('unemployment rate'):
            nums=[]
            for c in row[1:]:
                mm=re.fullmatch(r'(-?\d+(?:\.\d+)?)',c.replace('%','').strip())
                if mm:nums.append(float(mm.group(1)))
            if len(nums)>=2:ur.append(nums[1])
    if len(ur)<2:return None
    return {'reference_month':ref,'release_date':release,'unemployment_rate_sa_pct':ur[1],'source_url':url,'archive_format':'modern'}

def parse_legacy_dec18(raw):
    p=P(); p.feed(raw); txt=' '.join(p.text)
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
        assert k in ded,(k,'missing'); assert abs(ded[k]['unemployment_rate_sa_pct']-v)<1e-12,(k,ded[k]); assert ded[k]['release_date']==d,(k,ded[k])
    modern=[r for r in rows if r['archive_format']=='modern']
    if len(modern)<75:raise RuntimeError(f'insufficient modern releases {len(modern)} failures={len(failures)}')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    fields=['reference_month','release_date','unemployment_rate_sa_pct','source_url','archive_format']
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    payload={'schema':'GMFQ_AUD_UNEMPLOYMENT_PIT_V1','status':'PASS','created_at':'2026-10-07','source':'Australian Bureau of Statistics historical Labour Force release pages','definition':'seasonally adjusted unemployment rate exactly as published in each release','coverage':{'n':len(rows),'modern_n':len(modern),'first':rows[0]['reference_month'],'modern_first':modern[0]['reference_month'],'last':modern[-1]['reference_month'],'missing_modern_releases':len(failures)},'anchors':{k:ded[k] for k in anchors},'failures':failures,'first_release_policy':'archived release-page value only; no current revised-history substitution','changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
    EVID.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(payload,indent=2))
if __name__=='__main__':main()
