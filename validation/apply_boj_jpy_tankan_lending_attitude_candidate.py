#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
DB='CO'
SERIES='TK99F0000612GCQ00000'


def quarter_key(value: str) -> str:
    s=str(value)
    if '-Q' not in s:
        raise SystemExit(f'invalid quarterly runtime date: {value!r}')
    y,q=s.split('-Q',1)
    y=int(y); q=int(q)
    if q not in (1,2,3,4):
        raise SystemExit(f'invalid quarterly runtime date: {value!r}')
    return f'{y:04d}-Q{q}'


def next_quarter(value: str) -> str:
    yq=quarter_key(value)
    y=int(yq[:4]); q=int(yq[-1])
    return f'{y+1:04d}-Q1' if q==4 else f'{y:04d}-Q{q+1}'


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--candidate',required=True)
    ap.add_argument('--runtime',default=str(DEFAULT_RUNTIME))
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args()

    candidate=json.loads(Path(args.candidate).read_text(encoding='utf-8'))
    runtime_path=Path(args.runtime)
    liq=json.loads(runtime_path.read_text(encoding='utf-8'))

    if candidate.get('schema')!='GMFQ_LIQUIDITY_JPY_TANKAN_LENDING_ATTITUDE_CANDIDATE_V1':
        raise SystemExit('invalid JPY Tankan candidate schema')
    if candidate.get('status')!='GREEN_SOURCE_CANDIDATE_ONLY' or candidate.get('runtime_match_confirmed') is not True:
        raise SystemExit('JPY Tankan candidate proof is not GREEN')
    if candidate.get('runtime_history_unchanged_by_current_vintage') is not True:
        raise SystemExit('JPY Tankan current-vintage history proof missing')
    source=candidate.get('source') or {}
    if source.get('database')!=DB or source.get('series_id')!=SERIES:
        raise SystemExit('unexpected BOJ Tankan source contract')
    if source.get('frequency')!='QUARTERLY' or source.get('unit')!='% points':
        raise SystemExit('BOJ Tankan frequency/unit contract mismatch')
    if source.get('survey_item')!='612' or source.get('enterprise_size')!='All Enterprises' or source.get('industry')!='All industries' or source.get('result_type')!='Actual result':
        raise SystemExit('BOJ Tankan semantic identity mismatch')

    runtime=liq['JPY']['conditions']
    dates=list(runtime.get('dates') or [])
    values=list(runtime.get('values') or [])
    if not dates or len(dates)!=len(values):
        raise SystemExit('invalid JPY.conditions runtime arrays')
    if quarter_key(dates[-1])!=quarter_key(runtime.get('last_date')):
        raise SystemExit('JPY.conditions last_date inconsistent with dates array')
    if abs(float(values[-1])-float(runtime.get('last_value')))>1e-9:
        raise SystemExit('JPY.conditions last_value inconsistent with values array')

    cand_runtime=candidate.get('runtime') or {}
    if quarter_key(cand_runtime.get('last_date'))!=quarter_key(runtime.get('last_date')):
        raise SystemExit('candidate built against different JPY.conditions runtime date')
    if abs(float(cand_runtime.get('last_value'))-float(runtime.get('last_value')))>1e-9:
        raise SystemExit('candidate built against different JPY.conditions runtime value')

    expected=next_quarter(runtime['last_date'])
    new=[]
    existing={quarter_key(d) for d in dates}
    for row in candidate.get('new_observations') or []:
        d=quarter_key(row.get('date'))
        v=float(row.get('value'))
        if d in existing:
            raise SystemExit(f'duplicate JPY Tankan quarter: {d}')
        if d!=expected:
            raise SystemExit(f'non-contiguous JPY Tankan sequence: expected {expected}, got {d}')
        if not -100.0<=v<=100.0:
            raise SystemExit(f'invalid Tankan D.I. value on {d}: {v}')
        new.append((d,v))
        expected=next_quarter(d)
    if bool(new)!=bool(candidate.get('candidate_update_available')):
        raise SystemExit('candidate_update_available disagrees with new_observations')

    updated=json.loads(json.dumps(liq))
    target=updated['JPY']['conditions']
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
        raise SystemExit('JPY Tankan controlled apply attempted to rewrite history')

    changed=updated!=liq
    receipt={
        'schema':'GMFQ_LIQUIDITY_JPY_TANKAN_LENDING_ATTITUDE_APPLY_RECEIPT_V1',
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

if __name__=='__main__':
    main()
