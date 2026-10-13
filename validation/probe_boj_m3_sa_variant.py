#!/usr/bin/env python3
import json, urllib.parse, urllib.request
from pathlib import Path

LIQ=Path('live_data/sections/NATIVE_LIQ_DATA.json')
BASE='https://www.stat-search.boj.or.jp/api/v1/getDataCode'
CODES=['MAM1SAM3M3MO','MAM1NAM3M3MO']

def fetch(code):
    qs=urllib.parse.urlencode({'format':'json','lang':'en','db':'MD02','startDate':'202501','endDate':'202608','code':code})
    url=BASE+'?'+qs
    req=urllib.request.Request(url,headers={'User-Agent':'global-macro-fx-quant/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=45) as r:
        d=json.loads(r.read().decode('utf-8-sig'))
    return url,d

def main():
    liq=json.loads(LIQ.read_text(encoding='utf-8'))
    rt={str(d)[:7]:float(v) for d,v in zip(liq['JPY']['money']['dates'],liq['JPY']['money']['values']) if str(d)[:4] in {'2025','2026'}}
    out={'schema':'GMFQ_BOJ_M3_SA_VARIANT_PROBE_V1','candidates':{}}
    for code in CODES:
        url,d=fetch(code)
        row=(d.get('RESULTSET') or [None])[0]
        item={'status':d.get('STATUS'),'message':d.get('MESSAGE'),'url':url}
        if row:
            src={str(k)[:4]+'-'+str(k)[4:6]:float(v) for k,v in zip(row['VALUES']['SURVEY_DATES'],row['VALUES']['VALUES']) if v is not None}
            overlap=sorted(set(rt)&set(src))
            diffs=[abs(rt[x]-src[x]) for x in overlap]
            item.update({'name':row.get('NAME_OF_TIME_SERIES'),'unit':row.get('UNIT'),'overlap_count':len(overlap),'exact_matches_1e6':sum(x<=1e-6 for x in diffs),'mean_abs_diff':sum(diffs)/len(diffs) if diffs else None,'max_abs_diff':max(diffs) if diffs else None,'last_runtime':rt[overlap[-1]] if overlap else None,'last_source':src[overlap[-1]] if overlap else None})
        out['candidates'][code]=item
    print(json.dumps(out,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
