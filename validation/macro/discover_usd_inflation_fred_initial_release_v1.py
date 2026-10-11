#!/usr/bin/env python3
"""Discover whether the official FRED API can return CPIAUCSL initial releases.

Uses output_type=4 (Initial Release Only) from the FRED/ALFRED observations API.
Read-only discovery. Requires FRED_API_KEY in the environment and never prints it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import urllib.parse
import urllib.request

API='https://api.stlouisfed.org/fred/series/observations'
SERIES='CPIAUCSL'
START='2017-01-01'  # include t-12 base for Jan 2018 YoY
END='2026-08-01'
UA='GLOBAL-MACRO-FX-QUANT USD inflation FRED initial-release discovery v1'


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); args=ap.parse_args()
    key=os.environ.get('FRED_API_KEY','').strip()
    if not key:
        out={'schema':'GMFQ_USD_INFLATION_FRED_INITIAL_RELEASE_DISCOVERY_V1','status':'DISCOVERY_FAIL','reason':'FRED_API_KEY_MISSING','production_write':False}
        args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
        print(json.dumps(out,indent=2,sort_keys=True)); return 2
    params={
        'series_id':SERIES,'api_key':key,'file_type':'json','output_type':'4',
        'observation_start':START,'observation_end':END,'sort_order':'asc','limit':'1000'
    }
    safe_params={k:v for k,v in params.items() if k!='api_key'}
    url=API+'?'+urllib.parse.urlencode(params)
    safe_url=API+'?'+urllib.parse.urlencode(safe_params)
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=60) as r:
            raw=r.read(); status_code=r.status
        payload=json.loads(raw)
        obs=[]
        for row in payload.get('observations',[]):
            d=str(row.get('date','')); v=str(row.get('value','')).strip()
            if not d or not v or v=='.': continue
            obs.append({
                'observation_date':d,'value':float(v),
                'realtime_start':str(row.get('realtime_start','')),
                'realtime_end':str(row.get('realtime_end','')),
            })
        by_date={r['observation_date']:r for r in obs}
        required_first='2017-01-01'; required_last='2026-08-01'
        status='DISCOVERY_PASS' if len(obs)>=116 and required_first in by_date and required_last in by_date else 'DISCOVERY_FAIL'
        out={
            'schema':'GMFQ_USD_INFLATION_FRED_INITIAL_RELEASE_DISCOVERY_V1','status':status,
            'authority':'Federal Reserve Bank of St. Louis FRED/ALFRED; underlying source U.S. Bureau of Labor Statistics',
            'series_id':SERIES,'api_output_type':4,'api_output_semantics':'INITIAL_RELEASE_ONLY',
            'query':safe_params,'safe_url':safe_url,'http_status':status_code,'raw_sha256':hashlib.sha256(raw).hexdigest(),
            'observation_count':len(obs),'first_observation':obs[0] if obs else None,'last_observation':obs[-1] if obs else None,
            'sample_anchors':[by_date.get(x) for x in ('2018-01-01','2022-01-01','2024-01-01','2026-08-01')],
            'invariants':{'api_key_redacted':True,'initial_release_only_requested':True,'production_write':False,'changes_live_data':False,'changes_engine_rules':False},
        }
    except Exception as exc:
        out={
            'schema':'GMFQ_USD_INFLATION_FRED_INITIAL_RELEASE_DISCOVERY_V1','status':'DISCOVERY_FAIL',
            'reason':'FRED_API_REQUEST_FAILED','error':repr(exc),'query':safe_params,'safe_url':safe_url,
            'invariants':{'api_key_redacted':True,'production_write':False},
        }
    semantic={k:v for k,v in out.items() if k!='raw_sha256'}
    out['semantic_sha256']=hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out,indent=2,sort_keys=True))
    return 0 if out['status']=='DISCOVERY_PASS' else 2

if __name__=='__main__': raise SystemExit(main())
