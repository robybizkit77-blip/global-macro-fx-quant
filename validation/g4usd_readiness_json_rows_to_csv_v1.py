#!/usr/bin/env python3
"""Mechanical JSON-row -> source-schema CSV exporter for G4USD readiness.

This helper copies already-certified fields only. It does not derive macro values,
interpolate, impute, or inspect any backtest output.
"""
from __future__ import annotations

import argparse,csv,json,pathlib

MODES={
  'JPY_INFLATION': {
    'input_schema':'GMFQ_JPY_INFLATION_STRICT_PIT_EVIDENCE_V1_RUNTIME',
    'fields':['observation_date','release_date','value','availability_status'],
  },
  'USD_INFLATION': {
    'input_schema':'GMFQ_USD_INFLATION_ALFRED_RELEASE_PIT_V1',
    'fields':['reference_month','release_date','cpi_yoy','availability_status'],
  },
  'USD_LABOUR': {
    'input_schema':'GMFQ_USD_LABOUR_BLS_RELEASE_PIT_V1',
    'fields':['reference_month','release_date','unemployment_rate','availability_status'],
  },
}


def export(mode:str,src:pathlib.Path,dst:pathlib.Path)->dict:
    cfg=MODES[mode]
    d=json.loads(src.read_text(encoding='utf-8'))
    if d.get('schema')!=cfg['input_schema']:
        raise ValueError(f'{mode}: unexpected input schema {d.get("schema")!r}')
    rows=d.get('rows')
    if not isinstance(rows,list) or not rows:
        raise ValueError(f'{mode}: missing rows')
    out=[]
    for i,r in enumerate(rows,1):
        if mode=='JPY_INFLATION':
            vals={
              'observation_date':r.get('observation_date',''),
              'release_date':r.get('release_date',''),
              'value':r.get('value',''),
              'availability_status':'AVAILABLE_STRICT_PIT',
            }
            if not vals['observation_date'] or not vals['release_date'] or vals['value']=='' or vals['value'] is None:
                raise ValueError(f'{mode} row {i}: missing certified field')
        elif mode=='USD_INFLATION':
            status=r.get('availability_status','')
            vals={
              'reference_month':r.get('reference_month',''),
              'release_date':r.get('release_date') or '',
              'cpi_yoy':'' if r.get('cpi_yoy') is None else r.get('cpi_yoy'),
              'availability_status':status,
            }
            if status=='UNAVAILABLE_OFFICIAL_NOT_PUBLISHED':
                if vals['release_date'] or vals['cpi_yoy']!='':
                    raise ValueError(f'{mode} row {i}: official unavailable row carries value/date')
            elif status=='AVAILABLE_STRICT_PIT':
                if not vals['release_date'] or vals['cpi_yoy']=='':
                    raise ValueError(f'{mode} row {i}: available row missing value/date')
            else:
                raise ValueError(f'{mode} row {i}: unknown status {status!r}')
        else:
            status=r.get('availability_status','')
            vals={
              'reference_month':r.get('reference_month',''),
              'release_date':r.get('release_date') or '',
              'unemployment_rate':'' if r.get('unemployment_rate') is None else r.get('unemployment_rate'),
              'availability_status':status,
            }
            if status=='UNAVAILABLE_OFFICIAL_NOT_PUBLISHED':
                if vals['release_date'] or vals['unemployment_rate']!='':
                    raise ValueError(f'{mode} row {i}: official unavailable row carries value/date')
            elif status=='AVAILABLE_STRICT_PIT':
                if not vals['release_date'] or vals['unemployment_rate']=='':
                    raise ValueError(f'{mode} row {i}: available row missing value/date')
            else:
                raise ValueError(f'{mode} row {i}: unknown status {status!r}')
        out.append(vals)
    dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=cfg['fields']); w.writeheader(); w.writerows(out)
    return {'mode':mode,'rows':len(out),'output':str(dst)}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--mode',required=True,choices=sorted(MODES)); ap.add_argument('--input',required=True,type=pathlib.Path); ap.add_argument('--output',required=True,type=pathlib.Path)
    a=ap.parse_args(); print(json.dumps(export(a.mode,a.input,a.output),sort_keys=True))

if __name__=='__main__': main()
