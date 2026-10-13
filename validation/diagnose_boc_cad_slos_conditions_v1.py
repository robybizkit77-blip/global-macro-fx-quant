#!/usr/bin/env python3
import json
import math
import re
import urllib.request
from pathlib import Path
from datetime import datetime

RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
CATALOG_URL = 'https://www.bankofcanada.ca/valet/lists/series/json'
OBS_URL = 'https://www.bankofcanada.ca/valet/observations/{series}/json?start_date=2015-01-01'
UA = 'GMFQ-CAD-SLOS-diagnostic/1.0'
TERMS = (
    'senior loan officer', 'loan officer survey', 'lending conditions',
    'business lending', 'credit conditions', 'lending standards',
    'balance of opinion', 'business loans'
)


def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def flatten(x):
    if isinstance(x, dict):
        return ' '.join(flatten(v) for v in x.values())
    if isinstance(x, list):
        return ' '.join(flatten(v) for v in x)
    return str(x or '')


def runtime_row():
    d = json.loads(RUNTIME.read_text(encoding='utf-8'))
    row = d['CAD']['conditions']
    pts = []
    for ds, v in zip(row.get('dates') or [], row.get('values') or []):
        pts.append((str(ds), float(v)))
    return row, pts


def parse_obs(payload, sid):
    out=[]
    for o in payload.get('observations') or []:
        ds=o.get('d')
        c=o.get(sid) or {}
        raw=c.get('v') if isinstance(c,dict) else c
        if ds is None or raw in (None,''):
            continue
        try: val=float(raw)
        except Exception: continue
        if math.isfinite(val): out.append((str(ds),val))
    return out


def canon_period(ds):
    s=str(ds)
    # monthly/quarterly runtime dates are matched by calendar period when exact day differs.
    try:
        dt=datetime.strptime(s[:10],'%Y-%m-%d')
        return f'{dt.year:04d}-{dt.month:02d}'
    except Exception:
        pass
    m=re.match(r'^(\d{4})[- ]?Q([1-4])$',s,re.I)
    if m:
        y,q=int(m.group(1)),int(m.group(2)); return f'{y:04d}-{(q-1)*3+1:02d}'
    if re.match(r'^\d{4}-\d{2}$',s): return s
    return s


def aggregate_latest_by_period(obs):
    out={}
    for ds,v in obs:
        p=canon_period(ds)
        out[p]=(ds,v)
    return out


def score(rt, obs, mult=1.0, sign=1.0):
    src=aggregate_latest_by_period(obs)
    pairs=[]
    for ds,rv in rt:
        p=canon_period(ds)
        if p not in src: continue
        ods,ov=src[p]; sv=sign*mult*ov; diff=rv-sv
        pairs.append((p,rv,sv,diff,abs(diff),ods))
    exact=sum(1 for x in pairs if x[4] <= 1e-9)
    mae=sum(x[4] for x in pairs)/len(pairs) if pairs else None
    mx=max((x[4] for x in pairs),default=None)
    return {
        'overlap':len(pairs),'exact':exact,'exact_ratio':exact/len(pairs) if pairs else 0.0,
        'mae':mae,'max_abs_diff':mx,
        'first':None if not pairs else {'period':pairs[0][0],'runtime':pairs[0][1],'source':pairs[0][2],'source_date':pairs[0][5]},
        'last':None if not pairs else {'period':pairs[-1][0],'runtime':pairs[-1][1],'source':pairs[-1][2],'source_date':pairs[-1][5]},
    }


def main():
    row,rt=runtime_row()
    catalog=get_json(CATALOG_URL).get('series') or {}
    candidates=[]
    for sid,meta in catalog.items():
        txt=(str(sid)+' '+flatten(meta)).lower()
        hits=[t for t in TERMS if t in txt]
        if hits: candidates.append((str(sid),meta,hits))

    results=[]
    transforms=[(1.0,1.0),(1.0,-1.0),(100.0,1.0),(100.0,-1.0),(0.01,1.0),(0.01,-1.0)]
    for sid,meta,hits in candidates:
        try:
            obs=parse_obs(get_json(OBS_URL.format(series=sid)),sid)
            variants=[]
            for mult,sign in transforms:
                sc=score(rt,obs,mult,sign)
                variants.append({'multiplier':mult,'sign':sign,**sc})
            best=sorted(variants,key=lambda x:(-x['exact_ratio'], x['mae'] if x['mae'] is not None else float('inf'),-x['overlap']))[0]
            results.append({'series_id':sid,'metadata':meta,'term_hits':hits,'observation_count':len(obs),'best_transform':best,'all_transforms':variants})
        except Exception as exc:
            results.append({'series_id':sid,'metadata':meta,'term_hits':hits,'error':f'{type(exc).__name__}: {exc}'})

    ranked=sorted([r for r in results if 'best_transform' in r],key=lambda r:(-r['best_transform']['exact_ratio'], r['best_transform']['mae'] if r['best_transform']['mae'] is not None else float('inf'),-r['best_transform']['overlap']))
    full=[r for r in ranked if r['best_transform']['overlap']==len(rt) and r['best_transform']['exact']==len(rt)]
    out={
        'schema':'GMFQ_LIQUIDITY_CAD_SLOS_MAPPING_DIAGNOSTIC_V1',
        'source':{'publisher':'Bank of Canada','transport':'Valet API catalog + observations'},
        'runtime':{'lane':'CAD.conditions','label':row.get('label'),'count':len(rt),'first_date':rt[0][0] if rt else None,'last_date':rt[-1][0] if rt else None,'last_value':rt[-1][1] if rt else None},
        'catalog_candidate_count':len(candidates),'tested_candidate_count':len(results),
        'best_candidate':ranked[0] if ranked else None,
        'full_exact_match_count':len(full),'full_exact_matches':full,
        'top_candidates':ranked[:12],
        'runtime_match_certified':len(full)==1,
        'automation_ready':False,'promotion_performed':False,'runtime_mutated':False,'publication_performed':False
    }
    print(json.dumps(out,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
