#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
OUT=Path('validation/liquidity-jpy-reserve-balances-diagnostic.json')
BASE='https://www.stat-search.boj.or.jp/api/v1'
DB='MD08'
UA='global-macro-fx-quant/1.0'


def get_json(endpoint, params):
    url=BASE+'/'+endpoint+'?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return url,json.loads(r.read().decode('utf-8-sig'))


def walk(obj):
    if isinstance(obj,dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj,list):
        for v in obj:
            yield from walk(v)


def metadata_candidates():
    url,obj=get_json('getMetadata',{'format':'json','lang':'en','db':DB})
    if obj.get('STATUS')!=200:
        raise SystemExit(f'BOJ metadata API failure: {obj}')
    found={}
    for row in walk(obj):
        code=None
        for k in ('SERIES_CODE','seriesCode','series_code','CODE','code'):
            if row.get(k):
                code=str(row[k]); break
        if not code:
            continue
        text=' '.join(str(v) for k,v in row.items() if isinstance(v,(str,int,float))).strip()
        low=text.lower()
        terms=('current account','balance','reserve','sector','boj')
        score=sum(1 for t in terms if t in low)
        if score>=2:
            prev=found.get(code)
            rec={'series_code':code,'score':score,'text':text[:2000]}
            if prev is None or score>prev['score']:
                found[code]=rec
    ranked=sorted(found.values(),key=lambda x:(-x['score'],x['series_code']))
    return url,ranked[:120]


def fetch_series(code):
    url,obj=get_json('getDataCode',{
        'format':'json','lang':'en','db':DB,'startDate':'201601','endDate':'202612','code':code
    })
    if obj.get('STATUS')!=200 or len(obj.get('RESULTSET') or [])!=1:
        return url,None,None
    row=obj['RESULTSET'][0]
    vals=row.get('VALUES') or {}
    src={}
    for d,v in zip(vals.get('SURVEY_DATES') or [],vals.get('VALUES') or []):
        if v is None:
            continue
        s=str(d)
        if len(s)>=6:
            key=s[:4]+'-'+s[4:6]
        else:
            continue
        try: src[key]=float(v)
        except (TypeError,ValueError): pass
    return url,row,src


def runtime_series():
    liq=json.loads(RUNTIME.read_text(encoding='utf-8'))
    row=liq['JPY']['liquidity']
    dates=list(row.get('dates') or [])
    values=list(row.get('values') or [])
    if not dates or len(dates)!=len(values):
        raise SystemExit('invalid JPY.liquidity runtime arrays')
    rt={str(d)[:7]:float(v) for d,v in zip(dates,values)}
    return row,rt


def score(rt,src):
    common=sorted(set(rt)&set(src))
    if not common:
        return {'overlap':0,'exact':0,'exact_ratio':0.0,'mae':None,'max_abs_diff':None}
    diffs=[rt[d]-src[d] for d in common]
    exact=sum(abs(x)<=1e-6 for x in diffs)
    return {
        'overlap':len(common),'exact':exact,'exact_ratio':exact/len(common),
        'mae':sum(abs(x) for x in diffs)/len(diffs),'max_abs_diff':max(abs(x) for x in diffs),
        'first_month':common[0],'last_month':common[-1],
        'runtime_last_value':rt[common[-1]],'source_last_value':src[common[-1]],
        'mismatches':[
            {'month':d,'runtime':rt[d],'source':src[d],'diff':rt[d]-src[d]}
            for d in common if abs(rt[d]-src[d])>1e-6
        ][:30]
    }


def main():
    rtrow,rt=runtime_series()
    meta_url,candidates=metadata_candidates()
    if not candidates:
        raise SystemExit('no plausible MD08 metadata candidates found')
    results=[]
    for c in candidates:
        try:
            url,row,src=fetch_series(c['series_code'])
        except Exception as exc:
            results.append({**c,'fetch_error':repr(exc)})
            continue
        if not row or not src:
            continue
        sc=score(rt,src)
        results.append({
            **c,'url':url,'name':row.get('NAME_OF_TIME_SERIES'),'unit':row.get('UNIT'),
            'frequency':row.get('FREQUENCY'),'score':sc
        })
    results.sort(key=lambda x:(-float((x.get('score') or {}).get('exact_ratio',0)),-int((x.get('score') or {}).get('overlap',0)),float((x.get('score') or {}).get('mae') or 1e99)))
    best=results[0] if results else None
    proven=bool(best and (best.get('score') or {}).get('overlap',0)>=12 and (best.get('score') or {}).get('exact_ratio')==1.0)
    report={
        'schema':'GMFQ_LIQUIDITY_JPY_RESERVE_DIAGNOSTIC_V1',
        'status':'EXACT_MD08_SERIES_RUNTIME_MATCH_PROVEN' if proven else 'WITHHELD_EXACT_SERIES_OR_RUNTIME_MATCH_PENDING',
        'source':{
            'publisher':'Bank of Japan','api':'Time-Series Data Search API',
            'database':DB,'metadata_url':meta_url,
            'source_family':'BOJ Current Account Balances by Sector'
        },
        'runtime':{
            'label':rtrow.get('label'),'count':len(rt),'first_month':min(rt),'last_month':max(rt),
            'last_value':float(rtrow.get('last_value'))
        },
        'metadata_candidate_count':len(candidates),
        'tested_series_count':len(results),
        'best_candidate':best,
        'top_candidates':results[:20],
        'promotion_eligible':proven,
        'automation_ready':False,
        'runtime_mutated':False,'publication_performed':False,'bias_score_sizing_effect':'NONE'
    }
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
