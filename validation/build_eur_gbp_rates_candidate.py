#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, pathlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
CURRENT=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
REF_DATE='2026-09-25'
TARGET_DATE='2026-10-02'

def find_hist_value(obj,key,date):
    h=obj.get(key) or {}; dates=h.get('dates') or []; vals=h.get('values') or []
    if len(dates)!=len(vals): raise ValueError(f'{key}: dates/values mismatch')
    for d,v in zip(dates,vals):
        if str(d)==date: return float(v)
    raise ValueError(f'{key}: reference date {date} not found')

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

def apply_one(out,cur,ccy,src,source_text,quality='FULL_CURRENT_OFFICIAL_SAME_BASIS'):
    if src['official_date']!=TARGET_DATE: raise SystemExit(f'{ccy}: unexpected official date {src["official_date"]}')
    j=out[ccy]; old=cur[ccy]
    if old.get('date')!='2026-10-01': raise SystemExit(f'{ccy}: unexpected current date {old.get("date")}')
    y2=float(src['2Y']); y10=float(src['10Y'])
    ref2=find_hist_value(j,'history2',REF_DATE); ref10=find_hist_value(j,'history10',REF_DATE)
    chg2=round((y2-ref2)*100,1); chg10=round((y10-ref10)*100,1)
    j['date']=TARGET_DATE; j['source']=source_text; j['quality']=quality
    j['2Y']=y2; j['10Y']=y10; j['curve_bp']=round((y10-y2)*100,1)
    j['chg2_bp']=chg2; j['chg10_bp']=chg10; j['curve_state']=classify(chg2,chg10)
    for t in j.get('tenors',[]):
        if t.get('tenor')=='2Y': t['value']=y2; t['date']=TARGET_DATE
        if t.get('tenor')=='10Y': t['value']=y10; t['date']=TARGET_DATE
    append_hist(j,'history2',TARGET_DATE,y2); append_hist(j,'history10',TARGET_DATE,y10)
    j['freshness_status']='CURRENT_OFFICIAL_SAME_BASIS'
    j['freshness_note']=source_text+' updated through 2026-10-02.'
    j['weekly2_validation']={'start_date':REF_DATE,'start_value':ref2,'end_date':TARGET_DATE,'end_value':y2,'change_bp':chg2,'source':source_text,'note':'Same-basis weekly change from 2026-09-25 to 2026-10-02.'}
    j['weekly10_validation']={'start_date':REF_DATE,'start_value':ref10,'end_date':TARGET_DATE,'end_value':y10,'change_bp':chg10,'source':source_text,'note':'Same-basis weekly change from 2026-09-25 to 2026-10-02.'}
    return {'old_date':old['date'],'new_date':TARGET_DATE,'2Y':y2,'10Y':y10,'curve_bp':j['curve_bp'],'chg2_bp':chg2,'chg10_bp':chg10,'curve_state':j['curve_state']}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source-audit',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    audit=json.load(open(a.source_audit)); cur=json.loads(CURRENT.read_text()); out=copy.deepcopy(cur)
    if audit['GBP'].get('boe_file')!='GLC Nominal daily data current month.xlsx': raise SystemExit('GBP audit not from BoE nominal workbook')
    summary={}
    summary['EUR']=apply_one(out,cur,'EUR',audit['EUR'],'European Central Bank · AAA Svensson spot curve · 2 Oct 2026')
    summary['GBP']=apply_one(out,cur,'GBP',audit['GBP'],'Bank of England · UK nominal government zero-coupon spot curve · 2 Oct 2026')
    changed=[c for c in cur if cur[c]!=out[c]]
    if changed!=['EUR','GBP']: raise SystemExit('unexpected scope: '+repr(changed))
    pathlib.Path(a.output).write_text(json.dumps(out,separators=(',',':'),ensure_ascii=False)+'\n')
    print(json.dumps({'status':'PASS','changed_currencies':changed,**summary},indent=2,ensure_ascii=False))

if __name__=='__main__': sys.exit(main())
