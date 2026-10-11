#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,hashlib,io,json,pathlib,time,urllib.parse,urllib.request
from datetime import date,timedelta

BASE='https://alfred.stlouisfed.org/graph/alfredgraph.csv'
SERIES='CPIAUCSL'
UA='Mozilla/5.0 (compatible; GLOBAL-MACRO-FX-QUANT/1.0; strict PIT ALFRED replay)'
EXPECTED=104


def month_start(key:str)->date:
    y,m=map(int,key.split('-')); return date(y,m,1)
def add_months(d:date,n:int)->date:
    x=d.year*12+(d.month-1)+n
    return date(x//12,x%12+1,1)
def fetch_vintage(vintage:date,start:date,end:date)->tuple[dict[str,float],bytes,str]:
    # Transport hardening only: query semantics and PIT assertions are unchanged.
    # ALFRED's keyless graph endpoint can be slow for historical vintages from
    # hosted runners, so use a browser-like UA, a longer read timeout, exponential
    # spacing, and a cache-busting retry token that does not alter query semantics.
    base_params={'id':SERIES,'vintage_date':vintage.isoformat(),'cosd':start.isoformat(),'coed':end.isoformat()}
    raw=None; last=None; final_url=None
    for attempt,wait in enumerate((0,5,15,30,60),start=1):
        if wait: time.sleep(wait)
        params=dict(base_params)
        if attempt>1:
            params['_retry']=str(attempt)
        url=BASE+'?'+urllib.parse.urlencode(params)
        try:
            req=urllib.request.Request(url,headers={
                'User-Agent':UA,
                'Accept':'text/csv,application/csv;q=0.9,*/*;q=0.5',
                'Accept-Language':'en-US,en;q=0.8',
                'Connection':'close',
                'Cache-Control':'no-cache',
            })
            with urllib.request.urlopen(req,timeout=180) as r:
                raw=r.read(); final_url=r.geturl()
            if not raw:
                raise ValueError('empty ALFRED response')
            break
        except Exception as exc:
            last=exc; raw=None
    if raw is None: raise RuntimeError(f'ALFRED fetch failed {vintage}: {last!r}')
    rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig'))))
    if len(rows)<1 or len(rows[0])<2: raise ValueError(f'invalid ALFRED CSV for {vintage}')
    out={}
    for row in rows[1:]:
        if len(row)<2: continue
        ds,val=row[0].strip(),row[1].strip()
        if not ds or not val or val=='.': continue
        try: out[ds]=float(val)
        except ValueError: continue
    return out,raw,final_url or url

def canonical_yoy(idx_t:float,idx_12:float)->float:
    return 100.0*(idx_t/idx_12-1.0)

def validate_calendar(d:dict)->list[dict]:
    if d.get('schema')!='GMFQ_USD_CPI_BLS_RELEASE_CHAIN_V1': raise ValueError('wrong release-chain schema')
    if d.get('status')!='CERTIFIABLE_RELEASE_CALENDAR_WITH_OFFICIAL_GAP': raise ValueError('release calendar not certified with official-gap semantics')
    rows=d.get('release_rows',[])
    if len(rows)!=EXPECTED: raise ValueError(f'expected {EXPECTED} calendar months, got {len(rows)}')
    if rows[0]['reference_month']!='2018-01' or rows[-1]['reference_month']!='2026-08': raise ValueError('wrong coverage')
    gaps=[r for r in rows if r.get('availability_status')=='NOT_PUBLISHED_OFFICIAL']
    if len(gaps)!=1 or gaps[0]['reference_month']!='2025-10': raise ValueError('unexpected official-gap structure')
    for r in rows:
        if r.get('availability_status')=='PUBLISHED':
            if r.get('release_time')!='08:30' or r.get('release_timezone')!='America/New_York':
                raise ValueError('noncanonical BLS release timestamp')
        elif r.get('availability_status')!='NOT_PUBLISHED_OFFICIAL':
            raise ValueError('unknown availability status')
    return rows

def materialize(calendar_rows:list[dict])->dict:
    rows=[]; materialized=0; unavailable=0
    for i,r in enumerate(calendar_rows,1):
        if r.get('availability_status')=='NOT_PUBLISHED_OFFICIAL':
            unavailable+=1
            rows.append({
              'reference_month':r['reference_month'],'release_date':None,'release_time':None,
              'release_timezone':'America/New_York','eligible_date':None,'series_id':SERIES,
              'index_t':None,'index_t_minus_12':None,'cpi_yoy':None,'vintage_date':None,
              'prior_vintage_date':None,'release_day_ref_present':None,'day_before_ref_present':None,
              'availability_status':'UNAVAILABLE_OFFICIAL_NOT_PUBLISHED',
              'unavailable_reason':r.get('official_gap_reason'),'bls_gap_evidence_url':r.get('source_url'),
              'bls_gap_evidence_sha256':r.get('source_sha256'),
            })
            continue
        ref=month_start(r['reference_month']); ref12=add_months(ref,-12)
        release=date.fromisoformat(r['release_date']); prior=release-timedelta(days=1)
        cur,raw_cur,url_cur=fetch_vintage(release,ref12,ref)
        time.sleep(0.35)
        prev,raw_prev,url_prev=fetch_vintage(prior,ref12,ref)
        k_t=ref.isoformat(); k_12=ref12.isoformat()
        if k_t not in cur:
            raise ValueError(f'{r["reference_month"]}: current reference month absent on official release-date vintage {release}')
        if k_12 not in cur:
            raise ValueError(f'{r["reference_month"]}: t-12 absent on same release-date vintage')
        if k_t in prev:
            raise ValueError(f'{r["reference_month"]}: current reference month already present one day before release; availability semantics ambiguous')
        idx_t=cur[k_t]; idx_12=cur[k_12]; yoy=canonical_yoy(idx_t,idx_12)
        rows.append({
          'reference_month':r['reference_month'],'release_date':r['release_date'],'release_time':'08:30',
          'release_timezone':'America/New_York','eligible_date':r['release_date'],'series_id':SERIES,
          'index_t':idx_t,'index_t_minus_12':idx_12,'cpi_yoy':yoy,'vintage_date':release.isoformat(),
          'prior_vintage_date':prior.isoformat(),'release_day_ref_present':True,'day_before_ref_present':False,
          'availability_status':'AVAILABLE_STRICT_PIT','alfred_release_url':url_cur,
          'alfred_release_sha256':hashlib.sha256(raw_cur).hexdigest(),'alfred_prior_url':url_prev,
          'alfred_prior_sha256':hashlib.sha256(raw_prev).hexdigest(),'bls_release_url':r['source_url'],
          'bls_release_sha256':r['source_sha256'],
        })
        materialized+=1
        if i<EXPECTED: time.sleep(0.35)
    semantic=[{k:v for k,v in x.items() if k not in {'alfred_release_url','alfred_release_sha256','alfred_prior_url','alfred_prior_sha256','bls_release_url','bls_release_sha256','bls_gap_evidence_url','bls_gap_evidence_sha256'}} for x in rows]
    sha=hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {
      'schema':'GMFQ_USD_INFLATION_ALFRED_RELEASE_PIT_V1',
      'status':'CERTIFIABLE_STRICT_PIT_WITH_OFFICIAL_GAP',
      'authority_value_archive':'Federal Reserve Bank of St. Louis ALFRED',
      'authority_release_calendar':'U.S. Bureau of Labor Statistics','series_id':SERIES,
      'canonical_derivation':'cpi_yoy = 100 * (CPIAUCSL_t / CPIAUCSL_t_minus_12 - 1), both indexes from same official-release-date ALFRED vintage; official nonpublication remains null',
      'coverage':{'start':'2018-01','end':'2026-08','expected_rows':EXPECTED,'observed_rows':len(rows),'materialized_rows':materialized,'official_unavailable_rows':unavailable},
      'availability_semantics':{
        'official_release_timestamp':'08:30 America/New_York on BLS release date',
        'alfred_vintage_granularity':'calendar date','release_day_reference_month_must_exist_for_published_rows':True,
        'day_before_reference_month_must_not_exist_for_published_rows':True,'official_nonpublication_is_explicit_unavailable':True,
        'imputation_for_official_gap_forbidden':True,'mixed_vintage_derivation_forbidden':True,
        'current_revised_history_substitution_forbidden':True,
      },
      'semantic_sha256':sha,'rows':rows,
      'policy':{'authorizes_pr123_performance_by_itself':False,'production_write':False}
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--release-calendar',required=True,type=pathlib.Path); ap.add_argument('--output',required=True,type=pathlib.Path); a=ap.parse_args()
    calendar=json.loads(a.release_calendar.read_text(encoding='utf-8'))
    rows=validate_calendar(calendar); result=materialize(rows)
    if result['coverage']['observed_rows']!=EXPECTED or result['coverage']['official_unavailable_rows']!=1:
        raise ValueError('unexpected PIT materialization coverage')
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2,sort_keys=True))

if __name__=='__main__': main()
