#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import math
import pathlib
import statistics
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, datetime

import build_cot_ultraconservative_pit_calendar_v1 as pit
import discover_cot_conservative_availability_calendar_v1 as cotbase
from validate_cot_flow_fx_price_readiness_v1 import fetch_one

CONTRACT_PATH=pathlib.Path('validation/COT_FLOW_CONTINUATION_EDGE_CONTRACT_V1_2026-10-11.json')
PIT_POLICY_PATH=pathlib.Path('validation/COT_ULTRACONSERVATIVE_PIT_POLICY_V1_2026-10-11.json')
PRICE_CONTRACT_PATH=pathlib.Path('validation/COT_FLOW_FX_PRICE_SOURCE_CONTRACT_V1_2026-10-11.json')
OUTDIR=pathlib.Path('/tmp/cot-flow-one-shot')

# Official CFTC Legacy Futures Only fixed-column layout used by deacotYYYY.zip.
IDX_REPORT_DATE=2
IDX_CFTC_CODE=3
IDX_OPEN_INTEREST=7
IDX_NC_LONG=8
IDX_NC_SHORT=9


def fnum(s:str)->float:
    return float(s.strip().strip('"').replace(',',''))


def load_cot_positions(currencies:list[str])->dict[str,list[dict]]:
    wanted={cotbase.CODES[c]:c for c in currencies}
    out={c:[] for c in currencies}
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
            ccy=wanted[code]
            report=datetime.strptime(row[IDX_REPORT_DATE].strip().strip('"'),'%Y-%m-%d').date()
            oi=fnum(row[IDX_OPEN_INTEREST]); nc_long=fnum(row[IDX_NC_LONG]); nc_short=fnum(row[IDX_NC_SHORT])
            if not (oi>0 and nc_long>=0 and nc_short>=0):
                raise RuntimeError(f'{ccy} {report}: invalid CFTC numeric fields')
            # Structural sanity checks against a silent layout change.
            if nc_long>oi*3 or nc_short>oi*3:
                raise RuntimeError(f'{ccy} {report}: implausible CFTC field layout')
            key=(ccy,report)
            if key in seen: raise RuntimeError(f'{year}: duplicate {key}')
            seen.add(key)
            out[ccy].append({'report_date':report,'open_interest':oi,'nc_long':nc_long,'nc_short':nc_short,'net_oi':(nc_long-nc_short)/oi})
    for ccy,rows in out.items():
        rows.sort(key=lambda x:x['report_date'])
        if len(rows)<400: raise RuntimeError(f'{ccy}: insufficient COT rows {len(rows)}')
        if len({r['report_date'] for r in rows})!=len(rows): raise RuntimeError(f'{ccy}: duplicate report dates')
    date_sets=[{r['report_date'] for r in out[c]} for c in currencies]
    if any(s!=date_sets[0] for s in date_sets[1:]): raise RuntimeError('COT currency date sets differ')
    return out


def build_pit_map(report_dates:list[date])->dict[date,dict]:
    rows=[]
    for d in report_dates:
        rows.append(pit.transform(cotbase.candidate_row(d.isoformat())))
    eligible=sum(bool(r['research_pit_eligible']) for r in rows)
    withheld=len(rows)-eligible
    if (len(rows),eligible,withheld)!=(458,448,10):
        raise RuntimeError(f'unexpected PIT coverage {(len(rows),eligible,withheld)}')
    return {date.fromisoformat(r['report_date']):r for r in rows}


def load_fx_prices(price_contract:dict)->dict[str,list[tuple[date,float]]]:
    prices={}
    for ccy,spec in price_contract['series'].items():
        got_ccy,_,rows=fetch_one((ccy,spec))
        if got_ccy!=ccy: raise RuntimeError('FX source identity mismatch')
        transformed=[]
        for d,v in rows:
            p=v if spec['transform_to_local_currency_vs_usd']=='identity' else 1.0/v
            if not (math.isfinite(p) and p>0): raise RuntimeError(f'{ccy} invalid transformed price')
            transformed.append((d,p))
        if len(transformed)!=2187: raise RuntimeError(f'{ccy}: expected frozen readiness count 2187, got {len(transformed)}')
        if transformed[0][0]!=date(2018,1,2) or transformed[-1][0]!=date(2026,10,2):
            raise RuntimeError(f'{ccy}: FX coverage differs from readiness receipt')
        prices[ccy]=transformed
    return prices


def first_index_on_or_after(rows:list[tuple[date,float]], target:date):
    lo,hi=0,len(rows)
    while lo<hi:
        mid=(lo+hi)//2
        if rows[mid][0]<target: lo=mid+1
        else: hi=mid
    return lo if lo<len(rows) else None


def sample_sharpe(xs:list[float])->float|None:
    if len(xs)<2: return None
    sd=statistics.stdev(xs)
    if sd==0: return None
    return statistics.mean(xs)/sd*math.sqrt(52)


def max_drawdown(log_returns:list[float])->float:
    wealth=1.0; peak=1.0; mdd=0.0
    for r in log_returns:
        wealth*=math.exp(r); peak=max(peak,wealth); mdd=min(mdd,wealth/peak-1.0)
    return mdd


def summarize_currency(rows:list[dict])->dict:
    rs=[r['observation_return'] for r in rows]
    return {
      'n':len(rows),
      'sharpe':sample_sharpe(rs),
      'directional_accuracy':sum(r>0 for r in rs)/len(rs) if rs else None,
      'total_log_return':sum(rs),
      'max_drawdown':max_drawdown(rs) if rs else None,
      'positive_signals':sum(r['signal']>0 for r in rows),
      'negative_signals':sum(r['signal']<0 for r in rows),
      'first_entry':rows[0]['entry_date'].isoformat() if rows else None,
      'last_entry':rows[-1]['entry_date'].isoformat() if rows else None,
    }


def main()->int:
    contract=json.loads(CONTRACT_PATH.read_text())
    pit_policy=json.loads(PIT_POLICY_PATH.read_text())
    price_contract=json.loads(PRICE_CONTRACT_PATH.read_text())
    assert contract['status']=='PREDECLARED_NO_RESULTS_OBSERVED'
    assert pit_policy['status']=='PREDECLARED_NO_EDGE_RESULTS_OBSERVED'
    assert price_contract['status']=='PREDECLARED_NO_COT_EDGE_RESULTS_OBSERVED'
    assert contract['pit_contract']['required_policy_schema']==pit_policy['schema']
    currencies=contract['universe']['currencies']
    if currencies!=['EUR','GBP','JPY','CHF','AUD','NZD','CAD']: raise RuntimeError('frozen currency universe changed')

    positions=load_cot_positions(currencies)
    report_dates=[r['report_date'] for r in positions[currencies[0]]]
    pit_map=build_pit_map(report_dates)
    prices=load_fx_prices(price_contract)

    observations={c:[] for c in currencies}
    exclusions=defaultdict(int)
    for ccy in currencies:
        rows=positions[ccy]
        for i in range(1,len(rows)):
            cur=rows[i]; prev=rows[i-1]
            pcur=pit_map[cur['report_date']]; pprev=pit_map[prev['report_date']]
            if not pcur['research_pit_eligible']:
                exclusions['current_report_withheld']+=1; continue
            # Conservative result-blind interpretation of "withheld rows must not be imputed":
            # do not form a delta if its immediately previous COT row is itself PIT-withheld.
            if not pprev['research_pit_eligible']:
                exclusions['previous_report_withheld_for_delta']+=1; continue
            delta=cur['net_oi']-prev['net_oi']
            if delta==0:
                exclusions['zero_flow_no_position']+=1; continue
            signal=1 if delta>0 else -1
            available=date.fromisoformat(pcur['research_available_from'])
            px=prices[ccy]
            idx=first_index_on_or_after(px,available)
            if idx is None or idx+5>=len(px):
                exclusions['insufficient_future_fx_prices']+=1; continue
            entry_d,entry_p=px[idx]; exit_d,exit_p=px[idx+5]
            raw=math.log(exit_p/entry_p)
            obsret=signal*raw
            observations[ccy].append({
              'currency':ccy,'report_date':cur['report_date'],'research_available_from':available,
              'entry_date':entry_d,'exit_date':exit_d,'net_oi':cur['net_oi'],'prev_net_oi':prev['net_oi'],
              'delta_net_oi':delta,'signal':signal,'fx_log_return':raw,'observation_return':obsret,
            })

    diagnostic={}; oos={}; split_receipt={}
    for ccy in currencies:
        rows=sorted(observations[ccy],key=lambda r:(r['entry_date'],r['report_date']))
        n=len(rows); cut=math.floor(0.60*n)
        diagnostic[ccy]=rows[:cut]; oos[ccy]=rows[cut:]
        split_receipt[ccy]={'eligible_labeled_n':n,'diagnostic_n':cut,'oos_n':n-cut}

    pooled=[r for c in currencies for r in oos[c]]
    weekly=defaultdict(list)
    for r in pooled:
        iso=r['entry_date'].isocalendar(); weekly[(iso.year,iso.week)].append(r['observation_return'])
    weekly_series=[sum(weekly[k])/len(weekly[k]) for k in sorted(weekly)]
    panel_sharpe=sample_sharpe(weekly_series)
    accuracy=sum(r['observation_return']>0 for r in pooled)/len(pooled) if pooled else None
    currency_stats={c:summarize_currency(oos[c]) for c in currencies}
    positive_ccy=sum((currency_stats[c]['sharpe'] is not None and currency_stats[c]['sharpe']>0) for c in currencies)
    shares={c:len(oos[c])/len(pooled) if pooled else None for c in currencies}
    max_share=max(shares.values()) if pooled else None

    gates={
      'oos_panel_annualized_sharpe_ge_0_50': bool(panel_sharpe is not None and panel_sharpe>=0.50),
      'oos_directional_accuracy_ge_0_52': bool(accuracy is not None and accuracy>=0.52),
      'positive_currency_oos_sharpes_ge_5': positive_ccy>=5,
      'minimum_oos_observations_per_currency_ge_50': all(len(oos[c])>=50 for c in currencies),
      'minimum_pooled_oos_observations_ge_350': len(pooled)>=350,
      'max_single_currency_share_le_0_20': bool(max_share is not None and max_share<=0.20),
    }
    edge_survival=all(gates.values())

    yearly={}
    byyear=defaultdict(list)
    for r in pooled: byyear[r['entry_date'].year].append(r['observation_return'])
    for y,rs in sorted(byyear.items()):
        yearly[str(y)]={'n':len(rs),'mean_observation_return':statistics.mean(rs),'directional_accuracy':sum(x>0 for x in rs)/len(rs),'total_log_return':sum(rs)}

    result={
      'schema':'GMFQ_COT_FLOW_CONTINUATION_ONE_SHOT_RESULT_V1',
      'verdict':'PASS_PREDECLARED_COT_FLOW_CONTINUATION_EDGE_GATE' if edge_survival else 'FAIL_PREDECLARED_COT_FLOW_CONTINUATION_EDGE_GATE',
      'edge_survival':edge_survival,
      'contract_schema':contract['schema'],
      'pit_policy_schema':pit_policy['schema'],
      'price_source_schema':price_contract['schema'],
      'frozen_readiness_run_id':38176843675,
      'frozen_readiness_artifact_id':11715714197,
      'frozen_readiness_artifact_zip_sha256':'54473f5e01a49ba1cf83483e04da945dcfb41e34ebb29949b418a79b4d5e512c',
      'pit_coverage':{'report_dates':458,'eligible':448,'withheld':10},
      'delta_policy_note':'Immediate previous COT report must also be research-PIT eligible; this conservatively excludes the first eligible delta after a withheld block.',
      'exclusions':dict(sorted(exclusions.items())),
      'split_receipt':split_receipt,
      'oos':{
        'pooled_observations':len(pooled),
        'weekly_panel_observations':len(weekly_series),
        'panel_annualized_sharpe':panel_sharpe,
        'directional_accuracy':accuracy,
        'panel_total_log_return':sum(weekly_series),
        'panel_max_drawdown':max_drawdown(weekly_series),
        'positive_currency_sharpes':positive_ccy,
        'currency_share':shares,
        'max_single_currency_share':max_share,
        'currency':currency_stats,
        'calendar_year':yearly,
      },
      'predeclared_gates':gates,
      'governance':{
        'production_signal_authorized':False,
        'sizing_authorized':False,
        'failure_is_valid_result':True,
        'no_rescue_tuning':True,
      },
    }
    OUTDIR.mkdir(parents=True,exist_ok=True)
    (OUTDIR/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True,default=str)+'\n')
    # Audit rows are artifact-only; no repository write.
    with (OUTDIR/'oos_observations.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['currency','report_date','research_available_from','entry_date','exit_date','net_oi','prev_net_oi','delta_net_oi','signal','fx_log_return','observation_return']
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in sorted(pooled,key=lambda x:(x['entry_date'],x['currency'])):
            w.writerow({k:(v.isoformat() if isinstance(v,date) else v) for k,v in r.items()})
    print(json.dumps(result,indent=2,sort_keys=True,default=str))
    return 0

if __name__=='__main__': raise SystemExit(main())
