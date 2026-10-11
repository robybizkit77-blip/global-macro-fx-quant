#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import math
import pathlib
import urllib.parse
import urllib.request
from datetime import date

CONTRACT = pathlib.Path('validation/COT_FLOW_FX_PRICE_SOURCE_CONTRACT_V1_2026-10-11.json')
START = '2018-01-01'

def fetch_series(series_id: str):
    params=urllib.parse.urlencode({'id':series_id,'cosd':START})
    url='https://fred.stlouisfed.org/graph/fredgraph.csv?'+params
    req=urllib.request.Request(url,headers={'User-Agent':'GMFQ-COT-PIT-Research/1.0'})
    with urllib.request.urlopen(req,timeout=45) as r:
        raw=r.read().decode('utf-8')
    rows=[]
    reader=csv.reader(io.StringIO(raw))
    header=next(reader)
    assert len(header)>=2, header
    for rec in reader:
        if len(rec)<2: continue
        ds=rec[0].strip(); vs=rec[1].strip()
        if not ds or not vs or vs in {'.','NA','NaN'}: continue
        try: v=float(vs)
        except ValueError: continue
        if not math.isfinite(v): continue
        rows.append((date.fromisoformat(ds),v))
    return url,rows

def main():
    c=json.loads(CONTRACT.read_text())
    gate=c['readiness_gate']
    diagnostics={}
    latest=[]
    all_pass=True
    for ccy,spec in c['series'].items():
        url,rows=fetch_series(spec['fred_id'])
        values=[v for _,v in rows]
        first=rows[0][0] if rows else None
        last=rows[-1][0] if rows else None
        transformed=[v if spec['transform_to_local_currency_vs_usd']=='identity' else 1.0/v for v in values]
        checks={
          'nonempty': bool(rows),
          'first_nonmissing_on_or_before_gate': bool(first and first<=date.fromisoformat(gate['each_series_first_nonmissing_on_or_before'])),
          'minimum_nonmissing_observations': len(rows)>=gate['each_series_minimum_nonmissing_observations_2018_onward'],
          'native_positive': bool(values) and min(values)>0,
          'transformed_positive': bool(transformed) and min(transformed)>0,
          'explicit_transform': spec['transform_to_local_currency_vs_usd'] in {'identity','reciprocal'},
        }
        ok=all(checks.values())
        all_pass &= ok
        if last: latest.append(last)
        diagnostics[ccy]={
          'fred_id':spec['fred_id'],
          'url':url,
          'transform':spec['transform_to_local_currency_vs_usd'],
          'nonmissing_count':len(rows),
          'first_nonmissing':first.isoformat() if first else None,
          'latest_nonmissing':last.isoformat() if last else None,
          'checks':checks,
          'pass':ok,
        }
    common_latest=min(latest) if len(latest)==len(c['series']) else None
    common_pass=bool(common_latest and common_latest>=date.fromisoformat(gate['minimum_latest_common_nonmissing_date']))
    all_pass &= common_pass
    out={
      'schema':'GMFQ_COT_FLOW_FX_PRICE_READINESS_RECEIPT_V1',
      'status':'READY_FOR_RESULT_BLIND_EDGE_EXECUTION' if all_pass else 'BLOCKED_FX_PRICE_READINESS',
      'contract_schema':c['schema'],
      'series_count':len(c['series']),
      'common_latest_nonmissing_date':common_latest.isoformat() if common_latest else None,
      'common_latest_gate_pass':common_pass,
      'diagnostics':diagnostics,
      'edge_execution_authorized':all_pass,
      'production_signal_authorized':False,
      'sizing_authorized':False,
    }
    pathlib.Path('/tmp/cot-fx-price-readiness').mkdir(parents=True,exist_ok=True)
    pathlib.Path('/tmp/cot-fx-price-readiness/receipt.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out,indent=2,sort_keys=True))
    if not all_pass: raise SystemExit(2)

if __name__=='__main__': main()
