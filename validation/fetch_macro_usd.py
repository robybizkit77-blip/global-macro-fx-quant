#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, pathlib, sys, time, urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[1]
CURRENT=ROOT/'live_data'/'sections'/'MACRO_THERMOMETER_DATA.json'
BASE='https://fred.stlouisfed.org/graph/fredgraph.csv?id={}'

def fetch_series(series_id):
    url=BASE.format(series_id)
    last=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'GMFQ-Macro-Audit/1.0'})
            with urllib.request.urlopen(req,timeout=45) as r:
                text=r.read().decode('utf-8-sig')
            rows=list(csv.DictReader(io.StringIO(text)))
            out=[]
            for row in rows:
                dt=row.get('observation_date') or row.get('DATE') or row.get('date')
                raw=row.get(series_id)
                try: val=float(raw)
                except Exception: continue
                if dt: out.append((dt,val))
            if out: return out
            raise ValueError('empty series '+series_id)
        except Exception as e:
            last=e
            if attempt<2: time.sleep(2*(attempt+1))
    raise last

def main():
    cpi=fetch_series('CPIAUCSL'); un=fetch_series('UNRATE')
    if len(cpi)<13 or not un: raise SystemExit('insufficient FRED data')
    cpi_by_date=dict(cpi); cpi_date,cpi_idx=cpi[-1]
    y,m,_=map(int,cpi_date.split('-')); prev=f'{y-1:04d}-{m:02d}-01'
    if prev not in cpi_by_date: raise SystemExit('missing CPI year-ago observation '+prev)
    yoy=(cpi_idx/cpi_by_date[prev]-1)*100
    un_date,un_val=un[-1]
    cur=json.loads(CURRENT.read_text())['currencies']['USD']
    ci=cur['inflation']; cl=cur['labour']
    cpi_current_date=str(ci.get('as_of')); un_current_date=str(cl.get('as_of'))
    cpi_state='UPDATE_AVAILABLE' if cpi_date>cpi_current_date else ('NO_CHANGE' if cpi_date==cpi_current_date else 'SOURCE_BEHIND_CURRENT')
    un_state='UPDATE_AVAILABLE' if un_date>un_current_date else ('NO_CHANGE' if un_date==un_current_date else 'SOURCE_BEHIND_CURRENT')
    cpi_drift=abs(float(ci['latest_value'])-yoy) if cpi_date==cpi_current_date else None
    un_drift=abs(float(cl['latest_value'])-un_val) if un_date==un_current_date else None
    if cpi_drift is not None and cpi_drift>0.02: cpi_state='VALUE_DRIFT_SAME_DATE'
    if un_drift is not None and un_drift>1e-9: un_state='VALUE_DRIFT_SAME_DATE'
    out={'status':'PASS','currency':'USD','authority':'FRED transport / BLS underlying source','series':{
      'inflation':{'series_id':'CPIAUCSL','source_date':cpi_date,'index_value':cpi_idx,'year_ago_date':prev,'reported_transform':'yoy_pct_from_index','value':yoy,'current_as_of':cpi_current_date,'current_value':ci['latest_value'],'state':cpi_state,'same_date_abs_drift':cpi_drift},
      'labour':{'series_id':'UNRATE','source_date':un_date,'value':un_val,'current_as_of':un_current_date,'current_value':cl['latest_value'],'state':un_state,'same_date_abs_drift':un_drift}},
      'summary':{'updates_available':[k for k,v in [('inflation',cpi_state),('labour',un_state)] if v=='UPDATE_AVAILABLE'], 'blocking_states':[v for v in [cpi_state,un_state] if v not in ('NO_CHANGE','UPDATE_AVAILABLE')]}}
    print(json.dumps(out,indent=2,ensure_ascii=False)); return 0
if __name__=='__main__': sys.exit(main())
