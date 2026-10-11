#!/usr/bin/env python3
"""Probe decisive CFTC `Updated` anchors around the 2018-2019 shutdown.

Discovery only. The goal is NOT to build an availability calendar from the
`Updated` marker. Instead, cross-check two independent Legacy Futures Only venue
pages (CME and ICE Futures U.S.) on three decisive report dates:
- normal pre-shutdown control 2018-12-18;
- first two shutdown-backlog reports 2018-12-24 and 2018-12-31.

If the normal control's `Updated` date precedes the known ordinary Friday release,
that proves `Updated` cannot itself be treated as public availability.
"""
from __future__ import annotations

import argparse, hashlib, html, json, pathlib, re, time, urllib.request
from datetime import datetime
from urllib.error import HTTPError, URLError

UA='global-macro-fx-quant/cot-shutdown-updated-date-discovery-v1'
REPORT_DATES=['2018-12-18','2018-12-24','2018-12-31']
VENUES={'CME':'deacmelf','ICE_US':'deanybtlf'}
UPDATED_RE=re.compile(r'\bUpdated\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(20\d{2})\b',re.I)
TRANSIENT={429,500,502,503,504}


def sha(raw:bytes)->str: return hashlib.sha256(raw).hexdigest()
def compact(d:str)->str: return datetime.fromisoformat(d).strftime('%m%d%y')

def candidates(report_date:str,prefix:str)->list[str]:
    year=report_date[:4]; name=f'{prefix}{compact(report_date)}.htm'
    return [
        f'https://www.cftc.gov/files/dea/cotarchives/{year}/futures/{name}',
        f'https://www.cftc.gov/sites/default/files/files/dea/cotarchives/{year}/futures/{name}',
    ]

def fetch_one(url:str)->tuple[bytes,str]:
    last=None
    for attempt in range(1,6):
        req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*;q=0.8','Connection':'close'})
        try:
            with urllib.request.urlopen(req,timeout=60) as r:
                return r.read(),r.geturl()
        except HTTPError as exc:
            last=exc
            if exc.code not in TRANSIENT or attempt==5: raise
        except URLError as exc:
            last=exc
            if attempt==5: raise
        time.sleep((2,5,10,20)[attempt-1])
    raise RuntimeError(repr(last))

def fetch_first(urls:list[str])->tuple[bytes,str,str]:
    errors=[]
    for url in urls:
        try:
            raw,final=fetch_one(url); return raw,url,final
        except Exception as exc:
            errors.append(f'{url}:{exc!r}')
    raise RuntimeError('; '.join(errors))

def visible(raw:bytes)->str:
    text=raw.decode('latin-1',errors='replace')
    text=re.sub(r'<script\b.*?</script>',' ',text,flags=re.I|re.S)
    text=re.sub(r'<style\b.*?</style>',' ',text,flags=re.I|re.S)
    text=html.unescape(re.sub(r'<[^>]+>',' ',text))
    return re.sub(r'\s+',' ',text).strip()

def extract_updated(text:str)->list[str]:
    out=[]
    for month,day,year in UPDATED_RE.findall(text):
        d=datetime.strptime(f'{month.title()} {day} {year}','%B %d %Y').date().isoformat()
        if d not in out: out.append(d)
    return out

def probe(report_date:str,venue:str,prefix:str)->dict:
    raw,requested,final=fetch_first(candidates(report_date,prefix)); text=visible(raw)
    updates=extract_updated(text)
    return {
        'venue':venue,'report_date':report_date,'requested_url':requested,'final_url':final,
        'bytes':len(raw),'raw_sha256':sha(raw),'updated_dates':updates,
        'contains_updated_marker':bool(updates),
    }

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); args=ap.parse_args()
    rows=[]; agreed=[]; errors=[]
    for idx,report_date in enumerate(REPORT_DATES):
        venue_rows=[]
        for venue,prefix in VENUES.items():
            try:
                r=probe(report_date,venue,prefix); venue_rows.append(r); rows.append(r)
            except Exception as exc:
                errors.append({'report_date':report_date,'venue':venue,'error':repr(exc)})
            time.sleep(1.5)
        if len(venue_rows)==2:
            sets=[r['updated_dates'] for r in venue_rows]
            if sets[0] and sets[0]==sets[1] and len(sets[0])==1:
                agreed.append({'report_date':report_date,'updated_date':sets[0][0],'venues':['CME','ICE_US'],'agreement':'TWO_OFFICIAL_VENUE_PAGES_EXACT'})
        if idx < len(REPORT_DATES)-1: time.sleep(2)
    mapping={x['report_date']:x['updated_date'] for x in agreed}
    decisive=(mapping.get('2018-12-18')=='2018-12-20' and mapping.get('2018-12-24')=='2019-02-01' and mapping.get('2018-12-31')=='2019-02-05')
    out={
        'schema':'GMFQ_COT_2018_2019_SHUTDOWN_UPDATED_DATE_DISCOVERY_V1',
        'status':'DISCOVERY_PASS' if not errors and decisive else 'DISCOVERY_PARTIAL',
        'authority':'U.S. Commodity Futures Trading Commission (CFTC)',
        'purpose':'Prove whether CFTC page Updated markers can safely equal public availability.',
        'report_dates':REPORT_DATES,'probes':rows,'agreed_updated_dates':agreed,'errors':errors,
        'conclusion':{
            'updated_marker_equals_public_availability':False if decisive else None,
            'reason':'Normal report 2018-12-18 has venue-consistent Updated 2018-12-20, before ordinary Friday 2018-12-21 publication; therefore Updated cannot be promoted to public availability. Shutdown Updated dates remain corroboration only.' if decisive else 'Insufficient decisive anchors.',
        },
        'invariants':{'official_cftc_only':True,'legacy_futures_only':True,'two_venue_agreement_required':True,'updated_date_not_certified_as_first_publication':True,'historical_backtest_certified':False,'production_write':False}
    }
    semantic={'schema':out['schema'],'status':out['status'],'agreed_updated_dates':agreed,'errors':errors,'conclusion':out['conclusion'],'invariants':out['invariants']}
    out['semantic_sha256']=sha(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode())
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'status':out['status'],'agreed_updated_dates':agreed,'errors':errors,'conclusion':out['conclusion'],'semantic_sha256':out['semantic_sha256']},indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
