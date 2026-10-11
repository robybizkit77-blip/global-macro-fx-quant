#!/usr/bin/env python3
"""Exploratory characterization of G4USD macro-vs-front-end contradictions.

This script is intentionally DISCOVERY-ONLY. It consumes the already-defined
alignment observation rowset and characterizes the CONTRADICTORY bucket without
changing the frozen PR122 model, the macro definitions, or any trading rule.
Nothing emitted by this script is eligible for production or sizing promotion.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

CCYS=("EUR","JPY","CAD","AUD")
SUBTYPES=("DOUBLE_OPPOSITION","INFLATION_ONLY_OPPOSITION","LABOUR_ONLY_OPPOSITION","OTHER_CONTRADICTORY")


def sign(v,eps=1e-12):
    return 1 if v>eps else (-1 if v<-eps else 0)


def mean(xs):
    return sum(xs)/len(xs) if xs else None


def stdev(xs):
    if len(xs)<2:
        return 0.0
    m=sum(xs)/len(xs)
    return math.sqrt(sum((x-m)**2 for x in xs)/(len(xs)-1))


def sharpe(xs):
    if not xs:
        return None
    s=stdev(xs)
    return None if s<=1e-12 else mean(xs)/s*math.sqrt(12)


def max_drawdown_log_returns(xs):
    if not xs:
        return 0.0
    wealth=1.0; peak=1.0; mdd=0.0
    for x in xs:
        wealth*=math.exp(x)
        peak=max(peak,wealth)
        mdd=min(mdd,wealth/peak-1.0)
    return mdd


def classify_subtype(r):
    if r.get('alignment_state')!='CONTRADICTORY':
        return None
    rs=sign(r['d_diff_2y'])
    if rs==0:
        return None
    inf=sign(r['inflation_pressure'])
    lab=sign(r['labour_pressure'])
    inf_opp=(inf==-rs)
    lab_opp=(lab==-rs)
    if inf_opp and lab_opp:
        return 'DOUBLE_OPPOSITION'
    if inf_opp and lab==0:
        return 'INFLATION_ONLY_OPPOSITION'
    if lab_opp and inf==0:
        return 'LABOUR_ONLY_OPPOSITION'
    return 'OTHER_CONTRADICTORY'


def panel_returns(rows,key):
    by_date=defaultdict(list)
    for r in rows:
        by_date[r['asof_date'][:10]].append(r[key])
    return [sum(v)/len(v) for _,v in sorted(by_date.items())]


def parent_hit(rows):
    if not rows:
        return None
    return sum(1 for r in rows if (r['prediction']>=0)==(r['target_return']>0))/len(rows)


def summarize_parent(rows,panel=True):
    rr=panel_returns(rows,'strategy_return') if panel else [r['strategy_return'] for r in rows]
    return {
        'n':len(rows),
        'months':len(set(r['asof_date'][:10] for r in rows)),
        'directional_accuracy_of_frozen_parent_prediction':parent_hit(rows),
        'total_log_return_of_frozen_parent_prediction':sum(rr) if rr else 0.0,
        'annualized_sharpe_of_frozen_parent_prediction':sharpe(rr),
        'max_drawdown_of_frozen_parent_prediction':max_drawdown_log_returns(rr),
    }


def enrich_lead_lag(rows):
    by_ccy=defaultdict(list)
    for r in rows:
        by_ccy[r['currency']].append(r)
    out=[]
    for c,seq in by_ccy.items():
        seq=sorted(seq,key=lambda x:x['asof_date'])
        for i,r in enumerate(seq):
            x=dict(r)
            rs=sign(r['d_diff_2y'])
            x['front_end_signed_fx_return_1m']=None if rs==0 else rs*r['target_return']
            if rs!=0 and i+2<len(seq):
                x['front_end_signed_fx_return_3m']=rs*sum(seq[j]['target_return'] for j in (i,i+1,i+2))
            else:
                x['front_end_signed_fx_return_3m']=None
            if i+1<len(seq):
                next_s=sign(seq[i+1]['d_diff_2y'])
                x['front_end_persistence']='PERSISTS' if rs!=0 and next_s==rs else 'REVERSES_OR_ZERO'
            else:
                x['front_end_persistence']=None
            out.append(x)
    return out


def mean_not_none(xs):
    vals=[x for x in xs if x is not None]
    return mean(vals),len(vals)


def lead_lag_summary(rows):
    m1,n1=mean_not_none([r['front_end_signed_fx_return_1m'] for r in rows])
    m3,n3=mean_not_none([r['front_end_signed_fx_return_3m'] for r in rows])
    return {
        'n':len(rows),
        'signed_by_front_end_mean_1m':m1,
        'signed_by_front_end_n_1m':n1,
        'signed_by_front_end_mean_3m':m3,
        'signed_by_front_end_n_3m':n3,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--alignment-result',required=True)
    ap.add_argument('--output',required=True)
    a=ap.parse_args()

    src=json.load(open(a.alignment_result,encoding='utf-8'))
    assert src['schema']=='GMFQ_G4USD_FRONT_END_MACRO_CB_ALIGNMENT_V1'
    assert src['status']=='DIAGNOSTIC_COMPLETE'
    assert src['policy']=={'production_signal_authorized':False,'sizing_authorized':False}
    assert set(r['currency'] for r in src['observations'])==set(CCYS)

    all_rows=enrich_lead_lag(src['observations'])
    contradictory=[]
    for r in all_rows:
        st=classify_subtype(r)
        if st:
            x=dict(r); x['divergence_subtype']=st; contradictory.append(x)

    subtype_results={}
    for st in SUBTYPES:
        rr=[r for r in contradictory if r['divergence_subtype']==st]
        subtype_results[st]={
            'parent_performance':summarize_parent(rr,panel=True),
            'lead_lag':lead_lag_summary(rr),
        }

    per_ccy={}
    for c in CCYS:
        per_ccy[c]={}
        for st in SUBTYPES:
            rr=[r for r in contradictory if r['currency']==c and r['divergence_subtype']==st]
            s=summarize_parent(rr,panel=False)
            per_ccy[c][st]={
                'n':s['n'],
                'sharpe':s['annualized_sharpe_of_frozen_parent_prediction'],
                'directional_accuracy':s['directional_accuracy_of_frozen_parent_prediction'],
            }

    persistence={}
    for g in ('PERSISTS','REVERSES_OR_ZERO'):
        rr=[r for r in contradictory if r['front_end_persistence']==g]
        persistence[g]=lead_lag_summary(rr)

    counts={st:sum(1 for r in contradictory if r['divergence_subtype']==st) for st in SUBTYPES}
    assert sum(counts.values())==len(contradictory)
    assert len(contradictory)==src['state_results']['CONTRADICTORY']['n']

    result={
        'schema':'GMFQ_G4USD_FRONT_END_MACRO_DIVERGENCE_DISCOVERY_V1',
        'status':'EXPLORATORY_DIAGNOSTIC_COMPLETE_NOT_EDGE_CERTIFICATION',
        'source_alignment_schema':src['schema'],
        'source_contradictory_n':src['state_results']['CONTRADICTORY']['n'],
        'subtype_counts':counts,
        'subtype_results':subtype_results,
        'per_currency':per_ccy,
        'persistence_results':persistence,
        'observations':contradictory,
        'governance':{
            'same_sample_discovery_only':True,
            'production_signal_authorized':False,
            'sizing_authorized':False,
            'edge_certified':False,
            'future_unseen_confirmation_required':True,
            'no_threshold_search':True,
            'no_refit':True,
            'no_currency_exclusion':True,
        }
    }
    Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({
        'status':result['status'],
        'subtype_counts':counts,
        'subtype_results':subtype_results,
        'persistence_results':persistence,
    },indent=2,sort_keys=True))


if __name__=='__main__':
    main()
