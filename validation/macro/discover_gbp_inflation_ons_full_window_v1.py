#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html import unescape

INDEX='https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23/previous'
UA='GLOBAL-MACRO-FX-QUANT GBP inflation ONS temporal discovery v1'
TITLE='CPI ANNUAL RATE 00: ALL ITEMS 2015=100'
DATE_RE=re.compile(r'(\d{1,2}\s+[A-Za-z]+\s+\d{4})')
CSV_LINK_RE=re.compile(r'href=["\'](?P<href>[^"\']*generator\?format=csv[^"\']*)["\']',re.I)
VERSION_RE=re.compile(r'(?:%2F|/)previous(?:%2F|/)v(?P<v>\d+)',re.I)


def get(url:str,timeout:int=35)->bytes:
    last=None
    for attempt in range(4):
        req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,text/csv,*/*'})
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last=e
            if e.code != 429 or attempt == 3:
                raise
            retry_after=e.headers.get('Retry-After') if e.headers else None
            try: delay=max(1.0,float(retry_after)) if retry_after else (2.0*(attempt+1))
            except ValueError: delay=2.0*(attempt+1)
            time.sleep(delay)
    raise RuntimeError(f'ONS fetch failed: {last!r}')


def norm(s:str)->str:
    return re.sub(r'[^a-z0-9]+',' ',unescape(s).lower()).strip()


def parse_index(raw:bytes):
    text=raw.decode('utf-8',errors='replace')
    plain=re.sub(r'<[^>]+>',' ',text); plain=re.sub(r'\s+',' ',plain)
    n=norm(plain)
    if 'd7g7' not in n or 'cpi annual rate 00 all items 2015 100' not in n:
        raise ValueError('ONS previous-version index is not canonical D7G7/MM23')
    rows=[]
    for m in CSV_LINK_RE.finditer(text):
        href=unescape(m.group('href'))
        vm=VERSION_RE.search(href)
        if not vm: continue
        v=int(vm.group('v'))
        tail=text[m.end():m.end()+1200]
        dm=DATE_RE.search(re.sub(r'<[^>]+>',' ',tail))
        if not dm: continue
        url=urllib.parse.urljoin(INDEX,href)
        rows.append({'version':v,'release_date':dm.group(1),'csv_url':url})
    uniq={r['version']:r for r in rows}
    rows=[uniq[v] for v in sorted(uniq)]
    if not rows: raise ValueError('no versioned CSV links parsed from ONS index')
    return rows


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); a=ap.parse_args()
    index_raw=get(INDEX)
    versions=parse_index(index_raw)
    years={}
    for x in versions:
        y=x['release_date'].split()[-1]; years[y]=years.get(y,0)+1
    coverage={str(y):years.get(str(y),0) for y in range(2018,2027)}
    coverage_ok=all(coverage[str(y)]>=10 for y in range(2018,2026)) and coverage['2026']>=7

    target=[]
    for y in ('2018','2022','2026'):
        candidates=[x for x in versions if x['release_date'].endswith(y)]
        if candidates: target.append(candidates[0])
    samples=[]; errors=[]
    for row in target:
        try:
            raw=get(row['csv_url'])
            text=raw.decode('utf-8-sig',errors='replace')
            nt=norm(text)
            if 'd7g7' not in nt and 'cpi annual rate 00 all items 2015 100' not in nt:
                raise ValueError('sample CSV lacks D7G7/title marker')
            samples.append({'version':row['version'],'release_date':row['release_date'],'csv_url':row['csv_url'],'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
        except Exception as e:
            errors.append({'version':row['version'],'error':repr(e)})

    semantic=[[x['version'],x['release_date'],x['csv_url']] for x in versions]
    sha=hashlib.sha256(json.dumps(semantic,separators=(',',':')).encode()).hexdigest()
    samples_ok=len(samples)==len(target) and not errors and len(samples)>=3
    status='DISCOVERY_PASS' if coverage_ok and samples_ok else 'DISCOVERY_WITHHELD'
    out={'schema':'GMFQ_GBP_INFLATION_ONS_FULL_WINDOW_DISCOVERY_V1','status':status,'authority':'Office for National Statistics','canonical_series':{'dataset':'MM23','series_id':'D7G7','label':TITLE,'unit':'%','transformation':'reported_yoy_rate'},'index_url':INDEX,'index_sha256':hashlib.sha256(index_raw).hexdigest(),'version_count':len(versions),'first_version':versions[0],'last_version':versions[-1],'by_release_year':years,'target_coverage':coverage,'coverage_ok':coverage_ok,'sample_vintage_csvs':samples,'sample_csvs_ok':samples_ok,'errors':errors,'semantic_sha256':sha,'versions':versions,'invariants':{'exact_series_semantics':True,'native_ons_version_history':True,'as_it_existed_files':True,'no_cpih_substitution':True,'no_interpolation':True,'production_write':False,'changes_live_data':False,'changes_engine_rules':False,'certification_implied':False}}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ['status','version_count','first_version','last_version','target_coverage','coverage_ok','sample_vintage_csvs','sample_csvs_ok','errors','semantic_sha256']},indent=2))
    return 0 if status=='DISCOVERY_PASS' else 2

if __name__=='__main__': raise SystemExit(main())
