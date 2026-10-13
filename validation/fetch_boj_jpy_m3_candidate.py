#!/usr/bin/env python3
from __future__ import annotations

# Candidate-only probe: never mutates runtime or publishes.
import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
DEFAULT_OUT=Path('validation/liquidity-jpy-m3-candidate.json')
BASE='https://www.stat-search.boj.or.jp/api/v1/getDataCode'
DB='MD02'
CODE='MAM1NAM3M3MO'


def fetch():
    qs=urllib.parse.urlencode({'format':'json','lang':'en','db':DB,'startDate':'201501','endDate':'202612','code':CODE})
    url=BASE+'?'+qs
    req=urllib.request.Request(url,headers={'User-Agent':'global-macro-fx-quant/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=45) as r:
        d=json.loads(r.read().decode('utf-8-sig'))
    if d.get('STATUS')!=200 or len(d.get('RESULTSET') or [])!=1:
        raise SystemExit(f'BOJ API contract failure: {d}')
    row=d['RESULTSET'][0]
    if row.get('SERIES_CODE')!=CODE or row.get('FREQUENCY')!='MONTHLY':
        raise SystemExit(f'BOJ M3 metadata mismatch: {row}')
    src={str(k)[:4]+'-'+str(k)[4:6]:float(v) for k,v in zip(row['VALUES']['SURVEY_DATES'],row['VALUES']['VALUES']) if v is not None}
    return url,row,src


def month(v):
    s=str(v)
    if len(s)<7: raise SystemExit(f'invalid monthly date {v!r}')
    return s[:7]


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default=str(DEFAULT_OUT)); args=ap.parse_args()
    liq=json.loads(RUNTIME.read_text(encoding='utf-8'))
    rtrow=liq['JPY']['money']
    rt={month(d):float(v) for d,v in zip(rtrow['dates'],rtrow['values'])}
    url,row,src=fetch()
    overlap=sorted(set(rt)&set(src))
    mismatches=[{'date':d,'runtime':rt[d],'source':src[d],'diff':rt[d]-src[d]} for d in overlap if abs(rt[d]-src[d])>1e-6]
    runtime_last=month(rtrow['last_date'])
    last_match=runtime_last in src and abs(float(rtrow['last_value'])-src[runtime_last])<=1e-6
    latest=max(src)
    new=[{'date':d,'value':src[d]} for d in sorted(src) if d>runtime_last]
    result={
      'schema':'GMFQ_LIQUIDITY_JPY_M3_CANDIDATE_V1',
      'status':'GREEN_SOURCE_CANDIDATE_ONLY' if len(overlap)>=12 and not mismatches and last_match else 'WITHHELD_RUNTIME_SOURCE_MISMATCH',
      'source':{'publisher':'Bank of Japan','api':'Time-Series Data Search API / getDataCode','database':DB,'series_id':CODE,'url':url,'name':row.get('NAME_OF_TIME_SERIES'),'unit':row.get('UNIT'),'frequency':row.get('FREQUENCY')},
      'runtime':{'count':len(rt),'last_date':runtime_last,'last_value':float(rtrow['last_value'])},
      'runtime_overlap_count':len(overlap),'runtime_exact_match_count':len(overlap)-len(mismatches),'runtime_match_confirmed':bool(len(overlap)>=12 and not mismatches and last_match),
      'mismatch_count':len(mismatches),'mismatches':mismatches[:30],
      'latest_date':latest,'latest_value':src[latest],
      'candidate_update_available':bool(new),'new_observations':new,
      'publication_performed':False,'runtime_mutated':False
    }
    out=Path(args.out); out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
