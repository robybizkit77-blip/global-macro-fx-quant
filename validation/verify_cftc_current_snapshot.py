#!/usr/bin/env python3
from __future__ import annotations
import json, pathlib, re, sys, urllib.request
from datetime import datetime

ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'live_data'/'sections'/'V250_COT_CHART_DATA.json'

CURRENCIES={
    'CAD':('090741','https://www.cftc.gov/dea/futures/deacmesf.htm'),
    'CHF':('092741','https://www.cftc.gov/dea/futures/deacmesf.htm'),
    'GBP':('096742','https://www.cftc.gov/dea/futures/deacmesf.htm'),
    'JPY':('097741','https://www.cftc.gov/dea/futures/deacmesf.htm'),
    'EUR':('099741','https://www.cftc.gov/dea/futures/deacmesf.htm'),
    'NZD':('112741','https://www.cftc.gov/dea/futures/deacmesf.htm'),
    'AUD':('232741','https://www.cftc.gov/dea/futures/deacmesf.htm'),
    'USD':('098662','https://www.cftc.gov/dea/futures/deanybtsf.htm'),
}

def fetch(url:str)->str:
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 GMFQ validation'})
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.read().decode('utf-8','replace')

def parse_block(text:str, code:str)->dict:
    m=re.search(rf'Code-{re.escape(code)}|Code\s*#?{re.escape(code)}',text,re.I)
    if not m:
        raise ValueError(f'code {code} not found')
    start=m.start()
    nxt=re.search(r'\n\s*[A-Z0-9][^\n]{5,120}Code[-\s#]\d{6}',text[m.end():],re.I)
    end=(m.end()+nxt.start()) if nxt else min(len(text),start+6000)
    block=text[start:end]
    dm=re.search(r'(?:POSITIONS AS OF|Positions as of|Futures Only,?)\s+(\d{2}/\d{2}/\d{2}|[A-Za-z]+\s+\d{1,2},\s+\d{4})',block,re.I)
    if not dm:
        dm=re.search(r'(\d{2}/\d{2}/\d{2})',block)
    if not dm:
        raise ValueError(f'{code}: date not found')
    raw=dm.group(1)
    if '/' in raw:
        date=datetime.strptime(raw,'%m/%d/%y').strftime('%Y-%m-%d')
    else:
        date=datetime.strptime(raw,'%B %d, %Y').strftime('%Y-%m-%d')
    om=re.search(r'OPEN INTEREST:\s*([\d,]+)',block,re.I)
    if not om:
        om=re.search(r'Open Interest is\s*([\d,]+)',block,re.I)
    if not om:
        raise ValueError(f'{code}: open interest not found')
    oi=int(om.group(1).replace(',',''))
    cm=re.search(r'COMMITMENTS\s*\n\s*([\d,]+)\s+([\d,]+)',block,re.I)
    if not cm:
        cm=re.search(r'All\s*:\s*[\d,]+:\s*([\d,]+)\s+([\d,]+)',block,re.I)
    if not cm:
        raise ValueError(f'{code}: non-commercial commitments not found')
    longv=int(cm.group(1).replace(',','')); shortv=int(cm.group(2).replace(',',''))
    return {'date':date,'open_interest':oi,'long':longv,'short':shortv,'net':longv-shortv,'netoi':round((longv-shortv)/oi*100,3)}

def main()->int:
    current=json.loads(DATA.read_text())
    pages={}
    rows={}
    for c,(code,url) in CURRENCIES.items():
        pages.setdefault(url,fetch(url))
        rows[c]=parse_block(pages[url],code)
    dates={r['date'] for r in rows.values()}
    if len(dates)!=1:
        raise SystemExit('CFTC cross-market date mismatch: '+repr(rows))
    mismatches=[]
    for c,row in rows.items():
        s=current[c]
        observed={
            'date':s['dates'][-1],
            'long':int(s['long'][-1]),
            'short':int(s['short'][-1]),
            'net':int(s['net'][-1]),
            'netoi':round(float(s['netoi'][-1]),3),
        }
        for k in ('date','long','short','net','netoi'):
            if observed[k]!=row[k]:
                mismatches.append({'currency':c,'field':k,'live_data':observed[k],'official':row[k]})
    result={
        'status':'PASS' if not mismatches else 'FAIL',
        'source':'CFTC Legacy Futures Only current reports',
        'as_of':next(iter(dates)),
        'currencies':8,
        'official':rows,
        'mismatches':mismatches,
        'direct_section_action':'NO_CHANGE' if not mismatches else 'BLOCK',
    }
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0 if not mismatches else 1

if __name__=='__main__':
    sys.exit(main())
