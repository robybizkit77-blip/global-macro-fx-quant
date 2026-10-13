#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
DEFAULT_OUT=Path('validation/liquidity-jpy-tankan-lending-attitude-candidate.json')
BASE='https://www.stat-search.boj.or.jp/api/v1/getDataCode'
DB='CO'
CODE='TK99F0000612GCQ00000'
EXPECTED_NAME='D.I./Lending Attitude/All Enterprises/All industries/Actual result'
EXPECTED_UNIT='% points'
EXPECTED_FREQUENCY='QUARTERLY'


def quarter_key(value: str) -> str:
    s=str(value)
    if '-Q' in s:
        y,q=s.split('-Q',1)
        y=int(y); q=int(q)
        if q not in (1,2,3,4):
            raise SystemExit(f'invalid quarterly date: {value!r}')
        return f'{y:04d}-Q{q}'
    digits=''.join(ch for ch in s if ch.isdigit())
    if len(digits)<6:
        raise SystemExit(f'invalid quarterly date: {value!r}')
    y=int(digits[:4]); p=int(digits[4:6])
    if p in (1,2,3,4):
        q=p
    elif p in (3,6,9,12):
        q=((p-1)//3)+1
    else:
        raise SystemExit(f'invalid quarterly date: {value!r}')
    return f'{y:04d}-Q{q}'


def fetch():
    qs=urllib.parse.urlencode({'format':'json','lang':'en','db':DB,'startDate':'201601','endDate':'202604','code':CODE})
    url=BASE+'?'+qs
    req=urllib.request.Request(url,headers={'User-Agent':'global-macro-fx-quant/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as r:
        payload=json.loads(r.read().decode('utf-8-sig'))
    if payload.get('STATUS')!=200 or len(payload.get('RESULTSET') or [])!=1:
        raise SystemExit(f'BOJ Tankan API contract failure: {payload}')
    row=payload['RESULTSET'][0]
    if row.get('SERIES_CODE')!=CODE:
        raise SystemExit(f'BOJ Tankan series code mismatch: {row}')
    if row.get('NAME_OF_TIME_SERIES')!=EXPECTED_NAME:
        raise SystemExit(f'BOJ Tankan series name mismatch: {row.get("NAME_OF_TIME_SERIES")!r}')
    if row.get('UNIT')!=EXPECTED_UNIT or row.get('FREQUENCY')!=EXPECTED_FREQUENCY:
        raise SystemExit(f'BOJ Tankan metadata mismatch: {row}')
    vals=row.get('VALUES') or {}
    src={quarter_key(d):float(v) for d,v in zip(vals.get('SURVEY_DATES') or [],vals.get('VALUES') or []) if v is not None}
    if not src:
        raise SystemExit('BOJ Tankan source returned no observations')
    return url,row,src


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',default=str(DEFAULT_OUT))
    args=ap.parse_args()

    liq=json.loads(RUNTIME.read_text(encoding='utf-8'))
    rtrow=liq['JPY']['conditions']
    dates=list(rtrow.get('dates') or [])
    values=list(rtrow.get('values') or [])
    if not dates or len(dates)!=len(values):
        raise SystemExit('invalid JPY.conditions runtime arrays')
    rt={quarter_key(d):float(v) for d,v in zip(dates,values)}
    url,row,src=fetch()
    overlap=sorted(set(rt)&set(src))
    if len(overlap)!=len(rt):
        raise SystemExit(f'BOJ Tankan overlap does not cover runtime: {len(overlap)}/{len(rt)}')
    mismatches=[{'quarter':d,'runtime':rt[d],'source':src[d]} for d in overlap if abs(rt[d]-src[d])>1e-9]
    if mismatches:
        raise SystemExit(f'BOJ Tankan current vintage rewrites runtime history: {mismatches[:10]}')
    runtime_last=quarter_key(rtrow['last_date'])
    if runtime_last not in src or abs(float(rtrow['last_value'])-src[runtime_last])>1e-9:
        raise SystemExit('JPY.conditions runtime last observation does not match BOJ exact series')
    latest_date=max(src)
    new=[{'date':d,'value':src[d]} for d in sorted(src) if d>runtime_last]
    result={
        'schema':'GMFQ_LIQUIDITY_JPY_TANKAN_LENDING_ATTITUDE_CANDIDATE_V1',
        'status':'GREEN_SOURCE_CANDIDATE_ONLY',
        'source':{
            'publisher':'Bank of Japan','api':'Time-Series Data Search API / getDataCode',
            'database':DB,'series_id':CODE,'url':url,
            'name':row.get('NAME_OF_TIME_SERIES'),'unit':row.get('UNIT'),'frequency':row.get('FREQUENCY'),
            'last_update':row.get('LAST_UPDATE'),'survey_item':'612','enterprise_size':'All Enterprises','industry':'All industries','result_type':'Actual result'
        },
        'runtime':{'count':len(rt),'last_date':runtime_last,'last_value':float(rtrow['last_value'])},
        'runtime_overlap_count':len(overlap),'runtime_exact_match_count':len(overlap),
        'runtime_exact_match_ratio':1.0,'runtime_match_confirmed':True,
        'runtime_history_unchanged_by_current_vintage':True,
        'latest_date':latest_date,'latest_value':src[latest_date],
        'candidate_update_available':bool(new),'new_observations':new,
        'publication_performed':False,'runtime_mutated':False,
    }
    Path(args.out).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':
    main()
