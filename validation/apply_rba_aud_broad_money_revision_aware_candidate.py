#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path

DEFAULT_RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
SERIES_KEY='DMABMS'
TOL=1e-9

def next_month(v):
    y,m=map(int,str(v)[:7].split('-'))
    return f'{y+1:04d}-01' if m==12 else f'{y:04d}-{m+1:02d}'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--candidate',required=True); ap.add_argument('--runtime',default=str(DEFAULT_RUNTIME)); ap.add_argument('--apply',action='store_true'); args=ap.parse_args()
    c=json.loads(Path(args.candidate).read_text(encoding='utf-8')); rp=Path(args.runtime); p=json.loads(rp.read_text(encoding='utf-8'))
    if c.get('schema')!='GMFQ_LIQUIDITY_AUD_BROAD_MONEY_REVISION_AWARE_CANDIDATE_V1' or c.get('status')!='GREEN_SOURCE_CANDIDATE_ONLY': raise SystemExit('invalid AUD.money candidate')
    if (c.get('source') or {}).get('series_key')!=SERIES_KEY: raise SystemExit('unexpected AUD.money series')
    pr=c.get('proof') or {}
    if pr.get('revision_aware_append_only') is not True or pr.get('historical_runtime_values_frozen') is not True or pr.get('new_observation_transform')!='ROUND_1DP': raise SystemExit('AUD.money safety/transform contract missing')
    lane=p['AUD']['money']; dates=[str(x)[:7] for x in lane['dates']]; vals=[float(x) for x in lane['values']]
    cr=c.get('runtime') or {}
    if cr.get('lane')!='AUD.money' or str(cr.get('last_date'))[:7]!=dates[-1] or abs(float(cr.get('last_value'))-vals[-1])>TOL or int(cr.get('count',-1))!=len(dates): raise SystemExit('candidate built against different AUD.money runtime')
    new=[]; expected=next_month(dates[-1])
    for row in c.get('new_observations') or []:
        dt=str(row['date'])[:7]; value=float(row['value'])
        if dt!=expected: raise SystemExit(f'non-contiguous AUD.money month: {dt} expected {expected}')
        if abs(value-round(value,1))>TOL: raise SystemExit('AUD.money new value not 1dp normalized')
        new.append((dt,value)); expected=next_month(dt)
    if bool(new)!=bool(c.get('candidate_update_available')): raise SystemExit('candidate update flag mismatch')
    u=json.loads(json.dumps(p)); target=u['AUD']['money']; od=list(target['dates']); ov=list(target['values'])
    for dt,value in new: target['dates'].append(dt); target['values'].append(value)
    if new: target['last_date']=new[-1][0]; target['last_value']=new[-1][1]
    if target['dates'][:len(od)]!=od or target['values'][:len(ov)]!=ov: raise SystemExit('AUD.money historical rewrite attempted')
    changed=u!=p
    r={'schema':'GMFQ_LIQUIDITY_AUD_BROAD_MONEY_REVISION_AWARE_APPLY_RECEIPT_V1','status':'UPDATE_AVAILABLE' if changed else 'NO_CHANGE','series_key':SERIES_KEY,'before_last_date':lane['last_date'],'before_last_value':lane['last_value'],'after_last_date':target['last_date'],'after_last_value':target['last_value'],'appended_observations':len(new),'applied':bool(args.apply and changed),'runtime_history_rewritten':False,'revision_aware_append_only':True,'publication_performed':False}
    if args.apply and changed: rp.write_text(json.dumps(u,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps(r,indent=2,sort_keys=True))
if __name__=='__main__': main()
