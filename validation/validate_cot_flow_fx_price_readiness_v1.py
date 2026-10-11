#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
import json
import math
import pathlib
import urllib.request
from datetime import date, datetime
from html.parser import HTMLParser

CONTRACT = pathlib.Path('validation/COT_FLOW_FX_PRICE_SOURCE_CONTRACT_V1_2026-10-11.json')
START = date(2018,1,1)

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.in_tr=False; self.in_cell=False; self.cell_tag=None; self.cell=[]; self.row=[]; self.rows=[]
    def handle_starttag(self, tag, attrs):
        t=tag.lower()
        if t=='tr': self.in_tr=True; self.row=[]
        elif t in {'td','th'} and self.in_tr:
            self.in_cell=True; self.cell_tag=t; self.cell=[]
    def handle_data(self, data):
        if self.in_cell: self.cell.append(data)
    def handle_endtag(self, tag):
        t=tag.lower()
        if self.in_cell and t==self.cell_tag:
            self.row.append(' '.join(''.join(self.cell).split())); self.in_cell=False; self.cell_tag=None
        elif t=='tr' and self.in_tr:
            if self.row: self.rows.append(self.row)
            self.in_tr=False

def parse_h10_html(raw:str):
    p=TableParser(); p.feed(raw)
    rows=[]
    for r in p.rows:
        if len(r)<2: continue
        ds=r[0].strip().upper(); vs=r[1].strip().upper()
        try: d=datetime.strptime(ds,'%d-%b-%y').date()
        except ValueError: continue
        if d<START or vs in {'ND','NA','N/A',''}: continue
        try: v=float(vs.replace(',',''))
        except ValueError: continue
        if math.isfinite(v): rows.append((d,v))
    rows.sort(key=lambda x:x[0])
    return rows

def fetch_one(item):
    ccy,spec=item
    url=spec['board_history_url']
    req=urllib.request.Request(url,headers={'User-Agent':'GMFQ-COT-PIT-Research/1.0'})
    with urllib.request.urlopen(req,timeout=45) as r:
        raw=r.read().decode('utf-8',errors='replace')
    return ccy,url,parse_h10_html(raw)

def main():
    c=json.loads(CONTRACT.read_text())
    gate=c['readiness_gate']
    diagnostics={}; latest=[]; all_pass=True
    data={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as ex:
        for ccy,url,rows in ex.map(fetch_one,c['series'].items()): data[ccy]=(url,rows)
    for ccy,spec in c['series'].items():
        url,rows=data[ccy]
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
        ok=all(checks.values()); all_pass &= ok
        if last: latest.append(last)
        diagnostics[ccy]={
          'fred_id_identity':spec['fred_id'],
          'board_history_url':url,
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
      'transport':'parallel direct Federal Reserve H.10 country historical pages',
      'common_latest_nonmissing_date':common_latest.isoformat() if common_latest else None,
      'common_latest_gate_pass':common_pass,
      'diagnostics':diagnostics,
      'edge_execution_authorized':all_pass,
      'production_signal_authorized':False,
      'sizing_authorized':False,
    }
    outdir=pathlib.Path('/tmp/cot-fx-price-readiness'); outdir.mkdir(parents=True,exist_ok=True)
    (outdir/'receipt.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out,indent=2,sort_keys=True))
    if not all_pass: raise SystemExit(2)

if __name__=='__main__': main()
