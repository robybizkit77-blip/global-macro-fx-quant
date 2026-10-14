#!/usr/bin/env python3
"""Build a fail-closed, revision-aware BOJ JPY M3 candidate."""
from __future__ import annotations
import argparse, hashlib, json, urllib.parse, urllib.request
from pathlib import Path

RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
DEFAULT_OUT=Path('validation/liquidity-jpy-m3-exact-candidate.json')
BASE='https://www.stat-search.boj.or.jp/api/v1/getDataCode'
DB='MD02'; CODE='MAM1XAM3M3MO'; PUBLISHER='Bank of Japan'
API='Time-Series Data Search API / getDataCode'
NAME='M3/Average Amounts Outstanding/Seasonally Adjusted/Money Stock'
UNIT='100 million yen'; FREQUENCY='MONTHLY'; WINDOW=3; EPS=1e-6

def month(value):
    digits=''.join(ch for ch in str(value) if ch.isdigit())
    if len(digits)<6: raise ValueError(f'invalid monthly date: {value!r}')
    y,m=int(digits[:4]),int(digits[4:6])
    if not 1<=m<=12: raise ValueError(f'invalid monthly date: {value!r}')
    return f'{y:04d}-{m:02d}'

def previous(value, count):
    y,m=map(int,month(value).split('-'))
    for _ in range(count): y,m=(y-1,12) if m==1 else (y,m-1)
    return f'{y:04d}-{m:02d}'

def fingerprint(dates,values):
    raw=json.dumps({'dates':[month(d) for d in dates],'values':[float(v) for v in values]},sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(raw).hexdigest()

def descriptor(row, url=None):
    d={'publisher':PUBLISHER,'api':API,'database':DB,'series_id':CODE,'name':row.get('NAME_OF_TIME_SERIES',NAME),'unit':row.get('UNIT',UNIT),'frequency':row.get('FREQUENCY',FREQUENCY),'seasonal_adjustment':'Seasonally Adjusted'}
    if url: d['url']=url
    return d

def fetch():
    url=BASE+'?'+urllib.parse.urlencode({'format':'json','lang':'en','db':DB,'startDate':'201501','endDate':'202612','code':CODE})
    req=urllib.request.Request(url,headers={'User-Agent':'global-macro-fx-quant/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=45) as response: payload=json.loads(response.read().decode('utf-8-sig'))
    if payload.get('STATUS')!=200 or len(payload.get('RESULTSET') or [])!=1: raise ValueError(f'BOJ API contract failure: {payload}')
    row=payload['RESULTSET'][0]
    if (row.get('SERIES_CODE'),row.get('NAME_OF_TIME_SERIES'),row.get('UNIT'),row.get('FREQUENCY')) != (CODE,NAME,UNIT,FREQUENCY): raise ValueError(f'BOJ JPY M3 provenance/metadata mismatch: {row}')
    src={month(d):float(v) for d,v in zip(row['VALUES']['SURVEY_DATES'],row['VALUES']['VALUES']) if v is not None}
    if not src: raise ValueError('BOJ JPY M3 source returned no observations')
    return url,row,src

def veto(status,runtime,reason,**more):
    result={'schema':'GMFQ_LIQUIDITY_JPY_M3_REVISION_AWARE_CANDIDATE_V1','status':status,'source':descriptor({}),'runtime':runtime,'candidate_update_available':False,'revised_observations':[],'appended_observations':[],'fail_closed':True,'failure_reason':reason,'publication_performed':False,'runtime_mutated':False}
    result.update(more); return result

def build(liq,url,row,src):
    money=liq['JPY']['money']; dates=list(money.get('dates') or []); values=list(money.get('values') or [])
    if not dates or len(dates)!=len(values): raise ValueError('invalid JPY.money runtime arrays')
    rt={month(d):float(v) for d,v in zip(dates,values)}
    if len(rt)!=len(dates): raise ValueError('duplicate JPY.money runtime dates')
    last=month(money['last_date'])
    if last!=month(dates[-1]) or abs(float(money['last_value'])-float(values[-1]))>EPS: raise ValueError('JPY.money runtime terminal fields inconsistent')
    runtime={'count':len(rt),'last_date':last,'last_value':float(money['last_value']),'money_fingerprint_sha256':fingerprint(dates,values)}
    overlap=sorted(set(rt)&set(src))
    if len(overlap)<120: raise ValueError(f'insufficient JPY M3 runtime/source overlap: {len(overlap)}')
    revised=[{'date':d,'old_value':rt[d],'new_value':src[d]} for d in overlap if abs(rt[d]-src[d])>EPS]
    start=previous(last,WINDOW-1); source=descriptor(row,url)
    outside=[x for x in revised if x['date']<start]
    if outside: return veto('WITHHELD_REVISION_OUTSIDE_WINDOW',runtime,'official BOJ revision is older than the permitted trailing revision window',source=source,runtime_overlap_count=len(overlap),runtime_exact_match_count=len(overlap)-len(revised),runtime_exact_match_ratio=(len(overlap)-len(revised))/len(overlap),revision_window={'months':WINDOW,'start_date':start,'end_date':last},revised_observations=revised,out_of_window_revisions=outside)
    appended=[{'date':d,'value':src[d]} for d in sorted(src) if d>last]
    return {'schema':'GMFQ_LIQUIDITY_JPY_M3_REVISION_AWARE_CANDIDATE_V1','status':'GREEN_REVISION_AWARE_CANDIDATE','source':source,'runtime':runtime,'runtime_overlap_count':len(overlap),'runtime_exact_match_count':len(overlap)-len(revised),'runtime_exact_match_ratio':(len(overlap)-len(revised))/len(overlap),'runtime_match_confirmed':not revised,'revision_window':{'months':WINDOW,'start_date':start,'end_date':last},'revised_observations':revised,'appended_observations':appended,'latest_date':max(src),'latest_value':src[max(src)],'candidate_update_available':bool(revised or appended),'fail_closed':False,'publication_performed':False,'runtime_mutated':False}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default=str(DEFAULT_OUT)); args=ap.parse_args()
    liq=json.loads(RUNTIME.read_text(encoding='utf-8')); money=liq['JPY']['money']
    runtime={'count':len(money.get('dates') or []),'last_date':month(money['last_date']),'last_value':float(money['last_value'])}
    try: url,row,src=fetch(); result=build(liq,url,row,src)
    except Exception as exc: result=veto('WITHHELD_SOURCE_UNAVAILABLE',runtime,'source or provenance contract unavailable',source_error_type=type(exc).__name__)
    Path(args.out).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
