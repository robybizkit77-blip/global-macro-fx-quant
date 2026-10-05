#!/usr/bin/env python3
from __future__ import annotations
import json, pathlib, re, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
FILES={
 'heatmap':ROOT/'live_data'/'sections'/'MACRO_THERMOMETER_DATA.json',
 'engine':ROOT/'live_data'/'sections'/'D.json',
 'series':ROOT/'live_data'/'sections'/'MACRO_SERIES.json',
}
TARGETS=('JP_UNEMP_RATE','disoccupazione','unemployment','unemp','2.4','2026-07','JPY','Japan')

def walk(x,path=''):
    out=[]
    if isinstance(x,dict):
        for k,v in x.items():
            p=f'{path}.{k}' if path else str(k)
            if isinstance(v,(dict,list)): out.extend(walk(v,p))
            else: out.append((p,v))
    elif isinstance(x,list):
        for i,v in enumerate(x):
            p=f'{path}[{i}]'
            if isinstance(v,(dict,list)): out.extend(walk(v,p))
            else: out.append((p,v))
    return out

def relevant(path,val):
    s=(path+' '+str(val)).lower()
    return any(t.lower() in s for t in TARGETS)

def main():
    report={'status':'PASS','target':'JPY labour / unemployment','files':{}}
    for name,p in FILES.items():
        data=json.loads(p.read_text())
        hits=[]
        for path,val in walk(data):
            if relevant(path,val): hits.append({'path':path,'value':val})
        report['files'][name]={'path':str(p.relative_to(ROOT)),'hits':hits[:500],'hit_count':len(hits)}
    # Canonical heatmap target must exist exactly.
    heat=json.loads(FILES['heatmap'].read_text())
    j=heat['currencies']['JPY']['labour']
    report['canonical_heatmap']={k:j.get(k) for k in ['series_id','source','frequency','transformation','latest_value','as_of','percentile','temperature_score','temperature_label','direction','acceleration']}
    if j.get('series_id')!='JP_UNEMP_RATE': raise SystemExit('unexpected JPY labour series id')
    if float(j.get('latest_value'))!=2.4: raise SystemExit('unexpected current JPY labour value')
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0
if __name__=='__main__': sys.exit(main())
