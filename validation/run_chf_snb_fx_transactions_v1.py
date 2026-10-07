#!/usr/bin/env python3
from __future__ import annotations
import json, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'history/pit_v1/CHF_SNB_FX_TRANSACTIONS_QUARTERLY_2020_2026Q1.csv'
EVID=ROOT/'validation/CHF_SNB_FX_TRANSACTIONS_V1_2026-10-07.json'
URL='https://data.snb.ch/api/cube/snbfxtr/data/json/en'
UA={'User-Agent':'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)'}

def fetch():
    req=urllib.request.Request(URL,headers=UA)
    with urllib.request.urlopen(req,timeout=60) as r:
        if r.status!=200: raise RuntimeError(f'HTTP {r.status}')
        return json.load(r)

def main():
    obj=fetch(); ts=obj.get('timeseries')
    if not isinstance(ts,list) or len(ts)!=1: raise RuntimeError('unexpected SNB snbfxtr timeseries structure')
    s=ts[0]
    meta=s.get('metadata') or {}
    if meta.get('key')!='EPB@SNB.snbfxtr{T0}': raise RuntimeError(f'unexpected series key {meta.get("key")}')
    if meta.get('frequency')!='P3M': raise RuntimeError(f'unexpected frequency {meta.get("frequency")}')
    if meta.get('unit')!='In CHF millions': raise RuntimeError(f'unexpected unit {meta.get("unit")}')
    vals=s.get('values') or []
    rows=[]
    for v in vals:
        q=v.get('date'); x=v.get('value')
        if not isinstance(q,str) or '-Q' not in q or not isinstance(x,(int,float)): continue
        rows.append((q,float(x)))
    rows.sort()
    if len(rows)<24: raise RuntimeError(f'insufficient quarters {len(rows)}')
    # Sign semantics anchor: 2022 annual total must equal about CHF -22.3bn, matching
    # the SNB Annual Report statement of net foreign-currency sales in 2022.
    total_2022=sum(v for q,v in rows if q.startswith('2022-'))
    if abs(total_2022 - (-22283.0))>1e-9: raise RuntimeError(f'2022 sign anchor mismatch {total_2022}')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',encoding='utf-8') as f:
        f.write('quarter,net_fx_transactions_chf_mn,policy_interpretation\n')
        for q,v in rows:
            state='FX_PURCHASES_CHF_WEAKENING' if v>0 else ('FX_SALES_CHF_STRENGTHENING' if v<0 else 'LOW_OR_NO_REPORTED_ACTIVITY')
            f.write(f'{q},{v:.1f},{state}\n')
    payload={
      'schema':'GMFQ_CHF_SNB_FX_TRANSACTIONS_V1','status':'PASS','created_at':'2026-10-07',
      'source':'Swiss National Bank data portal','cube':'snbfxtr','series_key':meta.get('key'),
      'frequency':meta.get('frequency'),'unit':meta.get('unit'),'coverage':{'n':len(rows),'first':rows[0][0],'last':rows[-1][0]},
      'sign_semantics':{
        'positive':'net purchases of foreign currency by SNB; CHF-liquidity providing / intended to counter CHF appreciation pressure',
        'negative':'net sales of foreign currency by SNB; tighter monetary conditions / supports CHF',
        'validation_anchor_2022_chf_mn':total_2022,
        'official_annual_report_2022':'net sales of foreign currency equivalent to CHF 22.3bn'
      },
      'pit_policy':'quarterly official transaction total as published by SNB; use only after its publication timestamp in event-time replay',
      'sight_deposits_policy':'context only; never substitute for intervention volumes',
      'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False
    }
    EVID.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(payload,indent=2))
if __name__=='__main__': main()
