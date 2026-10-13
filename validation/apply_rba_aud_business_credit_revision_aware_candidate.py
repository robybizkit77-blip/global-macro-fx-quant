#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from datetime import datetime,date
from pathlib import Path
DEFAULT_RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json'); SERIES_KEY='DLCACSFBS'; TOL=1e-9

def month(v):
    if isinstance(v,(datetime,date)): return v.strftime('%Y-%m')
    s=str(v or '').strip()
    for fmt in ('%Y-%m-%d','%Y-%m','%d/%m/%Y'):
        try: return datetime.strptime(s,fmt).strftime('%Y-%m')
        except ValueError: pass
    raise SystemExit(f'invalid AUD.credit month: {v!r}')

def next_month(v):
    y,m=map(int,month(v).split('-')); return f'{y+1:04d}-01' if m==12 else f'{y:04d}-{m+1:02d}'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--candidate',required=True); ap.add_argument('--runtime',default=str(DEFAULT_RUNTIME)); ap.add_argument('--apply',action='store_true'); args=ap.parse_args()
    c=json.loads(Path(args.candidate).read_text(encoding='utf-8')); rp=Path(args.runtime); p=json.loads(rp.read_text(encoding='utf-8'))
    if c.get('schema')!='GMFQ_LIQUIDITY_AUD_BUSINESS_CREDIT_REVISION_AWARE_CANDIDATE_V1' or c.get('status')!='GREEN_SOURCE_CANDIDATE_ONLY': raise SystemExit('invalid AUD.credit candidate')
    if (c.get('source') or {}).get('series_key')!=SERIES_KEY: raise SystemExit('unexpected AUD.credit series')
    pr=c.get('proof') or {}
    if pr.get('revision_aware_append_only') is not True or pr.get('historical_runtime_values_frozen') is not True or pr.get('new_observation_transform')!='ROUND_1DP': raise SystemExit('AUD.credit safety contract missing')
    lane=p['AUD']['credit']; od=list(lane['dates']); ov=list(lane['values']); dates=[month(x) for x in od]; vals=[float(x) for x in ov]
    cr=c.get('runtime') or {}
    if cr.get('lane')!='AUD.credit' or month(cr.get('last_date'))!=dates[-1] or abs(float(cr.get('last_value'))-vals[-1])>TOL or int(cr.get('count',-1))!=len(dates): raise SystemExit('candidate built against different AUD.credit runtime')
    new=[]; expected=next_month(dates[-1])
    for row in c.get('new_observations') or []:
        dt=month(row['date']); value=float(row['value'])
        if dt!=expected: raise SystemExit(f'non-contiguous AUD.credit month: {dt} expected {expected}')
        if abs(value-round(value,1))>TOL: raise SystemExit('AUD.credit new value not 1dp normalized')
        new.append((dt,value)); expected=next_month(dt)
    if bool(new)!=bool(c.get('candidate_update_available')): raise SystemExit('candidate update flag mismatch')
    u=json.loads(json.dumps(p)); target=u['AUD']['credit']; orig_dates=list(target['dates']); orig_vals=list(target['values'])
    for dt,value in new: target['dates'].append(dt); target['values'].append(value)
    if new:
        target['last_date']=new[-1][0]; target['last_value']=new[-1][1]
    if target['dates'][:len(orig_dates)]!=orig_dates or target['values'][:len(orig_vals)]!=orig_vals: raise SystemExit('AUD.credit historical rewrite attempted')
    changed=u!=p
    r={'schema':'GMFQ_LIQUIDITY_AUD_BUSINESS_CREDIT_REVISION_AWARE_APPLY_RECEIPT_V1','status':'UPDATE_AVAILABLE' if changed else 'NO_CHANGE','series_key':SERIES_KEY,'before_last_date':dates[-1],'before_last_value':vals[-1],'after_last_date':target.get('last_date'),'after_last_value':target.get('last_value'),'appended_observations':len(new),'applied':bool(args.apply and changed),'runtime_history_rewritten':False,'revision_aware_append_only':True,'publication_performed':False}
    if args.apply and changed: rp.write_text(json.dumps(u,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps(r,indent=2,sort_keys=True))
if __name__=='__main__': main()
