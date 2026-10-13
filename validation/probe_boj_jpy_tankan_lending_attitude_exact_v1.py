#!/usr/bin/env python3
from __future__ import annotations
import json, urllib.parse, urllib.request
from pathlib import Path

BASE='https://www.stat-search.boj.or.jp/api/v1/getDataCode'
DB='CO'
RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
CODES={
  'all_enterprises':'TK99F0000612GCQ00000',
  'large_enterprises':'TK99F0000612GCQ01000',
  'medium_enterprises':'TK99F0000612GCQ02000',
  'small_enterprises':'TK99F0000612GCQ03000',
}

def fetch(code):
    q=urllib.parse.urlencode({'format':'json','lang':'en','db':DB,'startDate':'201601','endDate':'202612','code':code})
    req=urllib.request.Request(BASE+'?'+q,headers={'User-Agent':'global-macro-fx-quant/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as r:
        o=json.loads(r.read().decode('utf-8-sig'))
    if o.get('STATUS')!=200 or len(o.get('RESULTSET') or [])!=1:
        return {'code':code,'api_status':o.get('STATUS'),'message':o.get('MESSAGE'),'valid':False}
    row=o['RESULTSET'][0]; vals=row.get('VALUES') or {}
    src={}
    for d,v in zip(vals.get('SURVEY_DATES') or [],vals.get('VALUES') or []):
        if v is None: continue
        ds=''.join(ch for ch in str(d) if ch.isdigit())
        if len(ds)<6: continue
        y=int(ds[:4]); m=int(ds[4:6])
        # BOJ TANKAN API quarterly SURVEY_DATES may be YYYY01..YYYY04 (quarter number)
        if m in (1,2,3,4): qn=m
        elif m in (3,6,9,12): qn=((m-1)//3)+1
        else: continue
        try: src[f'{y}-Q{qn}']=float(v)
        except (TypeError,ValueError): pass
    return {'code':code,'valid':True,'name':row.get('NAME_OF_TIME_SERIES'),'unit':row.get('UNIT'),'frequency':row.get('FREQUENCY'),'last_update':row.get('LAST_UPDATE'),'values':src}

def main():
    rr=json.loads(RUNTIME.read_text())['JPY']['conditions']
    rt={str(d):float(v) for d,v in zip(rr['dates'],rr['values'])}
    out=[]
    for label,code in CODES.items():
        s=fetch(code)
        src=s.pop('values',{}) if s.get('valid') else {}
        common=sorted(set(rt)&set(src))
        diffs=[rt[d]-src[d] for d in common]
        exact=sum(abs(x)<=1e-9 for x in diffs)
        s.update({'variant':label,'overlap':len(common),'exact':exact,'exact_ratio':exact/len(common) if common else 0.0,'mae':sum(abs(x) for x in diffs)/len(diffs) if diffs else None,'max_abs_diff':max((abs(x) for x in diffs),default=None),'source_last_quarter':max(src) if src else None,'source_last_value':src[max(src)] if src else None,'runtime_overlap_last':rt[common[-1]] if common else None})
        out.append(s)
    exact=[x for x in out if x['overlap']==len(rt) and x['exact']==len(rt) and x['exact_ratio']==1.0]
    report={'schema':'GMFQ_BOJ_JPY_TANKAN_LENDING_ATTITUDE_EXACT_PROBE_V1','status':'UNIQUE_EXACT_MATCH' if len(exact)==1 else 'AMBIGUOUS_EXACT_MATCH' if len(exact)>1 else 'NO_FULL_EXACT_MATCH','runtime_count':len(rt),'runtime_first':min(rt),'runtime_last':max(rt),'runtime_last_value':rt[max(rt)],'tested_variants':out,'exact_match_count':len(exact),'exact_matches':exact,'promotion_eligible':len(exact)==1,'runtime_mutated':False,'publication_performed':False}
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
