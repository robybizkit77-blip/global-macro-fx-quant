#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
OUT=Path('validation/liquidity-eur-bls-conditions-diagnostic.json')
BASE='https://data-api.ecb.europa.eu/service/data/BLS'
UA='global-macro-fx-quant/1.0'


def qkey(v):
    s=str(v).strip()
    if '-Q' in s:
        return s[:7]
    if len(s)>=7 and s[4]=='-':
        return s[:7]
    return s


def fetch_all():
    qs=urllib.parse.urlencode({'format':'csvdata','startPeriod':'2016-Q1'})
    url=BASE+'?'+qs
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/csv,application/vnd.sdmx.data+csv;version=2.0.0'})
    with urllib.request.urlopen(req,timeout=120) as r:
        text=r.read().decode('utf-8-sig')
    rows=list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise SystemExit('ECB BLS returned no rows')
    return url,rows


def runtime_series():
    liq=json.loads(RUNTIME.read_text(encoding='utf-8'))
    row=liq['EUR']['conditions']
    dates=list(row.get('dates') or [])
    values=list(row.get('values') or [])
    if not dates or len(dates)!=len(values):
        raise SystemExit('invalid EUR.conditions runtime arrays')
    rt={qkey(d):float(v) for d,v in zip(dates,values)}
    return row,rt


def series_key(row):
    for k in ('KEY','SERIES_KEY','SERIES_CODE'):
        if row.get(k):
            return str(row[k])
    ignore={'TIME_PERIOD','OBS_VALUE','OBS_STATUS','OBS_CONF','OBS_PRE_BREAK','OBS_COM','TIME_FORMAT','TITLE','TITLE_COMPL','UNIT_INDEX_BASE'}
    parts=[]
    for k,v in row.items():
        if k in ignore or not v: continue
        if k.startswith('OBS_'): continue
        parts.append(f'{k}={v}')
    return '|'.join(parts)


def main():
    rtrow,rt=runtime_series()
    url,rows=fetch_all()
    grouped=defaultdict(dict)
    meta={}
    for row in rows:
        t=qkey(row.get('TIME_PERIOD') or '')
        raw=row.get('OBS_VALUE')
        if not t or raw in (None,''): continue
        try: val=float(raw)
        except ValueError: continue
        key=series_key(row)
        grouped[key][t]=val
        if key not in meta:
            meta[key]={k:v for k,v in row.items() if k not in {'TIME_PERIOD','OBS_VALUE'} and v not in (None,'')}
    results=[]
    for key,src in grouped.items():
        common=sorted(set(rt)&set(src))
        if len(common)<8: continue
        transforms=[]
        for sign in (1.0,-1.0):
            diffs=[rt[d]-sign*src[d] for d in common]
            exact=sum(abs(x)<=1e-6 for x in diffs)
            transforms.append({
                'sign':sign,'overlap':len(common),'exact':exact,'exact_ratio':exact/len(common),
                'mae':sum(abs(x) for x in diffs)/len(diffs),'max_abs_diff':max(abs(x) for x in diffs),
                'first_period':common[0],'last_period':common[-1],
                'runtime_last_value':rt[common[-1]],'source_last_value':sign*src[common[-1]],
            })
        best=min(transforms,key=lambda x:(-x['exact_ratio'],-x['overlap'],x['mae']))
        results.append({'series_key':key,'metadata':meta.get(key,{}),'best_transform':best})
    results.sort(key=lambda x:(-x['best_transform']['exact_ratio'],-x['best_transform']['overlap'],x['best_transform']['mae']))
    full=[r for r in results if r['best_transform']['overlap']==len(rt) and r['best_transform']['exact_ratio']==1.0]
    report={
        'schema':'GMFQ_LIQUIDITY_EUR_BLS_MAPPING_DIAGNOSTIC_V1',
        'status':'UNIQUE_FULL_EXACT_BLS_RUNTIME_MATCH_PROVEN' if len(full)==1 else ('AMBIGUOUS_FULL_EXACT_BLS_RUNTIME_MATCH' if len(full)>1 else 'WITHHELD_EXACT_BLS_SERIES_PENDING'),
        'source':{'publisher':'European Central Bank / ESCB','dataset':'BLS','url':url},
        'runtime':{'label':rtrow.get('label'),'count':len(rt),'first_period':min(rt),'last_period':max(rt),'last_value':float(rtrow.get('last_value'))},
        'downloaded_rows':len(rows),'candidate_series_count':len(results),
        'full_exact_match_count':len(full),'full_exact_matches':full[:10],
        'best_candidate':results[0] if results else None,'top_candidates':results[:20],
        'promotion_eligible':len(full)==1,'automation_ready':False,
        'runtime_mutated':False,'publication_performed':False,'bias_score_sizing_effect':'NONE'
    }
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
