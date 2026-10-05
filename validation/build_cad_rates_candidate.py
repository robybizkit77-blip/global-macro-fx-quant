#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, pathlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
CURRENT=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
REF_CUTOFF='2026-09-25'
TARGET_DATE='2026-10-02'

def find_hist_value_on_or_before(obj,key,cutoff):
    h=obj.get(key) or {}; dates=h.get('dates') or []; vals=h.get('values') or []
    if len(dates)!=len(vals): raise ValueError(f'{key}: dates/values mismatch')
    candidates=[]
    for d,v in zip(dates,vals):
        ds=str(d)
        if ds<=cutoff:
            candidates.append((ds,float(v)))
    if not candidates: raise ValueError(f'{key}: no reference observation on/before {cutoff}')
    return max(candidates,key=lambda x:x[0])

def append_hist(obj,key,date,value):
    h=obj.get(key)
    if not isinstance(h,dict): raise ValueError(f'{key}: missing history')
    dates=h.setdefault('dates',[]); vals=h.setdefault('values',[])
    if len(dates)!=len(vals): raise ValueError(f'{key}: dates/values mismatch')
    if date in dates:
        i=dates.index(date); vals[i]=value
    else:
        dates.append(date); vals.append(value)
    h['last_date']=date; h['last_value']=value

def classify(d2,d10):
    if d2>0 and d10>0: return 'Bear steepening' if d10>d2 else 'Bear flattening'
    if d2<0 and d10<0: return 'Bull steepening' if d2<d10 else 'Bull flattening'
    return 'Movimento misto'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source-audit',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    audit=json.load(open(a.source_audit))['CAD']
    if audit['official_date']!=TARGET_DATE: raise SystemExit(f'unexpected official date {audit["official_date"]}')
    if audit.get('series_2Y')!='BD.CDN.2YR.DQ.YLD' or audit.get('series_10Y')!='BD.CDN.10YR.DQ.YLD':
        raise SystemExit('unexpected Bank of Canada series identifiers')
    cur=json.loads(CURRENT.read_text()); out=copy.deepcopy(cur); old=cur['CAD']; j=out['CAD']
    if old.get('date')!='2026-10-01': raise SystemExit(f'unexpected current CAD date {old.get("date")}')
    y2=float(audit['2Y']); y10=float(audit['10Y'])
    ref2_date,ref2=find_hist_value_on_or_before(j,'history2',REF_CUTOFF)
    ref10_date,ref10=find_hist_value_on_or_before(j,'history10',REF_CUTOFF)
    if ref2_date!=ref10_date: raise SystemExit(f'same-basis reference mismatch {ref2_date} vs {ref10_date}')
    ref_date=ref2_date
    chg2=round((y2-ref2)*100,1); chg10=round((y10-ref10)*100,1)
    source='Bank of Canada Valet API · selected benchmark Government of Canada bond yields · 2 Oct 2026'
    j['date']=TARGET_DATE; j['source']=source; j['quality']='FULL_CURRENT_OFFICIAL_SAME_BASIS'
    j['2Y']=y2; j['10Y']=y10; j['curve_bp']=round((y10-y2)*100,1)
    j['chg2_bp']=chg2; j['chg10_bp']=chg10; j['curve_state']=classify(chg2,chg10)
    for t in j.get('tenors',[]):
        if t.get('tenor')=='2Y': t['value']=y2; t['date']=TARGET_DATE
        if t.get('tenor')=='10Y': t['value']=y10; t['date']=TARGET_DATE
    append_hist(j,'history2',TARGET_DATE,y2); append_hist(j,'history10',TARGET_DATE,y10)
    j['freshness_status']='CURRENT_OFFICIAL_SAME_BASIS'
    j['freshness_note']=source+' updated through 2026-10-02.'
    note=f'Same-basis change from {ref_date} (latest available on/before {REF_CUTOFF}) to {TARGET_DATE}.'
    j['weekly2_validation']={'start_date':ref_date,'start_value':ref2,'end_date':TARGET_DATE,'end_value':y2,'change_bp':chg2,'source':source,'note':note}
    j['weekly10_validation']={'start_date':ref_date,'start_value':ref10,'end_date':TARGET_DATE,'end_value':y10,'change_bp':chg10,'source':source,'note':note}
    changed=[c for c in cur if cur[c]!=out[c]]
    if changed!=['CAD']: raise SystemExit('unexpected scope: '+repr(changed))
    pathlib.Path(a.output).write_text(json.dumps(out,separators=(',',':'),ensure_ascii=False)+'\n')
    print(json.dumps({'status':'PASS','changed_currencies':changed,'CAD':{'old_date':old['date'],'new_date':TARGET_DATE,'2Y':y2,'10Y':y10,'curve_bp':j['curve_bp'],'reference_date':ref_date,'reference_2Y':ref2,'reference_10Y':ref10,'chg2_bp':chg2,'chg10_bp':chg10,'curve_state':j['curve_state']}},indent=2,ensure_ascii=False))

if __name__=='__main__': sys.exit(main())
