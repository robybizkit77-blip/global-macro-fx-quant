#!/usr/bin/env python3
"""Materialize USD inflation and labour PIT-compatible CSVs from certified canonical macro series.
Fail closed if required canonical series are absent. This is a read-only extractor.
"""
import argparse,csv,json
from pathlib import Path

def find_series(obj, needle):
    out=[]
    def walk(x):
        if isinstance(x,dict):
            if str(x.get('id',''))==needle or str(x.get('series_id',''))==needle or str(x.get('macro_series_id',''))==needle:
                out.append(x)
            for v in x.values(): walk(v)
        elif isinstance(x,list):
            for v in x: walk(v)
    walk(obj); return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--inflation-csv',required=True); ap.add_argument('--labour-csv',required=True); a=ap.parse_args()
    obj=json.loads(Path('live_data/sections/MACRO_SERIES.json').read_text())
    # Use canonical USD heatmap-compatible histories and their stored dates/values.
    inf=find_series(obj,'US_CPIAUCSL_history_value')
    lab=find_series(obj,'US_UNRATE_history_value')
    if not inf or not lab: raise SystemExit('required USD canonical macro histories unavailable')
    def extract(node,valname):
        rows=[]
        seq=node[0].get('history') or node[0].get('values') or node[0].get('data') or []
        for r in seq:
            if isinstance(r,dict):
                d=r.get('date') or r.get('observation_date') or r.get('period')
                v=r.get('value')
                if d is not None and v is not None: rows.append((str(d)[:10],float(v)))
        if not rows: raise SystemExit(f'empty USD series {valname}')
        return rows
    infrows=extract(inf,'inflation'); labrows=extract(lab,'labour')
    with open(a.inflation_csv,'w',newline='') as f:
        w=csv.writer(f); w.writerow(['reference_month','release_date','cpi_yoy']);
        for d,v in infrows: w.writerow([d[:7],d,v])
    with open(a.labour_csv,'w',newline='') as f:
        w=csv.writer(f); w.writerow(['reference_month','release_date','unemployment_rate']);
        for d,v in labrows: w.writerow([d[:7],d,v])
    print(json.dumps({'usd_inflation_rows':len(infrows),'usd_labour_rows':len(labrows)}))
if __name__=='__main__': main()
