#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
DEFAULT_OUT=Path('validation/liquidity-jpy-m3-exact-candidate.json')
BASE='https://www.stat-search.boj.or.jp/api/v1/getDataCode'
DB='MD02'
CODE='MAM1XAM3M3MO'
EXPECTED_NAME='M3/Average Amounts Outstanding/Seasonally Adjusted/Money Stock'
EXPECTED_UNIT='100 million yen'
EXPECTED_FREQUENCY='MONTHLY'


def month(value: str) -> str:
    s=str(value)
    if len(s)<6:
        raise SystemExit(f'invalid monthly date: {value!r}')
    digits=''.join(ch for ch in s if ch.isdigit())
    if len(digits)<6:
        raise SystemExit(f'invalid monthly date: {value!r}')
    y=int(digits[:4]); m=int(digits[4:6])
    if not 1<=m<=12:
        raise SystemExit(f'invalid monthly date: {value!r}')
    return f'{y:04d}-{m:02d}'


def fetch():
    qs=urllib.parse.urlencode({'format':'json','lang':'en','db':DB,'startDate':'201501','endDate':'202612','code':CODE})
    url=BASE+'?'+qs
    req=urllib.request.Request(url,headers={'User-Agent':'global-macro-fx-quant/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=45) as r:
        payload=json.loads(r.read().decode('utf-8-sig'))
    if payload.get('STATUS')!=200 or len(payload.get('RESULTSET') or [])!=1:
        raise SystemExit(f'BOJ API contract failure: {payload}')
    row=payload['RESULTSET'][0]
    if row.get('SERIES_CODE')!=CODE:
        raise SystemExit(f'BOJ JPY M3 series code mismatch: {row}')
    if row.get('NAME_OF_TIME_SERIES')!=EXPECTED_NAME:
        raise SystemExit(f'BOJ JPY M3 series name mismatch: {row.get("NAME_OF_TIME_SERIES")!r}')
    if row.get('UNIT')!=EXPECTED_UNIT or row.get('FREQUENCY')!=EXPECTED_FREQUENCY:
        raise SystemExit(f'BOJ JPY M3 metadata mismatch: {row}')
    src={month(k):float(v) for k,v in zip(row['VALUES']['SURVEY_DATES'],row['VALUES']['VALUES']) if v is not None}
    if not src:
        raise SystemExit('BOJ JPY M3 source returned no observations')
    return url,row,src


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',default=str(DEFAULT_OUT))
    args=ap.parse_args()

    liq=json.loads(RUNTIME.read_text(encoding='utf-8'))
    rtrow=liq['JPY']['money']
    if len(rtrow.get('dates') or [])!=len(rtrow.get('values') or []) or not rtrow.get('dates'):
        raise SystemExit('invalid JPY.money runtime arrays')
    rt={month(d):float(v) for d,v in zip(rtrow['dates'],rtrow['values'])}
    url,row,src=fetch()
    overlap=sorted(set(rt)&set(src))
    if len(overlap)<120:
        raise SystemExit(f'insufficient JPY M3 runtime/source overlap: {len(overlap)}')
    mismatches=[{'date':d,'runtime':rt[d],'source':src[d]} for d in overlap if abs(rt[d]-src[d])>1e-6]
    if mismatches:
        raise SystemExit(f'BOJ JPY M3 current vintage rewrites runtime history: {mismatches[:10]}')
    runtime_last=month(rtrow['last_date'])
    if runtime_last not in src or abs(float(rtrow['last_value'])-src[runtime_last])>1e-6:
        raise SystemExit('JPY M3 runtime last observation does not match BOJ exact series')
    latest_date=max(src)
    new=[{'date':d,'value':src[d]} for d in sorted(src) if d>runtime_last]
    result={
        'schema':'GMFQ_LIQUIDITY_JPY_M3_EXACT_CANDIDATE_V1',
        'status':'GREEN_SOURCE_CANDIDATE_ONLY',
        'source':{
            'publisher':'Bank of Japan','api':'Time-Series Data Search API / getDataCode',
            'database':DB,'series_id':CODE,'url':url,
            'name':row.get('NAME_OF_TIME_SERIES'),'unit':row.get('UNIT'),'frequency':row.get('FREQUENCY'),
            'seasonal_adjustment':'Seasonally Adjusted',
        },
        'runtime':{'count':len(rt),'last_date':runtime_last,'last_value':float(rtrow['last_value'])},
        'runtime_overlap_count':len(overlap),'runtime_exact_match_count':len(overlap),
        'runtime_exact_match_ratio':1.0,'runtime_match_confirmed':True,
        'runtime_history_unchanged_by_current_vintage':True,
        'latest_date':latest_date,'latest_value':src[latest_date],
        'candidate_update_available':bool(new),'new_observations':new,
        'publication_performed':False,'runtime_mutated':False,
    }
    out=Path(args.out)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':
    main()
