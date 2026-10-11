#!/usr/bin/env python3
"""Discovery-only test of relative-2Y repricing intensity inside CONTRADICTORY states.

Thresholds are fixed ex ante in basis points: <5, 5-<10, 10-<20, >=20.
This script does not refit the frozen PR122 model and cannot certify an edge.
"""
from __future__ import annotations

import argparse, json
from collections import defaultdict
from pathlib import Path

CCYS=("EUR","JPY","CAD","AUD")
BUCKETS=("LT_5BP","BP_5_TO_LT_10","BP_10_TO_LT_20","GE_20BP")


def sign(v,eps=1e-12):
    return 1 if v>eps else (-1 if v<-eps else 0)


def mean(xs):
    return sum(xs)/len(xs) if xs else None


def median(xs):
    if not xs: return None
    x=sorted(xs); n=len(x); m=n//2
    return x[m] if n%2 else (x[m-1]+x[m])/2


def bucket(bp):
    if bp<5.0: return 'LT_5BP'
    if bp<10.0: return 'BP_5_TO_LT_10'
    if bp<20.0: return 'BP_10_TO_LT_20'
    return 'GE_20BP'


def parent_hit(rows):
    if not rows: return None
    return sum(1 for r in rows if (r['prediction']>=0)==(r['target_return']>0))/len(rows)


def enrich_all(rows):
    by_ccy=defaultdict(list)
    for r in rows:
        by_ccy[r['currency']].append(r)
    out=[]
    for c,seq in by_ccy.items():
        seq=sorted(seq,key=lambda x:x['asof_date'])
        for i,r in enumerate(seq):
            x=dict(r)
            s=sign(r['d_diff_2y'])
            x['abs_repricing_bp']=abs(r['d_diff_2y'])*100.0
            x['intensity_bucket']=bucket(x['abs_repricing_bp'])
            x['front_end_signed_fx_return_1m']=None if s==0 else s*r['target_return']
            x['front_end_signed_fx_return_3m']=None
            if s!=0 and i+2<len(seq):
                x['front_end_signed_fx_return_3m']=s*sum(seq[j]['target_return'] for j in (i,i+1,i+2))
            out.append(x)
    return out


def vals(rows,key):
    return [r[key] for r in rows if r.get(key) is not None]


def summary(rows):
    v1=vals(rows,'front_end_signed_fx_return_1m')
    v3=vals(rows,'front_end_signed_fx_return_3m')
    mix={c:sum(1 for r in rows if r['currency']==c) for c in CCYS}
    return {
        'n':len(rows),
        'n_1m':len(v1),
        'n_3m':len(v3),
        'mean_fx_return_signed_by_front_end_1m':mean(v1),
        'mean_fx_return_signed_by_front_end_3m':mean(v3),
        'median_fx_return_signed_by_front_end_1m':median(v1),
        'median_fx_return_signed_by_front_end_3m':median(v3),
        'frozen_parent_strategy_return_mean':mean([r['strategy_return'] for r in rows]),
        'frozen_parent_directional_accuracy':parent_hit(rows),
        'currency_mix':mix,
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
    assert src['state_results']['CONTRADICTORY']['n']==67
    assert abs(src['state_results']['CONTRADICTORY']['sharpe']-1.1348751274937703)<1e-12

    all_rows=enrich_all(src['observations'])
    rows=[r for r in all_rows if r['alignment_state']=='CONTRADICTORY']
    assert len(rows)==67
    assert all(sign(r['d_diff_2y'])!=0 for r in rows)

    bucket_results={b:summary([r for r in rows if r['intensity_bucket']==b]) for b in BUCKETS}
    lt10=[r for r in rows if r['abs_repricing_bp']<10.0]
    ge20=[r for r in rows if r['abs_repricing_bp']>=20.0]
    lt10_summary=summary(lt10)
    ge20_summary=summary(ge20)

    per_currency={}
    positive_3m=0
    for c in CCYS:
        cr=[r for r in ge20 if r['currency']==c]
        s=summary(cr)
        per_currency[c]=s
        if s['mean_fx_return_signed_by_front_end_3m'] is not None and s['mean_fx_return_signed_by_front_end_3m']>0:
            positive_3m+=1

    max_share=max((sum(1 for r in ge20 if r['currency']==c)/len(ge20) for c in CCYS),default=1.0)
    g1=ge20_summary['mean_fx_return_signed_by_front_end_1m']
    g3=ge20_summary['mean_fx_return_signed_by_front_end_3m']
    l1=lt10_summary['mean_fx_return_signed_by_front_end_1m']
    l3=lt10_summary['mean_fx_return_signed_by_front_end_3m']
    rules={
        'minimum_large_n':len(ge20)>=15,
        'large_mean_signed_fx_1m_positive':g1 is not None and g1>0,
        'large_mean_signed_fx_3m_positive':g3 is not None and g3>0,
        'large_1m_exceeds_lt10bp':g1 is not None and l1 is not None and g1>l1,
        'large_3m_exceeds_lt10bp':g3 is not None and l3 is not None and g3>l3,
        'minimum_3_positive_currencies_at_3m':positive_3m>=3,
        'no_single_currency_over_50pct_of_large_bucket':max_share<=0.50,
    }
    candidate=all(rules.values())

    result={
        'schema':'GMFQ_G4USD_FRONT_END_REPRICING_INTENSITY_DISCOVERY_V3',
        'status':'EXPLORATORY_DIAGNOSTIC_COMPLETE_NOT_EDGE_CERTIFICATION',
        'source_contradictory_n':67,
        'intensity_thresholds_bp':{'LT_5BP':[0,5],'BP_5_TO_LT_10':[5,10],'BP_10_TO_LT_20':[10,20],'GE_20BP':[20,None]},
        'bucket_results':bucket_results,
        'lt10bp_combined':lt10_summary,
        'ge20bp':ge20_summary,
        'ge20bp_per_currency':per_currency,
        'candidate_generation_rules':rules,
        'candidate_generated_for_future_confirmation':candidate,
        'observations':rows,
        'governance':{
            'same_sample_discovery_only':True,
            'edge_certified':False,
            'production_signal_authorized':False,
            'sizing_authorized':False,
            'future_unseen_confirmation_required':True,
            'no_threshold_search':True,
            'no_rescue_tuning_after_outputs':True,
            'no_refit':True,
            'no_currency_exclusion':True,
        }
    }
    Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({
        'status':result['status'],
        'bucket_results':bucket_results,
        'lt10bp_combined':lt10_summary,
        'ge20bp':ge20_summary,
        'ge20bp_per_currency':per_currency,
        'candidate_generation_rules':rules,
        'candidate_generated_for_future_confirmation':candidate,
    },indent=2,sort_keys=True))

if __name__=='__main__':
    main()
