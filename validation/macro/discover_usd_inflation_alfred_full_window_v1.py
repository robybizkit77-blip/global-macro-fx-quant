#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,io,json,pathlib,time,urllib.parse,urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta

BASE='https://alfred.stlouisfed.org/graph/alfredgraph.csv'
SERIES='CPIAUCSL'
VINTAGES=['2018-03-15','2020-03-15','2022-03-15','2024-03-15','2026-03-15']
UA='GLOBAL-MACRO-FX-QUANT USD inflation ALFRED temporal discovery v1'


def bounded_window(vintage:str)->tuple[str,str]:
    end=date.fromisoformat(vintage)
    # Two years is sufficient for discovery and for a 12-month YoY check while
    # avoiding a full-history download for every historical vintage.
    start=end-timedelta(days=730)
    return start.isoformat(),end.isoformat()


def fetch(vintage:str):
    start,end=bounded_window(vintage)
    params={'id':SERIES,'vintage_date':vintage,'cosd':start,'coed':end}
    url=BASE+'?'+urllib.parse.urlencode(params)
    last_error=None
    raw=None
    for attempt in range(1,4):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/csv,*/*;q=0.8'})
            with urllib.request.urlopen(req,timeout=25) as r:
                raw=r.read()
            break
        except Exception as exc:
            last_error=exc
            if attempt<3:
                time.sleep(2**attempt)
    if raw is None:
        raise RuntimeError(f'ALFRED fetch failed for {vintage} after 3 attempts: {last_error!r}')

    text=raw.decode('utf-8-sig')
    rows=list(csv.reader(io.StringIO(text)))
    if len(rows)<2 or len(rows[0])<2:
        raise ValueError(f'invalid ALFRED CSV for {vintage}')
    header=rows[0]
    if header[0].lower() not in {'observation_date','date'}:
        raise ValueError(f'unexpected date column for {vintage}: {header}')
    values=[]
    for row in rows[1:]:
        if len(row)<2: continue
        d,v=row[0].strip(),row[1].strip()
        if not d or not v or v=='.': continue
        try: x=float(v)
        except ValueError: continue
        values.append((d,x))
    if not values:
        raise ValueError(f'no numeric observations for {vintage}')
    latest=max(values,key=lambda x:x[0])
    if latest[0] > vintage:
        raise ValueError(f'look-ahead: latest observation {latest[0]} after vintage {vintage}')
    return {
      'vintage_date':vintage,'query_start':start,'query_end':end,'url':url,
      'http_sha256':hashlib.sha256(raw).hexdigest(),
      'header':header,'observation_count':len(values),'first_observation':min(values,key=lambda x:x[0])[0],
      'latest_observation':latest[0],'latest_value':latest[1]
    }


def probe_all()->list[dict]:
    # Independent vintages are I/O-bound and may be slow at the ALFRED graph
    # endpoint. Parallel probing shortens discovery without changing semantics.
    with ThreadPoolExecutor(max_workers=len(VINTAGES)) as pool:
        probes=list(pool.map(fetch,VINTAGES))
    return sorted(probes,key=lambda x:x['vintage_date'])


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); a=ap.parse_args()
    probes=probe_all()
    out={
      'schema':'GMFQ_USD_INFLATION_ALFRED_FULL_WINDOW_DISCOVERY_V1',
      'status':'DISCOVERY_PASS',
      'authority':'Federal Reserve Bank of St. Louis ALFRED; underlying CPI source U.S. Bureau of Labor Statistics',
      'series_id':SERIES,
      'purpose':'Test key-free single-vintage retrieval for point-in-time USD inflation reconstruction.',
      'probes':probes,
      'invariants':{
        'single_vintage_per_request':True,'bounded_observation_window':True,
        'parallel_transport_only_semantics_unchanged':True,
        'no_future_observation_dates':True,'production_write':False,
        'changes_live_data':False,'changes_engine_rules':False
      }
    }
    raw=json.dumps(out,sort_keys=True,separators=(',',':')).encode(); out['semantic_sha256']=hashlib.sha256(raw).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))
if __name__=='__main__': main()
