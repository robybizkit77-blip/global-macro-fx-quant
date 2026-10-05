#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, sys
from datetime import date

ROOT=pathlib.Path(__file__).resolve().parents[1]
HEAT=ROOT/'live_data'/'sections'/'MACRO_THERMOMETER_DATA.json'
SERIES=ROOT/'live_data'/'sections'/'MACRO_SERIES.json'
D=ROOT/'live_data'/'sections'/'D.json'
EXPECTED=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']
DIMS=['inflation','labour']

def ym(v):
    if not v: return None
    s=str(v)[:7]
    try:
        y,m=map(int,s.split('-')); return y,m
    except Exception: return None

def month_gap(audit_date, as_of):
    x=ym(as_of)
    if not x: return None
    y,m=x; return (audit_date.year-y)*12+(audit_date.month-m)

def walk_strings(x,out):
    if isinstance(x,dict):
        for k,v in x.items():
            if isinstance(k,str): out.add(k)
            walk_strings(v,out)
    elif isinstance(x,list):
        for v in x: walk_strings(v,out)
    elif isinstance(x,str): out.add(x)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--audit-date',default='2026-10-05')
    ap.add_argument('--output')
    a=ap.parse_args()
    audit_date=date.fromisoformat(a.audit_date)
    heat=json.loads(HEAT.read_text())
    macro_series=json.loads(SERIES.read_text())
    d=json.loads(D.read_text())
    strings=set(); walk_strings(macro_series,strings)
    currencies=heat.get('currencies') or {}
    if sorted(currencies)!=sorted(EXPECTED):
        raise SystemExit(f'currency coverage mismatch: {sorted(currencies)}')
    rows=[]; old=[]; missing=[]; series_links=[]
    for c in EXPECTED:
        node=currencies[c]
        for dim in DIMS:
            s=node.get(dim)
            if not isinstance(s,dict):
                missing.append(f'{c}:{dim}'); continue
            asof=s.get('as_of') or (node.get('as_of_detail') or {}).get('unemployment' if dim=='labour' else 'inflation')
            gap=month_gap(audit_date,asof)
            sid=s.get('series_id')
            row={
                'currency':c,'dimension':dim,'label':s.get('label'),'series_id':sid,
                'source':s.get('source'),'frequency':s.get('frequency'),'transformation':s.get('transformation'),
                'as_of':asof,'latest_value':s.get('latest_value'),'history_points':len(s.get('history') or []),
                'month_gap':gap,'validation':s.get('validation'),
                'series_id_seen_in_macro_series': bool(sid and sid in strings),
            }
            rows.append(row)
            if gap is None or gap>2: old.append(f'{c}:{dim}')
            if row['series_id_seen_in_macro_series']: series_links.append(f'{c}:{dim}')
    # D presence is structural only: we do not infer semantic mappings here.
    d_text=json.dumps(d,separators=(',',':'))
    d_currency_presence={c:(f'"{c}"' in d_text) for c in EXPECTED}
    out={
        'schema_version':'GMFQ_MACRO_INVENTORY_V1','audit_date':a.audit_date,'status':'PASS' if not missing else 'FAIL',
        'scope':{'currencies':EXPECTED,'dimensions':DIMS,'expected_series_count':16,'observed_series_count':len(rows)},
        'rows':rows,
        'summary':{
            'missing_series':missing,
            'older_than_2_calendar_months':old,
            'series_ids_seen_in_macro_series':series_links,
            'unique_sources':sorted({str(r['source']) for r in rows}),
            'd_currency_presence':d_currency_presence,
        },
        'policy_note':'Inventory only. month_gap is descriptive and does not by itself declare a release stale; external source/release-calendar checks are required before UPDATE_AVAILABLE.'
    }
    txt=json.dumps(out,indent=2,ensure_ascii=False)
    if a.output: pathlib.Path(a.output).write_text(txt+'\n')
    print(txt)
    if missing: return 2
    return 0
if __name__=='__main__': sys.exit(main())
