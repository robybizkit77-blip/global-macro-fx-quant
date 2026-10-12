#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, json, math
from bisect import bisect_right
from datetime import date
from pathlib import Path

CCYS=("EUR","JPY","CAD","AUD")
OFFICIAL_UNAVAILABLE={"UNAVAILABLE_OFFICIAL_NOT_PUBLISHED","NOT_PUBLISHED_OFFICIAL"}


def add_months(y:int,m:int,n:int):
    z=y*12+(m-1)+n
    return z//12,z%12+1


def month_points(start_period:str,end_dp:str):
    sy,sm=map(int,start_period.split('-')); ey,em=map(int,end_dp[:7].split('-'))
    out=[]; y,m=sy,sm
    while (y,m)<=(ey,em):
        out.append(f"{y:04d}-{m:02d}-10")
        y,m=add_months(y,m,1)
    return out


def load_rates(path:Path):
    rows=[]
    with path.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            rows.append({'obs':r['observation_date'],'eligible':r['first_eligible_decision_date'],'y2':float(r['yield_2y'])})
    rows.sort(key=lambda r:(r['eligible'],r['obs']))
    return rows


def select_rate(rows,dp):
    eligible=[r for r in rows if r['eligible']<=dp]
    if not eligible: return None
    r=eligible[-1]
    if not (r['obs']<dp and r['eligible']<=dp): raise RuntimeError(f'temporal violation {dp}: {r}')
    return r


def load_macro(path:Path):
    rows=[]
    with path.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            status=(r.get('availability_status') or '').strip()
            if status in OFFICIAL_UNAVAILABLE: continue
            rel=(r.get('release_date') or '').strip()[:10]
            val=(r.get('value') or '').strip()
            if not rel or not val: raise RuntimeError(f'invalid canonical macro row in {path}: {r}')
            date.fromisoformat(rel)
            rows.append((rel,float(val)))
    rows.sort(); return rows


def latest_two(rows,asof):
    dates=[d for d,_ in rows]; i=bisect_right(dates,asof)-1
    if i<1: return None,None
    return rows[i][1],rows[i-1][1]


def change(rows,asof):
    cur,prev=latest_two(rows,asof)
    return None if cur is None or prev is None else cur-prev


def sgn(x,eps=1e-12): return 1 if x>eps else (-1 if x<-eps else 0)


def classify(repricing,inf_pressure,lab_pressure):
    if inf_pressure is None or lab_pressure is None: return 'UNAVAILABLE'
    s=sgn(repricing)
    if s==0: return 'MIXED'
    votes=[sgn(inf_pressure),sgn(lab_pressure)]
    agree=sum(v==s for v in votes); opp=sum(v==-s for v in votes)
    if agree==2: return 'ALIGNED'
    if agree==1: return 'MIXED'
    if opp>=1: return 'CONTRADICTORY'
    return 'MIXED'


def load_ecb(path:Path):
    out={}
    with path.open(newline='',encoding='utf-8-sig') as f:
        rd=csv.DictReader(f); fs=rd.fieldnames or []
        dk=next(k for k in ['TIME_PERIOD','TIME PERIOD','Date','DATE'] if k in fs)
        vk=next(k for k in ['OBS_VALUE','OBS VALUE','Value','VALUE'] if k in fs)
        for r in rd:
            ds=(r.get(dk) or '')[:10]; vs=(r.get(vk) or '').strip()
            try: date.fromisoformat(ds); v=float(vs)
            except Exception: continue
            if v>0: out[ds]=v
    return out


def first_common_after(dp,*series):
    common=sorted(set.intersection(*(set(s.keys()) for s in series)))
    i=bisect_right(common,dp)
    return None if i>=len(common) else common[i]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--contract',required=True,type=Path)
    ap.add_argument('--rates-dir',required=True,type=Path)
    ap.add_argument('--macro-dir',required=True,type=Path)
    ap.add_argument('--fx-dir',required=True,type=Path)
    ap.add_argument('--max-certified-decision-point',required=True)
    ap.add_argument('--output-ledger',required=True,type=Path)
    ap.add_argument('--output-snapshot',required=True,type=Path)
    a=ap.parse_args()
    c=json.loads(a.contract.read_text())
    assert c['schema']=='GMFQ_G4USD_DOVISH_DIVERGENCE_FORWARD_SHADOW_CONTRACT_V1'
    assert c['signal_rule']['state']=='CONTRADICTORY' and c['signal_rule']['d_diff_2y_condition']=='<0'
    assert c['eligible_currencies']==list(CCYS)
    cutoff=c['historical_cutoff_reference_period']
    max_dp=date.fromisoformat(a.max_certified_decision_point).isoformat()

    rates={x:load_rates(a.rates_dir/f'{x.lower()}.csv') for x in (*CCYS,'USD')}
    macro={}
    for x in (*CCYS,'USD'):
        macro[x]={
            'inf':load_macro(a.macro_dir/f'{x.lower()}_inflation.csv'),
            'lab':load_macro(a.macro_dir/f'{x.lower()}_labour.csv'),
        }
    usd_fx=load_ecb(a.fx_dir/'USD.csv')
    local_fx={'EUR':None,'JPY':load_ecb(a.fx_dir/'JPY.csv'),'CAD':load_ecb(a.fx_dir/'CAD.csv'),'AUD':load_ecb(a.fx_dir/'AUD.csv')}

    # Include August only as the previous repricing anchor; signals are strictly post-cutoff.
    dps=month_points(cutoff,max_dp)
    snapshots={x:[] for x in CCYS}
    for x in CCYS:
        for dp in dps:
            lr=select_rate(rates[x],dp); ur=select_rate(rates['USD'],dp)
            if lr is None or ur is None: continue
            if x=='EUR': fd=first_common_after(dp,usd_fx); px=usd_fx.get(fd) if fd else None
            else:
                fd=first_common_after(dp,usd_fx,local_fx[x])
                px=(usd_fx[fd]/local_fx[x][fd]) if fd else None
            snapshots[x].append({'dp':dp,'reference_period':dp[:7],'local_obs':lr['obs'],'usd_obs':ur['obs'],'diff_2y':lr['y2']-ur['y2'],'fixing_date':fd,'price':px})

    signals=[]; audit=[]
    for x in CCYS:
        seq=snapshots[x]
        for i in range(1,len(seq)):
            cur=seq[i]; prev=seq[i-1]
            if cur['reference_period']<=cutoff: continue
            d2=cur['diff_2y']-prev['diff_2y']
            asof=cur['dp']
            dli=change(macro[x]['inf'],asof); dui=change(macro['USD']['inf'],asof)
            dll=change(macro[x]['lab'],asof); dul=change(macro['USD']['lab'],asof)
            infp=None if dli is None or dui is None else dli-dui
            labp=None if dll is None or dul is None else -(dll-dul)
            state=classify(d2,infp,labp)
            row={'currency':x,'reference_period':cur['reference_period'],'decision_point':cur['dp'],'state':state,'d_diff_2y':d2,'inflation_pressure':infp,'labour_pressure':labp,'signal_eligible':state=='CONTRADICTORY' and d2<0}
            audit.append(row)
            if not row['signal_eligible']: continue
            # Dovish front-end direction (<0) means local weaker vs USD.
            sig=-1
            out1=out3=None
            if cur['price'] is not None and i+1<len(seq) and seq[i+1]['price'] is not None:
                out1=sig*math.log(seq[i+1]['price']/cur['price'])
            if cur['price'] is not None and i+3<len(seq) and seq[i+3]['price'] is not None:
                out3=sig*math.log(seq[i+3]['price']/cur['price'])
            signals.append({'currency':x,'reference_period':cur['reference_period'],'decision_point':cur['dp'],'state':'CONTRADICTORY','d_diff_2y':d2,'signal_direction':'LOCAL_WEAKER_VS_USD','entry_fixing_date':cur['fixing_date'],'outcome_1m':out1,'outcome_3m':out3})

    ledger={'schema':'GMFQ_G4USD_DOVISH_DIVERGENCE_FORWARD_SHADOW_LEDGER_V1','contract_schema':c['schema'],'historical_cutoff_reference_period':cutoff,'append_only':True,'signals':signals}
    snap={'schema':'GMFQ_G4USD_DOVISH_DIVERGENCE_FORWARD_COLLECTOR_SNAPSHOT_V1','status':'COLLECTED_FROM_FROZEN_CERTIFIED_INPUT_SNAPSHOTS','max_certified_decision_point':max_dp,'rates_source':'temporal-PIT rates store pinned by workflow','macro_source':'exact GREEN alignment readiness artifact plus release-date spelling normalization','candidate_rule':'state == CONTRADICTORY and d_diff_2y < 0','audit_rows':audit,'signals_total':len(signals),'matured_1m':sum(r['outcome_1m'] is not None for r in signals),'matured_3m':sum(r['outcome_3m'] is not None for r in signals),'production_signal_authorized':False,'sizing_authorized':False,'future_decision_points_after_max_certified':'WITHHELD_INPUT_SNAPSHOT_NOT_EXTENDED'}
    a.output_ledger.parent.mkdir(parents=True,exist_ok=True)
    a.output_ledger.write_text(json.dumps(ledger,indent=2,sort_keys=True)+'\n')
    a.output_snapshot.write_text(json.dumps(snap,indent=2,sort_keys=True)+'\n')
    print(json.dumps(snap,indent=2,sort_keys=True))

if __name__=='__main__': main()
