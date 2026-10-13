#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
DB='MD11'
SERIES='DLCLAEDBLTTO'


def month_key(value: str) -> str:
    parts=str(value).split('-')
    if len(parts)<2:
        raise SystemExit(f'invalid monthly date: {value}')
    y,m=map(int,parts[:2])
    if not 1<=m<=12:
        raise SystemExit(f'invalid monthly date: {value}')
    return f'{y:04d}-{m:02d}'


def next_month(value: str) -> str:
    y,m=map(int,month_key(value).split('-'))
    return f'{y+1:04d}-01' if m==12 else f'{y:04d}-{m+1:02d}'


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--candidate',required=True)
    ap.add_argument('--runtime',default=str(DEFAULT_RUNTIME))
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args()

    candidate=json.loads(Path(args.candidate).read_text(encoding='utf-8'))
    runtime_path=Path(args.runtime)
    liq=json.loads(runtime_path.read_text(encoding='utf-8'))

    if candidate.get('schema')!='GMFQ_LIQUIDITY_JPY_BANK_CREDIT_CANDIDATE_V1':
        raise SystemExit('invalid JPY bank credit candidate schema')
    if candidate.get('status')!='GREEN_SOURCE_CANDIDATE_ONLY' or candidate.get('runtime_match_confirmed') is not True:
        raise SystemExit('JPY bank credit candidate proof is not GREEN')
    source=candidate.get('source') or {}
    if source.get('database')!=DB or source.get('series_id')!=SERIES:
        raise SystemExit('unexpected BOJ JPY bank credit source contract')

    runtime=liq['JPY']['credit']
    dates=list(runtime.get('dates') or [])
    values=list(runtime.get('values') or [])
    if not dates or len(dates)!=len(values):
        raise SystemExit('invalid JPY.credit runtime arrays')
    if month_key(dates[-1])!=month_key(runtime.get('last_date')):
        raise SystemExit('JPY.credit last_date inconsistent with dates array')
    if abs(float(values[-1])-float(runtime.get('last_value')))>1e-6:
        raise SystemExit('JPY.credit last_value inconsistent with values array')

    cand_runtime=candidate.get('runtime') or {}
    if month_key(cand_runtime.get('last_date'))!=month_key(runtime.get('last_date')):
        raise SystemExit('candidate built against different JPY.credit runtime date')
    if abs(float(cand_runtime.get('last_value'))-float(runtime.get('last_value')))>1e-6:
        raise SystemExit('candidate built against different JPY.credit runtime value')

    expected=next_month(runtime['last_date'])
    new=[]
    for row in candidate.get('new_observations') or []:
        d=month_key(row.get('date'))
        v=float(row.get('value'))
        if d!=expected:
            raise SystemExit(f'non-contiguous JPY bank credit sequence: expected {expected}, got {d}')
        if v<=0:
            raise SystemExit(f'invalid JPY bank credit value on {d}: {v}')
        new.append((d,v))
        expected=next_month(d)
    if bool(new)!=bool(candidate.get('candidate_update_available')):
        raise SystemExit('candidate_update_available disagrees with new_observations')

    updated=json.loads(json.dumps(liq))
    target=updated['JPY']['credit']
    n=len(target['dates'])
    old_dates=list(target['dates'])
    old_values=list(target['values'])
    for d,v in new:
        target['dates'].append(d)
        target['values'].append(v)
    if new:
        target['last_date']=new[-1][0]
        target['last_value']=new[-1][1]
    if target['dates'][:n]!=old_dates or target['values'][:n]!=old_values:
        raise SystemExit('JPY bank credit controlled apply attempted to rewrite history')

    changed=updated!=liq
    receipt={
        'schema':'GMFQ_LIQUIDITY_JPY_BANK_CREDIT_APPLY_RECEIPT_V1',
        'status':'UPDATE_AVAILABLE' if changed else 'NO_CHANGE',
        'database':DB,'series_id':SERIES,
        'before_last_date':runtime['last_date'],'before_last_value':runtime['last_value'],
        'after_last_date':target['last_date'],'after_last_value':target['last_value'],
        'appended_observations':len(new),
        'applied':bool(args.apply and changed),
        'publication_performed':False,
    }
    if args.apply and changed:
        runtime_path.write_text(json.dumps(updated,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2,sort_keys=True))

if __name__=='__main__': main()
