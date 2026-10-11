#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,io,json,pathlib,time,urllib.parse,urllib.request
from datetime import date,timedelta
import calendar

BASE='https://alfred.stlouisfed.org/graph/alfredgraph.csv'
SERIES='CPIAUCSL'
UA='GLOBAL-MACRO-FX-QUANT USD inflation ALFRED monthly decision grid v1'
START=(2018,3)
END=(2026,9)


def month_end(y:int,m:int)->date:
    return date(y,m,calendar.monthrange(y,m)[1])

def month_grid():
    y,m=START
    ey,em=END
    out=[]
    while (y,m) <= (ey,em):
        out.append(month_end(y,m))
        m += 1
        if m==13:
            y += 1; m=1
    return out

def fetch(vintage:date):
    start=vintage-timedelta(days=760)
    params={'id':SERIES,'vintage_date':vintage.isoformat(),'cosd':start.isoformat(),'coed':vintage.isoformat()}
    url=BASE+'?'+urllib.parse.urlencode(params)
    raw=None; last=None
    for attempt,wait in enumerate((0,2,5,10),start=1):
        if wait: time.sleep(wait)
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/csv,*/*;q=0.8','Connection':'close'})
            with urllib.request.urlopen(req,timeout=60) as r: raw=r.read()
            break
        except Exception as exc:
            last=exc
    if raw is None: raise RuntimeError(f'fetch failed {vintage}: {last!r}')
    rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig'))))
    if len(rows)<2 or len(rows[0])<2: raise ValueError(f'invalid csv {vintage}')
    vals=[]
    for row in rows[1:]:
        if len(row)<2: continue
        d,v=row[0].strip(),row[1].strip()
        if not d or not v or v=='.': continue
        try: x=float(v)
        except ValueError: continue
        vals.append((d,x))
    if not vals: raise ValueError(f'no values {vintage}')
    latest=max(vals,key=lambda z:z[0])
    if latest[0] > vintage.isoformat(): raise ValueError(f'lookahead {vintage}: {latest[0]}')
    return {
      'decision_date':vintage.isoformat(),
      'latest_observation_date':latest[0],
      'latest_value':latest[1],
      'observation_count':len(vals),
      'http_sha256':hashlib.sha256(raw).hexdigest(),
      'url':url,
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); a=ap.parse_args()
    rows=[]; errors=[]
    for i,d in enumerate(month_grid(),start=1):
        try:
            rows.append(fetch(d))
        except Exception as exc:
            errors.append({'decision_date':d.isoformat(),'error':repr(exc)})
            break
        time.sleep(0.35)
    status='DISCOVERY_PASS' if len(rows)==len(month_grid()) and not errors else 'DISCOVERY_FAIL'
    semantic_rows=[{k:v for k,v in r.items() if k not in {'http_sha256','url'}} for r in rows]
    semantic_sha=hashlib.sha256(json.dumps(semantic_rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    out={
      'schema':'GMFQ_USD_INFLATION_ALFRED_MONTHLY_DECISION_GRID_V1',
      'status':status,
      'series_id':SERIES,
      'grid_start':month_grid()[0].isoformat(),
      'grid_end':month_grid()[-1].isoformat(),
      'expected_months':len(month_grid()),
      'observed_months':len(rows),
      'semantic_sha256':semantic_sha,
      'rows':rows,
      'errors':errors,
      'research_use':'transport_and_vintage_semantics_only; does not authorize PR123 conditional performance',
      'invariants':{
        'one_vintage_query_per_decision_date':True,
        'no_future_observation_dates':True,
        'current_revised_history_substitution_forbidden':True,
        'production_write':False,
        'changes_pr123_contract':False
      }
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2,sort_keys=True))
    if status!='DISCOVERY_PASS': raise SystemExit(2)

if __name__=='__main__': main()
