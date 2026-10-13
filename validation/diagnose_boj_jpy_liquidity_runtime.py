#!/usr/bin/env python3
import json
import urllib.parse
import urllib.request
from pathlib import Path

LIQ=Path('live_data/sections/NATIVE_LIQ_DATA.json')
BASE='https://www.stat-search.boj.or.jp/api/v1/getDataCode'
SERIES={
    'money': {'db':'MD02','code':'MAM1NAM3M3MO'},
    'credit': {'db':'MD11','code':'DLCLAEDBLTTO'},
}
SCALES={'raw_100m_yen':1.0,'billion_yen':0.1,'trillion_yen':0.0001}


def fetch(db,code):
    qs=urllib.parse.urlencode({'format':'json','lang':'en','db':db,'startDate':'202501','endDate':'202609','code':code})
    url=BASE+'?'+qs
    req=urllib.request.Request(url,headers={'User-Agent':'global-macro-fx-quant/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=45) as r:
        d=json.loads(r.read().decode('utf-8-sig'))
    if d.get('STATUS') != 200 or len(d.get('RESULTSET') or []) != 1:
        raise SystemExit(f'BOJ API contract failure {db}/{code}: {d}')
    row=d['RESULTSET'][0]
    dates=row['VALUES']['SURVEY_DATES']
    vals=row['VALUES']['VALUES']
    return url,row,{str(k)[:4]+'-'+str(k)[4:6]:float(v) for k,v in zip(dates,vals) if v is not None}


def runtime_series(obj):
    dates=obj.get('dates') or []
    vals=obj.get('values') or []
    if len(dates)!=len(vals):
        raise SystemExit('runtime dates/values length mismatch')
    return {str(d)[:7]:float(v) for d,v in zip(dates,vals) if str(d)[:4] in {'2025','2026'}}


def stats(rt,src,scale):
    overlap=sorted(set(rt)&set(src))
    diffs=[rt[d]-src[d]*scale for d in overlap]
    absd=[abs(x) for x in diffs]
    return {
        'overlap_count':len(overlap),
        'first_overlap':overlap[0] if overlap else None,
        'last_overlap':overlap[-1] if overlap else None,
        'mean_abs_diff':sum(absd)/len(absd) if absd else None,
        'max_abs_diff':max(absd) if absd else None,
        'exact_matches_1e6':sum(1 for x in absd if x<=1e-6),
        'last_runtime':rt[overlap[-1]] if overlap else None,
        'last_scaled_source':src[overlap[-1]]*scale if overlap else None,
    }


def main():
    liq=json.loads(LIQ.read_text(encoding='utf-8'))
    result={'schema':'GMFQ_BOJ_JPY_LIQUIDITY_RUNTIME_DIAGNOSTIC_V1','series':{}}
    for key,cfg in SERIES.items():
        rt=runtime_series(liq['JPY'][key])
        url,row,src=fetch(cfg['db'],cfg['code'])
        variants={name:stats(rt,src,scale) for name,scale in SCALES.items()}
        ranking=sorted(variants,key=lambda k: variants[k]['mean_abs_diff'] if variants[k]['mean_abs_diff'] is not None else float('inf'))
        result['series'][key]={
            'db':cfg['db'],'code':cfg['code'],'url':url,
            'name':row.get('NAME_OF_TIME_SERIES'),'unit':row.get('UNIT'),'frequency':row.get('FREQUENCY'),
            'runtime_last_date':str(liq['JPY'][key].get('last_date'))[:7],
            'runtime_last_value':liq['JPY'][key].get('last_value'),
            'variants':variants,'ranking':ranking,
        }
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':
    main()
