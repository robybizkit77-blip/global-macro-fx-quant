#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,io,json,urllib.parse,urllib.request
from datetime import datetime,date
from pathlib import Path

DEFAULT_RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
SERIES_KEY='BSI.M.U2.Y.V.M30.X.1.U2.2300.Z01.E'
API_KEY=SERIES_KEY.removeprefix('BSI.')
BASE=f'https://data-api.ecb.europa.eu/service/data/BSI/{API_KEY}'
TOL=1e-6

def norm_month(v):
    if isinstance(v,(datetime,date)): return v.strftime('%Y-%m')
    s=str(v or '').strip()
    for fmt in ('%Y-%m-%d','%Y-%m','%d/%m/%Y','%m/%d/%Y'):
        try: return datetime.strptime(s,fmt).strftime('%Y-%m')
        except ValueError: pass
    if len(s)>=7 and s[:4].isdigit() and s[4]=='-' and s[5:7].isdigit(): return s[:7]
    raise SystemExit(f'invalid month: {v!r}')

def next_month(v):
    y,m=map(int,norm_month(v).split('-'))
    return f'{y+1:04d}-01' if m==12 else f'{y:04d}-{m+1:02d}'

def fetch_official(start_period):
    url=BASE+'?'+urllib.parse.urlencode({'format':'csvdata','startPeriod':start_period})
    req=urllib.request.Request(url,headers={'User-Agent':'global-macro-fx-quant/1.0','Accept':'text/csv,application/vnd.sdmx.data+csv;version=2.0.0'})
    with urllib.request.urlopen(req,timeout=60) as r:
        rows=list(csv.DictReader(io.StringIO(r.read().decode('utf-8-sig'))))
    if not rows: raise SystemExit('ECB EUR M3 exact series returned no rows')
    obs={}; meta=None
    for row in rows:
        key=str(row.get('KEY') or '').strip()
        if key and key!=SERIES_KEY: raise SystemExit(f'unexpected ECB EUR M3 series key: {key}')
        p=str(row.get('TIME_PERIOD') or '').strip()
        raw=row.get('OBS_VALUE')
        if not p or raw in (None,''): continue
        m=norm_month(p); obs[m]=float(raw)
        if meta is None: meta={k:v for k,v in row.items() if k not in {'TIME_PERIOD','OBS_VALUE'} and v not in (None,'')}
    if not obs: raise SystemExit('ECB EUR M3 exact series returned no numeric observations')
    return meta or {},obs,url

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--runtime',default=str(DEFAULT_RUNTIME)); ap.add_argument('--out'); args=ap.parse_args()
    payload=json.loads(Path(args.runtime).read_text(encoding='utf-8')); lane=payload['EUR']['money']
    raw_dates=list(lane.get('dates') or []); values=[float(x) for x in lane.get('values') or []]
    dates=[norm_month(x) for x in raw_dates]
    if not dates or len(dates)!=len(values): raise SystemExit('invalid EUR.money runtime arrays')
    runtime_last=dates[-1]
    if lane.get('last_date') is not None and norm_month(lane.get('last_date'))!=runtime_last: raise SystemExit('EUR.money runtime last_date inconsistency')
    if lane.get('last_value') is not None and abs(values[-1]-float(lane.get('last_value')))>TOL: raise SystemExit('EUR.money runtime last_value inconsistency')
    runtime=dict(zip(dates,values))
    start_year=max(2000,int(runtime_last[:4])-2)
    meta,official,url=fetch_official(f'{start_year:04d}-01')
    common=sorted(set(runtime)&set(official))
    if len(common)<12: raise SystemExit(f'insufficient EUR.money overlap: {len(common)}')
    exact=0; mism=[]
    for dt in common:
        diff=runtime[dt]-official[dt]
        if abs(diff)<=TOL: exact+=1
        else: mism.append({'date':dt,'runtime':runtime[dt],'official':official[dt],'diff':diff})
    if runtime_last not in official: raise SystemExit('official EUR M3 source missing runtime last month')
    new_dates=sorted(dt for dt in official if dt>runtime_last)
    expected=next_month(runtime_last); new=[]
    for dt in new_dates:
        if dt!=expected: raise SystemExit(f'non-contiguous EUR M3 month: got {dt}, expected {expected}')
        new.append({'date':dt,'value':official[dt]}); expected=next_month(dt)
    latest=max(official)
    result={'schema':'GMFQ_LIQUIDITY_EUR_M3_REVISION_AWARE_CANDIDATE_V1','status':'GREEN_SOURCE_CANDIDATE_ONLY','source':{'publisher':'European Central Bank / ESCB','dataset':'BSI','series_key':SERIES_KEY,'frequency':meta.get('FREQ') or 'Monthly','unit':meta.get('UNIT'),'title':meta.get('TITLE'),'title_complete':meta.get('TITLE_COMPL'),'url':url},'runtime':{'lane':'EUR.money','count':len(dates),'last_date':runtime_last,'last_value':values[-1]},'proof':{'revision_aware_append_only':True,'historical_runtime_values_frozen':True,'identity_transform_for_new_observations':True,'overlap_count':len(common),'exact_match_count':exact,'exact_match_ratio':exact/len(common),'revision_mismatch_count':len(mism),'revision_mismatches':mism,'runtime_last_official_value_current_vintage':official[runtime_last],'runtime_last_current_vintage_diff':values[-1]-official[runtime_last]},'latest_date':latest,'latest_value':official[latest],'new_observations':new,'candidate_update_available':bool(new),'candidate_pipeline_ready':True,'runtime_mutated':False,'publication_performed':False}
    text=json.dumps(result,indent=2,ensure_ascii=False)
    if args.out: Path(args.out).write_text(text+'\n',encoding='utf-8')
    else: print(text)
if __name__=='__main__': main()
