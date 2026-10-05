#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, pathlib, subprocess, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
CURRENT=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
REF_DATE='2026-09-25'

def find_hist_value(obj:dict, key:str, date:str)->float:
    h=obj.get(key) or {}
    dates=h.get('dates') or []; vals=h.get('values') or []
    if len(dates)!=len(vals): raise ValueError(f'{key}: dates/values length mismatch')
    for d,v in zip(dates,vals):
        if str(d)==date: return float(v)
    raise ValueError(f'{key}: reference date {date} not found')

def append_hist(obj:dict,key:str,date:str,value:float)->None:
    h=obj.get(key)
    if not isinstance(h,dict): raise ValueError(f'{key}: missing history')
    dates=h.setdefault('dates',[]); vals=h.setdefault('values',[])
    if len(dates)!=len(vals): raise ValueError(f'{key}: dates/values length mismatch')
    if date in dates:
        i=dates.index(date); vals[i]=value
    else:
        dates.append(date); vals.append(value)
    h['last_date']=date; h['last_value']=value

def classify(d2:float,d10:float)->str:
    if d2>0 and d10>0:
        return 'Bear steepening' if d10>d2 else 'Bear flattening'
    if d2<0 and d10<0:
        return 'Bull steepening' if d2<d10 else 'Bull flattening'
    return 'Movimento misto'

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-audit',required=True)
    ap.add_argument('--output',required=True)
    a=ap.parse_args()
    audit=json.load(open(a.source_audit))
    if audit.get('status')!='PASS': raise SystemExit('source audit not PASS')
    if audit['USD']['state']!='NO_CHANGE': raise SystemExit('USD control is not NO_CHANGE')
    if audit['JPY']['state']!='ADVANCE_AVAILABLE': raise SystemExit('JPY advance not available')
    src=audit['JPY']['source']
    if src['authority']!='Japan Ministry of Finance': raise SystemExit('unexpected JPY authority')
    if src['date']!='2026-10-02': raise SystemExit('unexpected JPY source date')

    cur=json.loads(CURRENT.read_text())
    out=copy.deepcopy(cur); j=out['JPY']; old=cur['JPY']
    if old.get('date')!='2026-10-01': raise SystemExit('unexpected current JPY date')
    y2=float(src['2Y']); y10=float(src['10Y']); dt=src['date']
    ref2=find_hist_value(j,'history2',REF_DATE); ref10=find_hist_value(j,'history10',REF_DATE)
    chg2=round((y2-ref2)*100,1); chg10=round((y10-ref10)*100,1)

    j['date']=dt
    j['source']='Japan Ministry of Finance · JGB Interest Rate · 2 Oct 2026'
    j['quality']='FULL_CURRENT_OFFICIAL'
    j['2Y']=y2; j['10Y']=y10
    j['curve_bp']=round((y10-y2)*100,1)
    j['chg2_bp']=chg2; j['chg10_bp']=chg10
    j['curve_state']=classify(chg2,chg10)
    for t in j.get('tenors',[]):
        if t.get('tenor')=='2Y': t['value']=y2; t['date']=dt
        if t.get('tenor')=='10Y': t['value']=y10; t['date']=dt
    append_hist(j,'history2',dt,y2); append_hist(j,'history10',dt,y10)
    j['freshness_status']='CURRENT_OFFICIAL_SAME_BASIS'
    j['freshness_note']='MOF official same-basis 2Y/10Y updated through 2026-10-02.'
    j['weekly2_validation']={'start_date':REF_DATE,'start_value':ref2,'end_date':dt,'end_value':y2,'change_bp':chg2,'source':'Japan Ministry of Finance · JGB Interest Rate · 2 Oct 2026','note':'Same-basis weekly change from 2026-09-25 to 2026-10-02.'}
    j['weekly10_validation']={'start_date':REF_DATE,'start_value':ref10,'end_date':dt,'end_value':y10,'change_bp':chg10,'source':'Japan Ministry of Finance · JGB Interest Rate · 2 Oct 2026','note':'Same-basis weekly change from 2026-09-25 to 2026-10-02.'}

    # Strict scope: only JPY may differ from current rates section.
    changed=[c for c in cur if cur[c]!=out[c]]
    if changed!=['JPY']: raise SystemExit('unexpected currency scope: '+repr(changed))
    pathlib.Path(a.output).write_text(json.dumps(out,separators=(',',':'),ensure_ascii=False)+'\n')
    print(json.dumps({'status':'PASS','changed_currencies':changed,'JPY':{'old_date':old['date'],'new_date':dt,'2Y':y2,'10Y':y10,'curve_bp':j['curve_bp'],'reference_date':REF_DATE,'reference_2Y':ref2,'reference_10Y':ref10,'chg2_bp':chg2,'chg10_bp':chg10,'curve_state':j['curve_state']}},indent=2,ensure_ascii=False))
    return 0

if __name__=='__main__': sys.exit(main())
