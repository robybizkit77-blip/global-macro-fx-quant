#!/usr/bin/env python3
"""Conditional diagnostic: frozen G4USD relative-2Y repricing × macro/CB alignment.

This implementation is deliberately result-blind. It MUST NOT refit or retune the
PR #122 model. It consumes frozen OOS predictions plus point-in-time macro rowsets
and stratifies observations into the predeclared states ALIGNED, MIXED,
CONTRADICTORY, UNAVAILABLE.

Contract-critical semantics:
- macro pressure is based on CHANGES in the latest PIT-known macro readings,
  not contemporaneous relative levels;
- pooled state Sharpe is computed from equal-weight MONTHLY panel returns so it
  is comparable with the frozen PR #122 panel Sharpe;
- no observation/as-of date may substitute for release eligibility;
- an explicitly documented official nonpublication is not a synthetic reading:
  it is skipped in the release sequence, leaving the latest two actually-known
  readings unchanged until a new release becomes eligible.
"""
from __future__ import annotations

import argparse, csv, json, math
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path

CCYS=("EUR","JPY","CAD","AUD")
STATES=("ALIGNED","MIXED","CONTRADICTORY","UNAVAILABLE")
OFFICIAL_UNAVAILABLE_STATUSES={"UNAVAILABLE_OFFICIAL_NOT_PUBLISHED","NOT_PUBLISHED_OFFICIAL"}


def mean(x): return sum(x)/len(x) if x else None

def stdev(x):
    if len(x)<2: return 0.0
    m=sum(x)/len(x)
    return math.sqrt(sum((v-m)**2 for v in x)/(len(x)-1))

def sharpe(r):
    s=stdev(r)
    return None if not r or s<=1e-12 else (sum(r)/len(r))/s*math.sqrt(12)

def max_drawdown_log_returns(r):
    if not r: return 0.0
    wealth=1.0; peak=1.0; mdd=0.0
    for x in r:
        wealth*=math.exp(x)
        peak=max(peak,wealth)
        mdd=min(mdd,wealth/peak-1.0)
    return mdd

def hit(rows):
    if not rows: return None
    return sum(1 for r in rows if (r['prediction']>=0)==(r['target_return']>0))/len(rows)

def load_macro(path:Path, date_col:str, value_col:str):
    rows=[]
    with path.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if date_col not in r or value_col not in r:
                raise ValueError(f'missing required macro columns in {path}: {date_col}/{value_col}')
            status=(r.get('availability_status') or '').strip()
            value=(r.get(value_col) or '').strip()
            rel=(r.get('release_date') or r.get('first_eligible_decision_date') or r.get('eligible_date') or '').strip()
            if status in OFFICIAL_UNAVAILABLE_STATUSES:
                if value or rel:
                    raise ValueError(f'official-unavailable row in {path} unexpectedly contains value/eligibility')
                continue
            if not rel:
                raise ValueError(f'PIT eligibility missing in {path}; observation/asof dates are forbidden as release-date fallback')
            if not value:
                raise ValueError(f'macro value missing in {path} without certified official-unavailable status')
            rows.append((rel[:10],float(value)))
    rows.sort()
    return rows

def latest_two(rows,asof):
    dates=[d for d,_ in rows]
    i=bisect_right(dates,asof)-1
    if i<0: return (None,None)
    latest=rows[i][1]
    prev=rows[i-1][1] if i>=1 else None
    return latest,prev

def change_pair(rows,asof):
    cur,prev=latest_two(rows,asof)
    return (None,cur,prev) if cur is None or prev is None else (cur-prev,cur,prev)

def sign(v,eps=1e-12): return 1 if v>eps else (-1 if v<-eps else 0)

def classify(repricing, inflation_pressure, labour_pressure):
    if inflation_pressure is None or labour_pressure is None: return 'UNAVAILABLE'
    s=sign(repricing)
    if s==0: return 'MIXED'
    votes=[sign(inflation_pressure),sign(labour_pressure)]
    agree=sum(1 for v in votes if v==s)
    opp=sum(1 for v in votes if v==-s)
    if agree==2: return 'ALIGNED'
    if agree==1: return 'MIXED'
    if opp>=1: return 'CONTRADICTORY'
    return 'MIXED'

def panel_returns(rows):
    by_date=defaultdict(list)
    for r in rows: by_date[r['asof_date'][:10]].append(r['strategy_return'])
    return [(d,sum(v)/len(v)) for d,v in sorted(by_date.items())]

def summarize(rows,panel:bool):
    if panel:
        pr=panel_returns(rows); rr=[v for _,v in pr]
    else:
        pr=[]; rr=[r['strategy_return'] for r in rows]
    return {
        'n':len(rows),
        'months':len(pr) if panel else len(rows),
        'sharpe':sharpe(rr),
        'directional_accuracy':hit(rows),
        'total_log_return':sum(rr) if rr else 0.0,
        'max_drawdown':max_drawdown_log_returns(rr),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--frozen-oos',required=True)
    for c in (*CCYS,'USD'):
        cl=c.lower()
        ap.add_argument(f'--{cl}-inflation',required=True)
        ap.add_argument(f'--{cl}-labour',required=True)
    ap.add_argument('--output',required=True)
    a=ap.parse_args()

    frozen=json.load(open(a.frozen_oos,encoding='utf-8'))
    assert frozen['schema']=='GMFQ_G4USD_RELATIVE_FRONT_END_PANEL_OOS_V1'
    assert frozen['frozen_from_pr']==122

    meta={
      'EUR':('reference_month','cpi_yoy','reference_month','unemployment_rate'),
      'JPY':('reference_month','cpi_yoy','reference_month','unemployment_rate'),
      'CAD':('reference_month','cpi_yoy_full_precision','reference_month','unemployment_rate'),
      'AUD':('reference_quarter','cpi_yoy','reference_month','unemployment_rate'),
      'USD':('reference_month','cpi_yoy','reference_month','unemployment_rate'),
    }
    data={}
    for c in (*CCYS,'USD'):
        ic,iv,lc,lv=meta[c]
        data[c]={
          'inf':load_macro(Path(getattr(a,f'{c.lower()}_inflation')),ic,iv),
          'lab':load_macro(Path(getattr(a,f'{c.lower()}_labour')),lc,lv),
        }

    out=[]
    for r in frozen['observations']:
        c=r['currency']; asof=r['asof_date'][:10]
        dli,li,pli=change_pair(data[c]['inf'],asof)
        dui,ui,pui=change_pair(data['USD']['inf'],asof)
        dll,ll,pll=change_pair(data[c]['lab'],asof)
        dul,ul,pul=change_pair(data['USD']['lab'],asof)
        inf_pressure=None if dli is None or dui is None else dli-dui
        lab_pressure=None if dll is None or dul is None else -(dll-dul)
        state=classify(r['d_diff_2y'],inf_pressure,lab_pressure)
        x=dict(r)
        x.update({
          'local_inflation':li,'local_inflation_previous':pli,'local_inflation_change':dli,
          'usd_inflation':ui,'usd_inflation_previous':pui,'usd_inflation_change':dui,
          'inflation_pressure':inf_pressure,
          'local_unemployment':ll,'local_unemployment_previous':pll,'local_unemployment_change':dll,
          'usd_unemployment':ul,'usd_unemployment_previous':pul,'usd_unemployment_change':dul,
          'labour_pressure':lab_pressure,'alignment_state':state,
        })
        out.append(x)

    states={s:summarize([r for r in out if r['alignment_state']==s],panel=True) for s in STATES}
    per_ccy={}
    for c in CCYS:
        per_ccy[c]={s:summarize([r for r in out if r['currency']==c and r['alignment_state']==s],panel=False)
                    for s in ('ALIGNED','MIXED','CONTRADICTORY')}

    baseline=frozen['baseline_panel_sharpe']
    sa=states['ALIGNED']['sharpe']; sc=states['CONTRADICTORY']['sharpe']
    positive=sum(1 for c in CCYS if per_ccy[c]['ALIGNED']['sharpe'] is not None and per_ccy[c]['ALIGNED']['sharpe']>0)
    min_cov=all(per_ccy[c]['ALIGNED']['n']>=12 for c in CCYS) and states['ALIGNED']['n']>=60
    gates={
      'aligned_panel_sharpe_ge_0_50': sa is not None and sa>=0.50,
      'aligned_improvement_ge_0_20': sa is not None and sa-baseline>=0.20,
      'aligned_minus_contradictory_ge_0_30': sa is not None and sc is not None and sa-sc>=0.30,
      'positive_aligned_currency_sharpes_ge_3': positive>=3,
      'aligned_directional_accuracy_ge_0_52': states['ALIGNED']['directional_accuracy'] is not None and states['ALIGNED']['directional_accuracy']>=0.52,
      'minimum_coverage': min_cov,
    }
    zero_repricing=sum(1 for r in out if sign(r['d_diff_2y'])==0)
    result={
      'schema':'GMFQ_G4USD_FRONT_END_MACRO_CB_ALIGNMENT_V1',
      'status':'DIAGNOSTIC_COMPLETE',
      'method':{
        'frozen_model_refit':False,'hyperparameter_tuning':False,'state_threshold_search':False,
        'currency_specific_rules':False,'eur_excluded':False,'pit_release_fallback_forbidden':True,
        'official_nonpublication_semantics':'skip as non-observation; do not impute or synthesize; retain latest two actually-known releases',
        'inflation_definition':'change(local PIT-known inflation) minus change(US PIT-known inflation)',
        'labour_definition':'negative of [change(local PIT-known unemployment) minus change(US PIT-known unemployment)]',
        'pooled_state_sharpe_definition':'annualized Sharpe of equal-weight monthly panel strategy returns',
        'direction_convention':'prediction >= 0 is positive, matching frozen parent',
        'zero_repricing_state':'MIXED','zero_repricing_observations':zero_repricing,
      },
      'baseline_panel_sharpe':baseline,'state_results':states,'currency_state_results':per_ccy,
      'edge_gate':gates,'edge_survival':all(gates.values()),'observations':out,
      'policy':{'production_signal_authorized':False,'sizing_authorized':False}
    }
    Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'edge_survival':result['edge_survival'],'state_results':states,'gates':gates,'zero_repricing_observations':zero_repricing},indent=2,sort_keys=True))

if __name__=='__main__': main()
