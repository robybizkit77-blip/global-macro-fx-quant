#!/usr/bin/env python3
"""Apply only a source-proven, bounded BOJ revision to JPY.money."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

DEFAULT_RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
DB='MD02'; SERIES='MAM1XAM3M3MO'; EPS=1e-6
SCHEMA='GMFQ_LIQUIDITY_JPY_M3_REVISION_AWARE_CANDIDATE_V1'
SOURCE={'publisher':'Bank of Japan','api':'Time-Series Data Search API / getDataCode','database':DB,'series_id':SERIES,'name':'M3/Average Amounts Outstanding/Seasonally Adjusted/Money Stock','unit':'100 million yen','frequency':'MONTHLY','seasonal_adjustment':'Seasonally Adjusted'}

def month(value):
    digits=''.join(ch for ch in str(value) if ch.isdigit())
    if len(digits)<6: raise ValueError(f'invalid monthly date: {value!r}')
    y,m=int(digits[:4]),int(digits[4:6])
    if not 1<=m<=12: raise ValueError(f'invalid monthly date: {value!r}')
    return f'{y:04d}-{m:02d}'

def next_month(value):
    y,m=map(int,month(value).split('-')); return f'{y+1:04d}-01' if m==12 else f'{y:04d}-{m+1:02d}'

def fingerprint(dates,values):
    raw=json.dumps({'dates':[month(d) for d in dates],'values':[float(v) for v in values]},sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(raw).hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--candidate',required=True); ap.add_argument('--runtime',default=str(DEFAULT_RUNTIME)); ap.add_argument('--apply',action='store_true'); args=ap.parse_args()
    candidate=json.loads(Path(args.candidate).read_text(encoding='utf-8')); runtime_path=Path(args.runtime); liq=json.loads(runtime_path.read_text(encoding='utf-8'))
    if candidate.get('schema')!=SCHEMA or candidate.get('status')!='GREEN_REVISION_AWARE_CANDIDATE': raise SystemExit('JPY M3 revision-aware candidate proof is not GREEN')
    if any((candidate.get('source') or {}).get(k)!=v for k,v in SOURCE.items()): raise SystemExit('unexpected BOJ JPY M3 provenance contract')
    money=liq['JPY']['money']; dates=list(money.get('dates') or []); values=list(money.get('values') or [])
    if not dates or len(dates)!=len(values) or month(dates[-1])!=month(money.get('last_date')) or abs(float(values[-1])-float(money.get('last_value')))>EPS: raise SystemExit('invalid JPY.money runtime arrays')
    baseline=candidate.get('runtime') or {}
    if baseline.get('count')!=len(dates) or month(baseline.get('last_date'))!=month(money['last_date']) or abs(float(baseline.get('last_value'))-float(money['last_value']))>EPS or baseline.get('money_fingerprint_sha256')!=fingerprint(dates,values): raise SystemExit('candidate was not built against this exact JPY.money runtime vintage')
    window=candidate.get('revision_window') or {}; start,end=window.get('start_date'),window.get('end_date')
    if window.get('months')!=3 or not start or end!=month(money['last_date']): raise SystemExit('invalid bounded BOJ revision window')
    index={month(d):i for i,d in enumerate(dates)}; revised=[]; seen=set()
    for item in candidate.get('revised_observations') or []:
        d,old,new=month(item.get('date')),float(item.get('old_value')),float(item.get('new_value'))
        if d in seen or d not in index or not start<=d<=end or abs(float(values[index[d]])-old)>EPS or new<=0 or abs(old-new)<=EPS: raise SystemExit('invalid or stale BOJ revision receipt')
        seen.add(d); revised.append((d,index[d],old,new))
    appended=[]; expected=next_month(money['last_date'])
    for item in candidate.get('appended_observations') or []:
        d,value=month(item.get('date')),float(item.get('value'))
        if d!=expected or value<=0: raise SystemExit(f'non-contiguous or invalid JPY M3 append: expected {expected}, got {d}')
        appended.append((d,value)); expected=next_month(d)
    if bool(revised or appended)!=bool(candidate.get('candidate_update_available')): raise SystemExit('candidate_update_available disagrees with revision/append receipts')
    updated=json.loads(json.dumps(liq)); target=updated['JPY']['money']
    for _,i,_,new in revised: target['values'][i]=new
    for d,value in appended: target['dates'].append(d); target['values'].append(value)
    if appended: target['last_date'],target['last_value']=appended[-1]
    changed=updated!=liq; receipt={'schema':'GMFQ_LIQUIDITY_JPY_M3_REVISION_AWARE_APPLY_RECEIPT_V1','status':'UPDATE_AVAILABLE' if changed else 'NO_CHANGE','database':DB,'series_id':SERIES,'before_last_date':money['last_date'],'before_last_value':money['last_value'],'after_last_date':target['last_date'],'after_last_value':target['last_value'],'revised_months':[{'date':d,'old_value':old,'new_value':new} for d,_,old,new in revised],'appended_months':[{'date':d,'value':value} for d,value in appended],'applied':bool(args.apply and changed),'publication_performed':False}
    if args.apply and changed: runtime_path.write_text(json.dumps(updated,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2,sort_keys=True))

if __name__=='__main__': main()
