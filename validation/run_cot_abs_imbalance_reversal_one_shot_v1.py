#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, math, pathlib, statistics, urllib.request, zipfile
from collections import defaultdict
from datetime import date, datetime

import build_cot_ultraconservative_pit_calendar_v1 as pit
import discover_cot_conservative_availability_calendar_v1 as cotbase
from validate_cot_flow_fx_price_readiness_v1 import fetch_one

CONTRACT_PATH=pathlib.Path('validation/COT_ABS_IMBALANCE_REVERSAL_EDGE_CONTRACT_V1_2026-10-12.json')
PIT_POLICY_PATH=pathlib.Path('validation/COT_ULTRACONSERVATIVE_PIT_POLICY_V1_2026-10-11.json')
PRICE_CONTRACT_PATH=pathlib.Path('validation/COT_FLOW_FX_PRICE_SOURCE_CONTRACT_V1_2026-10-11.json')
OUTDIR=pathlib.Path('/tmp/cot-abs-imbalance-reversal-one-shot')
IDX_REPORT_DATE=2; IDX_CFTC_CODE=3; IDX_OPEN_INTEREST=7; IDX_NC_LONG=8; IDX_NC_SHORT=9

def fnum(s:str)->float:
    return float(s.strip().strip('"').replace(',',''))

def load_cot_positions(currencies):
    wanted={cotbase.CODES[c]:c for c in currencies}; out={c:[] for c in currencies}
    for year in cotbase.YEARS:
        req=urllib.request.Request(cotbase.BASE.format(year=year),headers={'User-Agent':cotbase.UA,'Accept':'application/zip,*/*;q=0.8'})
        with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            members=[n for n in z.namelist() if not n.endswith('/')]
            if len(members)!=1: raise RuntimeError(f'{year}: unexpected ZIP members {members}')
            text=z.read(members[0]).decode('latin-1')
        seen=set()
        for row in csv.reader(io.StringIO(text)):
            if len(row)<=IDX_NC_SHORT: continue
            code=row[IDX_CFTC_CODE].strip().strip('"')
            if code not in wanted: continue
            ccy=wanted[code]; report=datetime.strptime(row[IDX_REPORT_DATE].strip().strip('"'),'%Y-%m-%d').date()
            oi=fnum(row[IDX_OPEN_INTEREST]); nc_long=fnum(row[IDX_NC_LONG]); nc_short=fnum(row[IDX_NC_SHORT])
            if not (oi>0 and nc_long>=0 and nc_short>=0): raise RuntimeError(f'{ccy} {report}: invalid CFTC fields')
            key=(ccy,report)
            if key in seen: raise RuntimeError(f'{year}: duplicate {key}')
            seen.add(key); out[ccy].append({'report_date':report,'net_oi':(nc_long-nc_short)/oi})
    for ccy,rows in out.items():
        rows.sort(key=lambda x:x['report_date'])
        if len(rows)<400: raise RuntimeError(f'{ccy}: insufficient COT rows')
    sets=[{r['report_date'] for r in out[c]} for c in currencies]
    if any(s!=sets[0] for s in sets[1:]): raise RuntimeError('COT currency date sets differ')
    return out

def build_pit_map(report_dates):
    rows=[pit.transform(cotbase.candidate_row(d.isoformat())) for d in report_dates]
    eligible=sum(bool(r['research_pit_eligible']) for r in rows)
    if (len(rows),eligible,len(rows)-eligible)!=(458,448,10): raise RuntimeError('unexpected PIT coverage')
    return {date.fromisoformat(r['report_date']):r for r in rows}

def load_fx_prices(price_contract):
    prices={}
    for ccy,spec in price_contract['series'].items():
        got,_,rows=fetch_one((ccy,spec))
        if got!=ccy: raise RuntimeError('FX source mismatch')
        xs=[]
        for d,v in rows:
            p=v if spec['transform_to_local_currency_vs_usd']=='identity' else 1.0/v
            if not (math.isfinite(p) and p>0): raise RuntimeError(f'{ccy}: invalid price')
            xs.append((d,p))
        if len(xs)!=2187 or xs[0][0]!=date(2018,1,2) or xs[-1][0]!=date(2026,10,2): raise RuntimeError(f'{ccy}: FX readiness mismatch')
        prices[ccy]=xs
    return prices

def first_index_on_or_after(rows,target):
    lo,hi=0,len(rows)
    while lo<hi:
        mid=(lo+hi)//2
        if rows[mid][0]<target: lo=mid+1
        else: hi=mid
    return lo if lo<len(rows) else None

def sample_sharpe(xs):
    if len(xs)<2: return None
    sd=statistics.stdev(xs)
    return None if sd==0 else statistics.mean(xs)/sd*math.sqrt(52)

def max_drawdown(log_returns):
    wealth=peak=1.0; mdd=0.0
    for r in log_returns:
        wealth*=math.exp(r); peak=max(peak,wealth); mdd=min(mdd,wealth/peak-1.0)
    return mdd

def summarize(rows):
    rs=[r['observation_return'] for r in rows]
    return {'n':len(rows),'sharpe':sample_sharpe(rs),'directional_accuracy':sum(x>0 for x in rs)/len(rs) if rs else None,
            'total_log_return':sum(rs),'max_drawdown':max_drawdown(rs) if rs else None,
            'positive_imbalance_signals':sum(r['net_oi']>=0.30 for r in rows),'negative_imbalance_signals':sum(r['net_oi']<=-0.30 for r in rows)}

def main():
    contract=json.loads(CONTRACT_PATH.read_text()); policy=json.loads(PIT_POLICY_PATH.read_text()); price_contract=json.loads(PRICE_CONTRACT_PATH.read_text())
    assert contract['status']=='PREDECLARED_NO_RESULTS_OBSERVED'
    assert policy['status']=='PREDECLARED_NO_EDGE_RESULTS_OBSERVED'
    assert price_contract['status']=='PREDECLARED_NO_COT_EDGE_RESULTS_OBSERVED'
    assert contract['signal']['positive_extreme_threshold']==0.30
    assert contract['signal']['negative_extreme_threshold']==-0.30
    currencies=contract['universe']['currencies']
    positions=load_cot_positions(currencies)
    pit_map=build_pit_map([r['report_date'] for r in positions[currencies[0]]])
    prices=load_fx_prices(price_contract)
    observations={c:[] for c in currencies}; exclusions=defaultdict(int)
    for ccy in currencies:
        for cur in positions[ccy]:
            pcur=pit_map[cur['report_date']]
            if not pcur['research_pit_eligible']:
                exclusions['current_report_withheld']+=1; continue
            if cur['net_oi']>=0.30: signal=-1
            elif cur['net_oi']<=-0.30: signal=1
            else:
                exclusions['non_imbalance_no_position']+=1; continue
            available=date.fromisoformat(pcur['research_available_from']); px=prices[ccy]; idx=first_index_on_or_after(px,available)
            if idx is None or idx+5>=len(px): exclusions['insufficient_future_fx_prices']+=1; continue
            entry_d,entry_p=px[idx]; exit_d,exit_p=px[idx+5]; raw=math.log(exit_p/entry_p)
            observations[ccy].append({'currency':ccy,'report_date':cur['report_date'],'research_available_from':available,'entry_date':entry_d,'exit_date':exit_d,
                                      'net_oi':cur['net_oi'],'signal':signal,'fx_log_return':raw,'observation_return':signal*raw})
    oos={}; split_receipt={}
    for ccy in currencies:
        rows=sorted(observations[ccy],key=lambda r:(r['entry_date'],r['report_date']))
        cut=math.floor(0.60*len(rows)); oos[ccy]=rows[cut:]
        split_receipt[ccy]={'eligible_imbalance_signals':len(rows),'diagnostic_n':cut,'oos_n':len(rows)-cut}
    pooled=[r for c in currencies for r in oos[c]]; weekly=defaultdict(list)
    for r in pooled:
        iso=r['entry_date'].isocalendar(); weekly[(iso.year,iso.week)].append(r['observation_return'])
    weekly_series=[sum(weekly[k])/len(weekly[k]) for k in sorted(weekly)]
    panel_sharpe=sample_sharpe(weekly_series); accuracy=sum(r['observation_return']>0 for r in pooled)/len(pooled) if pooled else None
    currency_stats={c:summarize(oos[c]) for c in currencies}
    positive_ccy=sum(currency_stats[c]['sharpe'] is not None and currency_stats[c]['sharpe']>0 for c in currencies)
    shares={c:len(oos[c])/len(pooled) if pooled else None for c in currencies}; max_share=max(shares.values()) if pooled else None
    gates={
      'oos_panel_annualized_sharpe_ge_0_50': panel_sharpe is not None and panel_sharpe>=0.50,
      'oos_directional_accuracy_ge_0_52': accuracy is not None and accuracy>=0.52,
      'positive_currency_oos_sharpes_ge_5': positive_ccy>=5,
      'minimum_oos_signal_observations_per_currency_ge_20': all(len(oos[c])>=20 for c in currencies),
      'minimum_pooled_oos_signal_observations_ge_150': len(pooled)>=150,
      'max_single_currency_share_le_0_30': max_share is not None and max_share<=0.30,
    }
    edge=all(gates.values())
    side_stats={'positive_imbalance_reversal':summarize([r for r in pooled if r['net_oi']>=0.30]),
                'negative_imbalance_reversal':summarize([r for r in pooled if r['net_oi']<=-0.30])}
    result={'schema':'GMFQ_COT_ABS_IMBALANCE_REVERSAL_ONE_SHOT_RESULT_V1','verdict':'PASS_PREDECLARED_COT_ABS_IMBALANCE_REVERSAL_EDGE_GATE' if edge else 'FAIL_PREDECLARED_COT_ABS_IMBALANCE_REVERSAL_EDGE_GATE',
            'edge_survival':edge,'contract_schema':contract['schema'],'pit_policy_schema':policy['schema'],'price_source_schema':price_contract['schema'],
            'pit_coverage':{'report_dates':458,'eligible':448,'withheld':10},'exclusions':dict(sorted(exclusions.items())),'split_receipt':split_receipt,
            'oos':{'pooled_observations':len(pooled),'weekly_panel_observations':len(weekly_series),'panel_annualized_sharpe':panel_sharpe,
                   'directional_accuracy':accuracy,'panel_total_log_return':sum(weekly_series),'panel_max_drawdown':max_drawdown(weekly_series) if weekly_series else None,
                   'positive_currency_sharpes':positive_ccy,'currency_share':shares,'max_single_currency_share':max_share,'currency':currency_stats,'side':side_stats},
            'predeclared_gates':gates,'governance':{'production_signal_authorized':False,'sizing_authorized':False,'failure_is_valid_result':True,'no_rescue_tuning':True}}
    OUTDIR.mkdir(parents=True,exist_ok=True); (OUTDIR/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True,default=str)+'\n')
    with (OUTDIR/'oos_observations.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['currency','report_date','research_available_from','entry_date','exit_date','net_oi','signal','fx_log_return','observation_return']
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in sorted(pooled,key=lambda x:(x['entry_date'],x['currency'])): w.writerow({k:(v.isoformat() if isinstance(v,date) else v) for k,v in r.items()})
    print(json.dumps(result,indent=2,sort_keys=True,default=str))
    return 0

if __name__=='__main__': raise SystemExit(main())
