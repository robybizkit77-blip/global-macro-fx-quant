#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, pathlib, sys
from datetime import date, timedelta

ROOT=pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CURRENT=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
SUPPORTED={'USD','EUR','GBP','JPY','CAD','NZD'}
SOURCE_LABELS={
 'USD':'U.S. Department of the Treasury · Daily Par Yield Curve',
 'EUR':'European Central Bank · AAA Svensson spot curve',
 'GBP':'Bank of England · UK nominal government zero-coupon spot curve',
 'JPY':'Japan Ministry of Finance · JGB Interest Rate',
 'CAD':'Bank of Canada · benchmark Government of Canada bond yields',
 'NZD':'Reserve Bank of New Zealand · B2 wholesale interest rates',
}

def hist_points(obj,key):
    h=obj.get(key) or {}; ds=h.get('dates') or []; vs=h.get('values') or []
    if len(ds)!=len(vs): raise ValueError(f'{key}: dates/values length mismatch')
    return [(str(d),float(v)) for d,v in zip(ds,vs)]

def reference_point(obj,key,end_date):
    cutoff=(date.fromisoformat(end_date)-timedelta(days=7)).isoformat()
    pts=[p for p in hist_points(obj,key) if p[0] <= cutoff]
    if not pts: raise ValueError(f'{key}: no same-basis history on/before {cutoff}')
    return max(pts,key=lambda x:x[0]), cutoff

def append_hist(obj,key,dt,val):
    h=obj.get(key)
    if not isinstance(h,dict): raise ValueError(f'{key}: missing history')
    ds=h.setdefault('dates',[]); vs=h.setdefault('values',[])
    if len(ds)!=len(vs): raise ValueError(f'{key}: dates/values length mismatch')
    if dt in ds: vs[ds.index(dt)]=val
    else: ds.append(dt); vs.append(val)
    h['last_date']=dt; h['last_value']=val

def classify(d2,d10):
    if d2>0 and d10>0: return 'Bear steepening' if d10>d2 else 'Bear flattening'
    if d2<0 and d10<0: return 'Bull steepening' if d2<d10 else 'Bull flattening'
    return 'Movimento misto'

def validate_coverage(c,row):
    mode=row.get('coverage_mode')
    if mode=='LIVE_FETCH':
        return mode
    if mode=='MANUAL_OFFICIAL_VERIFICATION':
        if c!='NZD': raise SystemExit(f'{c}: manual official verification is only permitted for NZD')
        if row.get('authority')!='Reserve Bank of New Zealand': raise SystemExit('NZD: manual verification authority mismatch')
        if 'rbnz.govt.nz' not in str(row.get('source_url') or ''): raise SystemExit('NZD: manual verification lacks official RBNZ URL')
        return mode
    raise SystemExit(f'{c}: update coverage mode not approved: {mode!r}')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--audit',required=True)
    ap.add_argument('--output',required=True)
    ap.add_argument('--current-rates',default=str(DEFAULT_CURRENT))
    a=ap.parse_args()
    audit=json.load(open(a.audit))
    if audit.get('status')!='PASS': raise SystemExit('unified audit is not PASS')
    updates=list(audit.get('summary',{}).get('updates_available') or [])
    unsupported=[c for c in updates if c not in SUPPORTED]
    if unsupported: raise SystemExit('UPDATE_AVAILABLE without generic support: '+repr(unsupported))
    cur=json.load(open(a.current_rates)); out=copy.deepcopy(cur)
    summary={'status':'NO_UPDATES' if not updates else 'CANDIDATE_READY','changed_currencies':[],'currencies':{}}
    for c in updates:
        row=audit['currencies'][c]
        mode=validate_coverage(c,row)
        src=row.get('official') or {}
        dt=str(src.get('date')); y2=float(src['2Y']); y10=float(src['10Y'])
        old=cur[c]
        if dt <= str(old.get('date')): raise SystemExit(f'{c}: non-advancing update {dt} <= {old.get("date")}')
        obj=out[c]
        (r2d,r2),cutoff=reference_point(obj,'history2',dt)
        (r10d,r10),_=reference_point(obj,'history10',dt)
        d2=round((y2-r2)*100,1); d10=round((y10-r10)*100,1)
        label=SOURCE_LABELS[c]
        obj['date']=dt; obj['source']=f'{label} · {dt}'
        obj['quality']='FULL_CURRENT_OFFICIAL' if mode=='LIVE_FETCH' else 'FULL_CURRENT_OFFICIAL_MANUAL_VERIFIED'
        obj['2Y']=y2; obj['10Y']=y10; obj['curve_bp']=round((y10-y2)*100,1)
        obj['chg2_bp']=d2; obj['chg10_bp']=d10; obj['curve_state']=classify(d2,d10)
        for t in obj.get('tenors',[]):
            if t.get('tenor')=='2Y': t['value']=y2; t['date']=dt
            if t.get('tenor')=='10Y': t['value']=y10; t['date']=dt
        append_hist(obj,'history2',dt,y2); append_hist(obj,'history10',dt,y10)
        obj['freshness_status']='CURRENT_OFFICIAL_SAME_BASIS' if mode=='LIVE_FETCH' else 'CURRENT_OFFICIAL_SAME_BASIS_MANUAL_VERIFIED'
        suffix='Official same-basis 2Y/10Y updated' if mode=='LIVE_FETCH' else 'Official RBNZ same-basis 2Y/10Y manually verified after automated source access was blocked'
        obj['freshness_note']=f'{suffix} through {dt}.'
        obj['weekly2_validation']={'start_date':r2d,'start_value':r2,'end_date':dt,'end_value':y2,'change_bp':d2,'source':f'{label} · {dt}','note':f'Same-basis change from latest observation on/before {cutoff}.'}
        obj['weekly10_validation']={'start_date':r10d,'start_value':r10,'end_date':dt,'end_value':y10,'change_bp':d10,'source':f'{label} · {dt}','note':f'Same-basis change from latest observation on/before {cutoff}.'}
        summary['changed_currencies'].append(c)
        summary['currencies'][c]={'old_date':old.get('date'),'new_date':dt,'2Y':y2,'10Y':y10,'curve_bp':obj['curve_bp'],'reference_2Y_date':r2d,'reference_10Y_date':r10d,'chg2_bp':d2,'chg10_bp':d10,'curve_state':obj['curve_state'],'coverage_mode':mode}
    changed=[c for c in cur if cur[c]!=out[c]]
    if sorted(changed)!=sorted(summary['changed_currencies']): raise SystemExit(f'scope mismatch expected={summary["changed_currencies"]} actual={changed}')
    pathlib.Path(a.output).write_text(json.dumps(out,separators=(',',':'),ensure_ascii=False)+'\n')
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    return 0
if __name__=='__main__': sys.exit(main())
