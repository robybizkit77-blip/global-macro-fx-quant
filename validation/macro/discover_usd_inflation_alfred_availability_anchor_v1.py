#!/usr/bin/env python3
"""Test whether ALFRED vintage dates line up with known official BLS CPI releases.

For each pinned BLS anchor, query only the target CPI observation on the day
before release and on the official release date. Strict expectation:
- target observation absent before official BLS release date;
- target observation present on official BLS release date.

This is discovery evidence only; it does not certify the full 2018-2026 ledger.
"""
from __future__ import annotations
import argparse,csv,hashlib,io,json,pathlib,time,urllib.parse,urllib.request
from datetime import date,timedelta

BASE='https://alfred.stlouisfed.org/graph/alfredgraph.csv'
SERIES='CPIAUCSL'
UA='GLOBAL-MACRO-FX-QUANT USD inflation ALFRED availability anchor v1'
ANCHORS=[
    {'observation_date':'2018-01-01','release_date':'2018-02-14','official_reference':'https://www.bls.gov/schedule/2018/home.htm'},
    {'observation_date':'2022-01-01','release_date':'2022-02-10','official_reference':'https://www.bls.gov/schedule/2022/02_sched_list.htm'},
    {'observation_date':'2024-01-01','release_date':'2024-02-13','official_reference':'https://www.bls.gov/schedule/2024/02_sched_list.htm'},
    {'observation_date':'2026-08-01','release_date':'2026-09-11','official_reference':'https://www.bls.gov/news.release/archives/cpi_09112026.htm'},
]

def fetch_one(obs_date:str,vintage_date:str)->dict:
    params={'id':SERIES,'vintage_date':vintage_date,'cosd':obs_date,'coed':obs_date}
    url=BASE+'?'+urllib.parse.urlencode(params)
    raw=None; last=None
    for attempt in range(1,5):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/csv,*/*;q=0.8','Connection':'close'})
            with urllib.request.urlopen(req,timeout=60) as r: raw=r.read()
            break
        except Exception as exc:
            last=exc
            if attempt<4: time.sleep((3,8,15)[attempt-1])
    if raw is None: raise RuntimeError(f'ALFRED fetch failed {obs_date=} {vintage_date=}: {last!r}')
    rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig'))))
    vals=[]
    for row in rows[1:]:
        if len(row)<2: continue
        if row[0].strip()!=obs_date: continue
        value=row[1].strip()
        if value and value!='.': vals.append(float(value))
    if len(vals)>1: raise RuntimeError(f'duplicate values {obs_date=} {vintage_date=}: {vals}')
    return {
        'observation_date':obs_date,'vintage_date':vintage_date,'present':len(vals)==1,
        'value':vals[0] if vals else None,'http_sha256':hashlib.sha256(raw).hexdigest(),'url':url,
    }

def economic(row:dict)->dict: return {k:v for k,v in row.items() if k!='http_sha256'}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); a=ap.parse_args()
    tests=[]; errors=[]
    try:
        for anchor in ANCHORS:
            release=date.fromisoformat(anchor['release_date'])
            before=(release-timedelta(days=1)).isoformat()
            pre=fetch_one(anchor['observation_date'],before)
            on=fetch_one(anchor['observation_date'],anchor['release_date'])
            passed=(pre['present'] is False and on['present'] is True)
            tests.append({**anchor,'before_release_probe':pre,'release_date_probe':on,'pass':passed})
    except Exception as exc:
        errors.append(repr(exc))
    status='DISCOVERY_PASS' if not errors and len(tests)==len(ANCHORS) and all(t['pass'] for t in tests) else 'DISCOVERY_FAIL'
    out={
        'schema':'GMFQ_USD_INFLATION_ALFRED_AVAILABILITY_ANCHOR_V1','status':status,
        'authority':'Federal Reserve Bank of St. Louis ALFRED; release-date anchors U.S. Bureau of Labor Statistics',
        'series_id':SERIES,'tests':tests,'errors':errors,
        'interpretation':'ALFRED vintage_date may be used as a date-level availability boundary only if every pinned BLS anchor transitions from absent to present exactly on the official release date.',
        'time_rule':'Official CPI release time is separately pinned as 08:30 America/New_York; ALFRED vintage_date has day precision only.',
        'production_write':False,
    }
    semantic={**out,'tests':[{**t,'before_release_probe':economic(t['before_release_probe']),'release_date_probe':economic(t['release_date_probe'])} for t in tests]}
    out['semantic_sha256']=hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':status,'tests':[{'obs':t['observation_date'],'release':t['release_date'],'pre':t['before_release_probe']['present'],'on':t['release_date_probe']['present'],'pass':t['pass']} for t in tests],'errors':errors,'semantic_sha256':out['semantic_sha256']},indent=2))
    if status!='DISCOVERY_PASS': raise SystemExit(2)
if __name__=='__main__': main()
