#!/usr/bin/env python3
"""Conditional diagnostic: frozen G4USD relative-2Y repricing × macro/CB alignment.

This script MUST NOT refit or retune the PR #122 model. It consumes a frozen OOS
prediction file plus point-in-time macro rowsets and only stratifies observations
into predeclared states: ALIGNED, MIXED, CONTRADICTORY, UNAVAILABLE.
"""
from __future__ import annotations

import argparse, csv, json, math
from bisect import bisect_right
from pathlib import Path

CCYS=("EUR","JPY","CAD","AUD")


def mean(x): return sum(x)/len(x) if x else None

def stdev(x):
    if len(x)<2: return 0.0
    m=sum(x)/len(x)
    return math.sqrt(sum((v-m)**2 for v in x)/(len(x)-1))

def sharpe(r):
    s=stdev(r)
    return None if not r or s<=1e-12 else (sum(r)/len(r))/s*math.sqrt(12)

def hit(rows):
    if not rows: return None
    return sum(1 for r in rows if (r['prediction']>0)==(r['target_return']>0))/len(rows)

def load_macro(path:Path, date_col:str, value_col:str):
    rows=[]
    with path.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if date_col not in r or value_col not in r:
                raise ValueError(f'missing required macro columns in {path}: {date_col}/{value_col}')
            rel=r.get('release_date') or r.get('first_eligible_decision_date') or r.get('eligible_date')
            if not rel:
                raise ValueError(f'PIT eligibility missing in {path}; observation/asof dates are forbidden as release-date fallback')
            rows.append((rel[:10],float(r[value_col])))
    rows.sort()
    return rows

def latest(rows, asof):
    dates=[d for d,_ in rows]
    i=bisect_right(dates,asof)-1
    return None if i<0 else rows[i][1]

def sign(v, eps=1e-12): return 1 if v>eps else (-1 if v<-eps else 0)

def classify(repricing, inf_rel, lab_rel):
    if inf_rel is None or lab_rel is None: return 'UNAVAILABLE'
    s=sign(repricing)
    if s==0: return 'MIXED'
    # Inflation higher relative to US => more hawkish pressure; labour uses unemployment,
    # so LOWER unemployment relative to US is more hawkish: invert labour differential.
    votes=[sign(inf_rel), sign(-lab_rel)]
    agree=sum(1 for v in votes if v==s)
    opp=sum(1 for v in votes if v==-s)
    if agree==2: return 'ALIGNED'
    if agree==1: return 'MIXED'
    if opp>=1: return 'CONTRADICTORY'
    return 'MIXED'

def summarize(rows):
    return {
        'n':len(rows),
        'sharpe':sharpe([r['strategy_return'] for r in rows]),
        'directional_accuracy':hit(rows),
        'total_log_return':sum(r['strategy_return'] for r in rows) if rows else 0.0,
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
        li=latest(data[c]['inf'],asof); ui=latest(data['USD']['inf'],asof)
        ll=latest(data[c]['lab'],asof); ul=latest(data['USD']['lab'],asof)
        inf_rel=None if li is None or ui is None else li-ui
        lab_rel=None if ll is None or ul is None else ll-ul
        state=classify(r['d_diff_2y'],inf_rel,lab_rel)
        x=dict(r)
        x.update({'local_inflation':li,'usd_inflation':ui,'inflation_relative':inf_rel,
                  'local_unemployment':ll,'usd_unemployment':ul,'labour_relative':lab_rel,
                  'alignment_state':state})
        out.append(x)

    states={s:summarize([r for r in out if r['alignment_state']==s]) for s in ('ALIGNED','MIXED','CONTRADICTORY','UNAVAILABLE')}
    per_ccy={}
    for c in CCYS:
        per_ccy[c]={s:summarize([r for r in out if r['currency']==c and r['alignment_state']==s]) for s in ('ALIGNED','MIXED','CONTRADICTORY')}

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
    result={
      'schema':'GMFQ_G4USD_FRONT_END_MACRO_CB_ALIGNMENT_V1',
      'status':'DIAGNOSTIC_COMPLETE',
      'method':{
        'frozen_model_refit':False,'hyperparameter_tuning':False,'state_threshold_search':False,
        'currency_specific_rules':False,'eur_excluded':False,
        'pit_release_fallback_forbidden':True,
        'labour_definition':'local minus US unemployment; lower relative unemployment implies more hawkish pressure',
      },
      'baseline_panel_sharpe':baseline,
      'state_results':states,'currency_state_results':per_ccy,
      'edge_gate':gates,'edge_survival':all(gates.values()),
      'observations':out,
      'policy':{'production_signal_authorized':False,'sizing_authorized':False}
    }
    Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'edge_survival':result['edge_survival'],'state_results':states,'gates':gates},indent=2,sort_keys=True))

if __name__=='__main__': main()
