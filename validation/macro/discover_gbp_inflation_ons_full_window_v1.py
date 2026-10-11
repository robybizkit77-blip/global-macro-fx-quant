#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import pathlib
import re
import urllib.error
import urllib.request

BASE='https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23/previous/v{}'
UA='GLOBAL-MACRO-FX-QUANT GBP inflation ONS temporal discovery v1'
VERSION_MIN=1
VERSION_MAX=160
DATE_RE=re.compile(r'Release date:\s*</?[^>]*>?(?:\s*)?(\d{1,2}\s+[A-Za-z]+\s+\d{4})',re.I)
DATE_TEXT_RE=re.compile(r'Release date:\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})',re.I)
SERIES_RE=re.compile(r'Series ID:\s*D7G7',re.I)
TITLE_RE=re.compile(r'CPI ANNUAL RATE 00:\s*ALL ITEMS 2015=100',re.I)


def fetch(v:int):
    url=BASE.format(v)
    req=urllib.request.Request(url,headers={'User-Agent':UA})
    try:
        with urllib.request.urlopen(req,timeout=25) as r:
            raw=r.read()
    except urllib.error.HTTPError as e:
        if e.code in (404,410):
            return None
        raise
    text=raw.decode('utf-8',errors='replace')
    plain=re.sub(r'<[^>]+>',' ',text)
    plain=re.sub(r'\s+',' ',plain)
    if not SERIES_RE.search(plain) or not TITLE_RE.search(plain):
        raise ValueError(f'v{v} is not canonical D7G7/MM23 CPI page')
    m=DATE_TEXT_RE.search(plain)
    if not m:
        raise ValueError(f'cannot parse release date for v{v}')
    return {'version':v,'release_date':m.group(1),'url':url,'http_sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); a=ap.parse_args()
    found=[]; errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        futs={ex.submit(fetch,v):v for v in range(VERSION_MIN,VERSION_MAX+1)}
        for fut,v in futs.items():
            try:
                row=fut.result()
                if row: found.append(row)
            except Exception as e:
                errors.append({'version':v,'error':repr(e)})
    found.sort(key=lambda x:x['version'])
    semantic=[[x['version'],x['release_date'],x['url']] for x in found]
    sha=hashlib.sha256(json.dumps(semantic,separators=(',',':')).encode()).hexdigest()
    years={}
    for x in found:
        y=x['release_date'].split()[-1]
        years[y]=years.get(y,0)+1
    target_years=[str(y) for y in range(2018,2027)]
    coverage={y:years.get(y,0) for y in target_years}
    coverage_ok=all(coverage[y]>=10 for y in map(str,range(2018,2026))) and coverage['2026']>=8
    out={'schema':'GMFQ_GBP_INFLATION_ONS_FULL_WINDOW_DISCOVERY_V1','status':'DISCOVERY_PASS' if coverage_ok and not errors else 'DISCOVERY_WITHHELD','authority':'Office for National Statistics','canonical_series':{'dataset':'MM23','series_id':'D7G7','label':'CPI ANNUAL RATE 00: ALL ITEMS 2015=100','unit':'%'},'version_scan':{'min':VERSION_MIN,'max':VERSION_MAX},'version_count':len(found),'by_release_year':years,'target_coverage':coverage,'coverage_ok':coverage_ok,'errors':errors,'semantic_sha256':sha,'versions':found,'invariants':{'exact_series_semantics':True,'no_cpih_substitution':True,'no_interpolation':True,'production_write':False,'changes_live_data':False,'changes_engine_rules':False,'certification_implied':False}}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ['status','version_count','target_coverage','coverage_ok','errors','semantic_sha256']},indent=2))
    return 0 if out['status']=='DISCOVERY_PASS' else 2

if __name__=='__main__': raise SystemExit(main())
