#!/usr/bin/env python3
"""Probe CFTC shutdown-backlog report pages for first-publication date evidence.

Discovery only. For each report date around the 2018-2019 appropriations lapse,
fetch two independent Legacy Futures Only venue pages (CME and ICE Futures U.S.)
and extract any CFTC-rendered `Updated Month D, YYYY` marker. A date is emitted
only when both venues agree. Controls before the shutdown and after catch-up are
included to test whether `Updated` tracks ordinary publication timing too.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import pathlib
import re
import urllib.error
import urllib.request
from datetime import datetime

UA='global-macro-fx-quant/cot-shutdown-updated-date-discovery-v1'
REPORT_DATES=[
    '2018-12-18', # normal pre-shutdown control
    '2018-12-24','2018-12-31',
    '2019-01-08','2019-01-15','2019-01-22','2019-01-29',
    '2019-02-05','2019-02-12','2019-02-19','2019-02-26','2019-03-05',
    '2019-03-12', # post-catch-up/control candidate
]
VENUES={
    'CME':'deacmelf',
    'ICE_US':'deanybtlf',
}
UPDATED_RE=re.compile(r'\bUpdated\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(20\d{2})\b',re.I)


def sha(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()


def compact(d:str)->str:
    return datetime.fromisoformat(d).strftime('%m%d%y')


def candidates(report_date:str,prefix:str)->list[str]:
    year=report_date[:4]; stamp=compact(report_date); name=f'{prefix}{stamp}.htm'
    return [
        f'https://www.cftc.gov/files/dea/cotarchives/{year}/futures/{name}',
        f'https://www.cftc.gov/sites/default/files/files/dea/cotarchives/{year}/futures/{name}',
    ]


def fetch_first(urls:list[str])->tuple[bytes,str,str]:
    errors=[]
    for url in urls:
        req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*;q=0.8'})
        try:
            with urllib.request.urlopen(req,timeout=60) as r:
                raw=r.read()
                if r.status==200:
                    return raw,url,r.geturl()
                errors.append(f'{url}:HTTP {r.status}')
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
    raw,requested,final=fetch_first(candidates(report_date,prefix))
    text=visible(raw)
    updates=extract_updated(text)
    report_human=datetime.fromisoformat(report_date).strftime('%B %-d, %Y')
    report_identity=(report_human.lower() in text.lower()) or (report_date in text)
    return {
        'venue':venue,'report_date':report_date,'requested_url':requested,'final_url':final,
        'bytes':len(raw),'raw_sha256':sha(raw),'report_identity_ok':report_identity,
        'updated_dates':updates,
        'contains_updated_marker':bool(updates),
    }


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); args=ap.parse_args()
    rows=[]; agreed=[]; errors=[]
    for report_date in REPORT_DATES:
        venue_rows=[]
        for venue,prefix in VENUES.items():
            try:
                r=probe(report_date,venue,prefix); venue_rows.append(r); rows.append(r)
            except Exception as exc:
                errors.append({'report_date':report_date,'venue':venue,'error':repr(exc)})
        if len(venue_rows)==2:
            if not all(r['report_identity_ok'] for r in venue_rows):
                errors.append({'report_date':report_date,'error':'REPORT_IDENTITY_FAILED'})
                continue
            update_sets=[r['updated_dates'] for r in venue_rows]
            if update_sets[0] and update_sets[0]==update_sets[1] and len(update_sets[0])==1:
                agreed.append({
                    'report_date':report_date,
                    'updated_date':update_sets[0][0],
                    'venues':['CME','ICE_US'],
                    'agreement':'TWO_OFFICIAL_VENUE_PAGES_EXACT',
                })
    out={
        'schema':'GMFQ_COT_2018_2019_SHUTDOWN_UPDATED_DATE_DISCOVERY_V1',
        'status':'DISCOVERY_PASS' if not errors and len(agreed)==len(REPORT_DATES) else 'DISCOVERY_PARTIAL',
        'authority':'U.S. Commodity Futures Trading Commission (CFTC)',
        'purpose':'Test whether period-specific official Legacy Futures Only pages expose venue-consistent Updated dates usable as publication-availability evidence.',
        'report_dates':REPORT_DATES,
        'probes':rows,
        'agreed_updated_dates':agreed,
        'errors':errors,
        'invariants':{
            'official_cftc_only':True,
            'legacy_futures_only':True,
            'two_venue_agreement_required':True,
            'updated_date_not_yet_certified_as_first_publication':True,
            'historical_backtest_certified':False,
            'production_write':False,
        }
    }
    semantic={
        'schema':out['schema'],'status':out['status'],'report_dates':REPORT_DATES,
        'agreed_updated_dates':agreed,'errors':errors,'invariants':out['invariants']
    }
    out['semantic_sha256']=sha(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({
        'status':out['status'],'agreed_updated_dates':agreed,'errors':errors,
        'semantic_sha256':out['semantic_sha256']
    },indent=2))
    # Partial is valuable discovery evidence; transport/parser errors are surfaced in artifact.
    return 0

if __name__=='__main__': raise SystemExit(main())
