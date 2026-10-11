#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics
from collections import defaultdict
from pathlib import Path

CCYS=("EUR","JPY","CAD","AUD")
GROUPS=("KNOWN_PERSISTENCE_AT_T","NO_KNOWN_PERSISTENCE_AT_T")

def sign(v,eps=1e-12): return 1 if v>eps else (-1 if v<-eps else 0)
def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

def summarize(rows):
    m1=[r['signed_fx_return_1m'] for r in rows if r['signed_fx_return_1m'] is not None]
    m3=[r['signed_fx_return_3m'] for r in rows if r['signed_fx_return_3m'] is not None]
    return {
      'n':len(rows),
      'n_1m':len(m1),'n_3m':len(m3),
      'mean_signed_fx_return_1m':mean(m1),
      'mean_signed_fx_return_3m':mean(m3),
      'median_signed_fx_return_1m':median(m1),
      'median_signed_fx_return_3m':median(m3),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--alignment-result',required=True)
    ap.add_argument('--output',required=True)
    a=ap.parse_args()
    src=json.load(open(a.alignment_result,encoding='utf-8'))
    assert src['schema']=='GMFQ_G4USD_FRONT_END_MACRO_CB_ALIGNMENT_V1'
    rows=src['observations']
    by=defaultdict(list)
    for r in rows: by[r['currency']].append(r)
    out=[]
    for c in CCYS:
        seq=sorted(by[c],key=lambda x:x['asof_date'])
        for i,r in enumerate(seq):
            if r['alignment_state']!='CONTRADICTORY': continue
            cs=sign(r['d_diff_2y'])
            if cs==0: continue
            ps=sign(seq[i-1]['d_diff_2y']) if i>0 else 0
            grp='KNOWN_PERSISTENCE_AT_T' if ps!=0 and ps==cs else 'NO_KNOWN_PERSISTENCE_AT_T'
            x=dict(r)
            x['known_persistence_group']=grp
            x['previous_front_end_sign']=ps
            x['current_front_end_sign']=cs
            x['signed_fx_return_1m']=cs*r['target_return']
            x['signed_fx_return_3m']=cs*sum(seq[j]['target_return'] for j in (i,i+1,i+2)) if i+2<len(seq) else None
            out.append(x)
    groups={g:summarize([r for r in out if r['known_persistence_group']==g]) for g in GROUPS}
    per={}
    for c in CCYS:
        per[c]={g:summarize([r for r in out if r['currency']==c and r['known_persistence_group']==g]) for g in GROUPS}
    kp=[r for r in out if r['known_persistence_group']=='KNOWN_PERSISTENCE_AT_T']
    total=len(kp)
    shares={c:(sum(1 for r in kp if r['currency']==c)/total if total else 0.0) for c in CCYS}
    positive_ccys=sum(1 for c in CCYS if per[c]['KNOWN_PERSISTENCE_AT_T']['mean_signed_fx_return_3m'] is not None and per[c]['KNOWN_PERSISTENCE_AT_T']['mean_signed_fx_return_3m']>0)
    kg=groups['KNOWN_PERSISTENCE_AT_T']; ng=groups['NO_KNOWN_PERSISTENCE_AT_T']
    rules={
      'minimum_pooled_known_persistence_n': kg['n']>=25,
      'pooled_3m_mean_positive': kg['mean_signed_fx_return_3m'] is not None and kg['mean_signed_fx_return_3m']>0,
      'known_persistence_3m_mean_exceeds_no_persistence': kg['mean_signed_fx_return_3m'] is not None and ng['mean_signed_fx_return_3m'] is not None and kg['mean_signed_fx_return_3m']>ng['mean_signed_fx_return_3m'],
      'minimum_3_positive_currencies': positive_ccys>=3,
      'no_single_currency_over_50pct': max(shares.values())<=0.5 if shares else False,
    }
    result={
      'schema':'GMFQ_G4USD_FRONT_END_KNOWN_PERSISTENCE_DISCOVERY_V2',
      'status':'EXPLORATORY_DIAGNOSTIC_COMPLETE_NOT_EDGE_CERTIFICATION',
      'groups':groups,'per_currency':per,'known_persistence_currency_shares':shares,
      'candidate_generation_rules':rules,
      'candidate_generated_for_future_confirmation':all(rules.values()),
      'observations':out,
      'governance':{
        'same_sample_discovery_only':True,'edge_certified':False,
        'production_signal_authorized':False,'sizing_authorized':False,
        'future_unseen_confirmation_required':True,'lookahead_forbidden':True,
        'no_refit':True,'no_threshold_search':True,'no_currency_exclusion':True,
      }
    }
    Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('groups','per_currency','known_persistence_currency_shares','candidate_generation_rules','candidate_generated_for_future_confirmation')},indent=2,sort_keys=True))
if __name__=='__main__': main()
