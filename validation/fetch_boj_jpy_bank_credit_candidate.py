#!/usr/bin/env python3
import json
import urllib.parse
import urllib.request
from pathlib import Path

LIQ=Path('live_data/sections/NATIVE_LIQ_DATA.json')
OUT=Path('validation/liquidity-jpy-bank-credit-candidate.json')
BASE='https://www.stat-search.boj.or.jp/api/v1/getDataCode'
DB='MD11'
CODE='DLCLAEDBLTTO'


def fetch():
    qs=urllib.parse.urlencode({'format':'json','lang':'en','db':DB,'startDate':'202401','endDate':'202612','code':CODE})
    url=BASE+'?'+qs
    req=urllib.request.Request(url,headers={'User-Agent':'global-macro-fx-quant/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=45) as r:
        d=json.loads(r.read().decode('utf-8-sig'))
    if d.get('STATUS')!=200 or len(d.get('RESULTSET') or [])!=1:
        raise SystemExit(f'BOJ API contract failure: {d}')
    row=d['RESULTSET'][0]
    if row.get('SERIES_CODE')!=CODE or row.get('UNIT')!='100 million yen' or row.get('FREQUENCY')!='MONTHLY':
        raise SystemExit(f'BOJ series metadata mismatch: {row}')
    src={str(k)[:4]+'-'+str(k)[4:6]:float(v) for k,v in zip(row['VALUES']['SURVEY_DATES'],row['VALUES']['VALUES']) if v is not None}
    return url,row,src


def main():
    liq=json.loads(LIQ.read_text(encoding='utf-8'))
    rtrow=liq['JPY']['credit']
    rt={str(d)[:7]:float(v) for d,v in zip(rtrow['dates'],rtrow['values'])}
    url,row,src=fetch()
    overlap=sorted(set(rt)&set(src))
    if len(overlap)<12:
        raise SystemExit(f'insufficient runtime/source overlap: {len(overlap)}')
    mismatches=[{'date':d,'runtime':rt[d],'source':src[d]} for d in overlap if abs(rt[d]-src[d])>1e-6]
    if mismatches:
        raise SystemExit(f'BOJ JPY credit runtime/source mismatch: {mismatches[:10]}')
    runtime_last=str(rtrow['last_date'])[:7]
    if runtime_last not in src or abs(float(rtrow['last_value'])-src[runtime_last])>1e-6:
        raise SystemExit('runtime last observation does not match BOJ source')
    latest_date=max(src)
    result={
        'schema':'GMFQ_LIQUIDITY_JPY_BANK_CREDIT_CANDIDATE_V1',
        'source':{
            'publisher':'Bank of Japan','api':'Time-Series Data Search API / getDataCode',
            'database':DB,'series_id':CODE,'url':url,
            'name':row.get('NAME_OF_TIME_SERIES'),'unit':row.get('UNIT'),'frequency':row.get('FREQUENCY'),
        },
        'runtime':{'last_date':runtime_last,'last_value':float(rtrow['last_value'])},
        'runtime_overlap_count':len(overlap),'runtime_exact_match_count':len(overlap),'runtime_match_confirmed':True,
        'latest_date':latest_date,'latest_value':src[latest_date],
        'candidate_update_available':latest_date>runtime_last,
        'status':'GREEN_SOURCE_CANDIDATE_ONLY','publication_performed':False,'runtime_mutated':False,
    }
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
