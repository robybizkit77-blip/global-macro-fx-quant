#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,hashlib,json
from datetime import date,datetime
from pathlib import Path

CCYS=("USD","EUR","JPY","CAD","AUD")
DIMS=("inflation","labour")
CANON_FIELDS=["reference_period","release_date","value","availability_status"]
UNAVAILABLE={"UNAVAILABLE_OFFICIAL_NOT_PUBLISHED","NOT_PUBLISHED_OFFICIAL"}


def sha256(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()


def iso(raw:str)->str:
    x=(raw or '').strip()
    for fmt in ('%Y-%m-%d','%d/%m/%Y'):
        try:return datetime.strptime(x[:10],fmt).date().isoformat()
        except ValueError:pass
    raise RuntimeError(f'unsupported certified date {raw!r}')


def macro_check(p:Path,dp:str)->dict:
    with p.open(newline='',encoding='utf-8-sig') as f:
        rd=csv.DictReader(f)
        if rd.fieldnames != CANON_FIELDS:
            raise RuntimeError(f'{p}: canonical schema drift {rd.fieldnames}')
        rows=list(rd)
    usable=[]
    for i,r in enumerate(rows,1):
        status=(r['availability_status'] or '').strip()
        rel=(r['release_date'] or '').strip()
        val=(r['value'] or '').strip()
        if status in UNAVAILABLE:
            if rel or val: raise RuntimeError(f'{p}: unavailable row {i} carries release/value')
            continue
        if not rel or not val: raise RuntimeError(f'{p}: available row {i} missing release/value')
        d=iso(rel)
        float(val)
        if d<=dp: usable.append((d,r['reference_period'],float(val)))
    usable.sort()
    if len(usable)<3: raise RuntimeError(f'{p}: fewer than 3 PIT-usable observations at {dp}')
    return {
      'status':'CERTIFIED_IN_CURRENT_SNAPSHOT',
      'file_sha256':sha256(p),
      'rows_total':len(rows),
      'usable_asof_rows':len(usable),
      'latest_release_date_asof':usable[-1][0],
      'latest_reference_period_asof':usable[-1][1],
      'certified_through_decision_point':dp,
    }


def rates_check(p:Path,dp:str)->dict:
    with p.open(newline='',encoding='utf-8-sig') as f:
        rd=csv.DictReader(f); fs=set(rd.fieldnames or [])
        need={'observation_date','yield_2y','yield_10y','first_eligible_decision_date'}
        if not need.issubset(fs): raise RuntimeError(f'{p}: rates schema drift {sorted(fs)}')
        rows=list(rd)
    elig=[]
    for i,r in enumerate(rows,1):
        obs=iso(r['observation_date']); eligible=iso(r['first_eligible_decision_date'])
        if not eligible>obs: raise RuntimeError(f'{p}: same-day/nonconservative eligibility row {i}')
        float(r['yield_2y']); float(r['yield_10y'])
        if eligible<=dp: elig.append((eligible,obs,float(r['yield_2y']),float(r['yield_10y'])))
    elig.sort()
    if not elig: raise RuntimeError(f'{p}: no eligible row at {dp}')
    return {
      'status':'CERTIFIED_IN_CURRENT_SNAPSHOT',
      'file_sha256':sha256(p),
      'rows_total':len(rows),
      'eligible_asof_rows':len(elig),
      'latest_observation_date_asof':elig[-1][1],
      'latest_first_eligible_date_asof':elig[-1][0],
      'certified_through_decision_point':dp,
      'same_day_use_allowed':False,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--contract',required=True,type=Path)
    ap.add_argument('--macro-dir',required=True,type=Path)
    ap.add_argument('--rates-dir',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    a=ap.parse_args()
    c=json.loads(a.contract.read_text(encoding='utf-8'))
    assert c['schema']=='GMFQ_FORWARD_INPUT_READINESS_CONTRACT_V1'
    cur=c['current_certified_decision_point']; nxt=c['next_required_decision_point']
    date.fromisoformat(cur); date.fromisoformat(nxt); assert nxt>cur

    inputs={}; macro_ok=0; rates_ok=0
    for ccy in CCYS:
        for dim in DIMS:
            key=f'{ccy}.{dim}'
            info=macro_check(a.macro_dir/f'{ccy.lower()}_{dim}.csv',cur)
            inputs[key]=info; macro_ok += 1
        key=f'{ccy}.rates_2y_10y'
        info=rates_check(a.rates_dir/f'{ccy.lower()}.csv',cur)
        inputs[key]=info; rates_ok += 1

    assert len(inputs)==c['required_inputs_total']==15
    assert macro_ok==c['macro_inputs']['count']==10
    assert rates_ok==c['rates_inputs']['count']==5

    # A current snapshot may prove readiness only through its explicitly frozen
    # certification boundary. It may NOT self-promote simply because old rows can
    # be numerically selected at a future date. Advancing requires fresh receipts.
    blockers=[
      {'input':f'{ccy}.{dim}','reason':f'fresh atomic PIT refresh receipt required through {nxt}'}
      for ccy in CCYS for dim in DIMS
    ] + [
      {'input':f'{ccy}.rates_2y_10y','reason':f'fresh Temporal-PIT materialization/receipt required through {nxt}'}
      for ccy in CCYS
    ]

    out={
      'schema':'GMFQ_FORWARD_INPUT_READINESS_V1',
      'status':f'READY_THROUGH_{cur}_WAITING_NEXT_REFRESH',
      'current_max_certified_decision_point':cur,
      'next_required_decision_point':nxt,
      'current_inputs_green':15,
      'required_inputs_total':15,
      'macro_green':macro_ok,
      'rates_green':rates_ok,
      'next_decision_point_ready':False,
      'next_decision_point_blockers':blockers,
      'advance_rule':'ALL 10 macro + ALL 5 rates require fresh certified receipts; partial refresh cannot advance max_certified_decision_point',
      'authorized_macro_refresh_path':c['macro_inputs']['authorized_refresh_path'],
      'rates_refresh_rule':c['rates_inputs']['authorized_source_family'],
      'inputs':inputs,
      'historical_backfill_used':False,
      'changes_signal_rules':False,
      'production_signal_authorized':False,
      'sizing_authorized':False,
      'repository_write_performed':False,
    }
    assert out['current_inputs_green']==out['required_inputs_total']
    assert out['next_decision_point_ready'] is False
    assert len(out['next_decision_point_blockers'])==15
    assert out['production_signal_authorized'] is out['sizing_authorized'] is False
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:out[k] for k in ('status','current_max_certified_decision_point','next_required_decision_point','current_inputs_green','macro_green','rates_green','next_decision_point_ready')},indent=2))

if __name__=='__main__': main()
