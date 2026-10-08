#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, pathlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
CURRENT=ROOT/'live_data'/'sections'/'V250_COT_CHART_DATA.json'
sys.path.insert(0,str(ROOT/'validation'))
from verify_cftc_current_snapshot import CURRENCIES, fetch, parse_block

ORDER=['EUR','GBP','JPY','CHF','AUD','NZD','CAD','USD']
FIELDS=['dates','net','long','short','percentile','netoi']
WINDOW=104

def pct_rank(values:list[int], current:int)->float:
    if len(values)!=WINDOW:
        raise ValueError(f'percentile window must be exactly {WINDOW}, got {len(values)}')
    return round(sum(1 for v in values if int(v)<=int(current))/WINDOW*100,6)

def fetch_official()->dict:
    pages={}; rows={}
    for c,(code,url) in CURRENCIES.items():
        pages.setdefault(url,fetch(url))
        rows[c]=parse_block(pages[url],code)
    dates={x['date'] for x in rows.values()}
    if len(dates)!=1:
        raise ValueError('CFTC cross-market date mismatch: '+repr(rows))
    return rows

def validate_series(cur:dict)->str:
    if set(cur)!=set(ORDER):
        raise ValueError('V250 must contain exactly 8 G8 currencies')
    dates=set()
    for c in ORDER:
        s=cur[c]
        for k in FIELDS:
            if k not in s: raise ValueError(f'{c}: missing {k}')
        n=len(s['dates'])
        if n!=WINDOW: raise ValueError(f'{c}: expected {WINDOW} observations, got {n}')
        if any(len(s[k])!=n for k in FIELDS[1:]):
            raise ValueError(f'{c}: inconsistent series lengths')
        if s['dates']!=sorted(s['dates']): raise ValueError(f'{c}: dates not sorted')
        dates.add(s['dates'][-1])
    if len(dates)!=1: raise ValueError('Current COT cross-currency latest date mismatch')
    return next(iter(dates))

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',required=True)
    ap.add_argument('--current',default=str(CURRENT))
    a=ap.parse_args()
    cur=json.loads(pathlib.Path(a.current).read_text())
    current_date=validate_series(cur)
    official=fetch_official()
    official_date=next(iter({x['date'] for x in official.values()}))
    if official_date < current_date:
        raise SystemExit(f'CFTC source regressed: official {official_date} < runtime {current_date}')
    out=copy.deepcopy(cur)
    if official_date == current_date:
        mismatches=[]
        for c in ORDER:
            row=official[c]; s=cur[c]
            observed={'long':int(s['long'][-1]),'short':int(s['short'][-1]),'net':int(s['net'][-1]),'netoi':round(float(s['netoi'][-1]),3)}
            expected={'long':row['long'],'short':row['short'],'net':row['net'],'netoi':round(float(row['netoi']),3)}
            for k in expected:
                if observed[k]!=expected[k]: mismatches.append({'currency':c,'field':k,'runtime':observed[k],'official':expected[k]})
        if mismatches: raise SystemExit('same-date CFTC mismatch: '+json.dumps(mismatches))
        status='NO_UPDATE'
    else:
        for c in ORDER:
            s=out[c]; row=official[c]
            if official_date in s['dates']:
                raise SystemExit(f'{c}: new official date already exists unexpectedly')
            new_net=list(s['net'][-(WINDOW-1):])+[int(row['net'])]
            vals={
                'dates':list(s['dates'][-(WINDOW-1):])+[official_date],
                'net':new_net,
                'long':list(s['long'][-(WINDOW-1):])+[int(row['long'])],
                'short':list(s['short'][-(WINDOW-1):])+[int(row['short'])],
                'netoi':list(s['netoi'][-(WINDOW-1):])+[round(float(row['netoi']),3)],
            }
            vals['percentile']=list(s['percentile'][-(WINDOW-1):])+[pct_rank(new_net,int(row['net']))]
            out[c]=vals
        validate_series(out)
        status='CANDIDATE_READY'
    pathlib.Path(a.output).write_text(json.dumps(out,separators=(',',':'),ensure_ascii=False)+'\n')
    result={
        'status':status,'source':'CFTC Legacy Futures Only current reports','current_as_of':current_date,'official_as_of':official_date,
        'currencies':8,'window_weeks':WINDOW,'candidate_changed':out!=cur,
        'official':official,
        'policy':{'price_confirmation':'WITHHELD','orphan_open_interest':'NOT_STORED','single_new_week_only':True}
    }
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0

if __name__=='__main__': sys.exit(main())
