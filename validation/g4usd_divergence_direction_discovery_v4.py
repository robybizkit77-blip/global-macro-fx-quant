#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path

CCYS=("EUR","JPY","CAD","AUD")
GROUPS=("HAWKISH_DIVERGENCE","DOVISH_DIVERGENCE")

def sign(v,eps=1e-12): return 1 if v>eps else (-1 if v<-eps else 0)
def mean(xs): return sum(xs)/len(xs) if xs else None

def enrich(rows):
    by=defaultdict(list)
    for r in rows: by[r['currency']].append(r)
    out=[]
    for c,seq in by.items():
        seq=sorted(seq,key=lambda x:x['asof_date'])
        for i,r in enumerate(seq):
            if r.get('alignment_state')!='CONTRADICTORY': continue
            s=sign(r['d_diff_2y'])
            if s==0: continue
            x=dict(r)
            x['direction_group']='HAWKISH_DIVERGENCE' if s>0 else 'DOVISH_DIVERGENCE'
            x['front_end_signed_fx_return_1m']=s*r['target_return']
            x['front_end_signed_fx_return_3m']=None if i+2>=len(seq) else s*sum(seq[j]['target_return'] for j in (i,i+1,i+2))
            out.append(x)
    return out

def summarize(rows):
    r1=[r['front_end_signed_fx_return_1m'] for r in rows if r['front_end_signed_fx_return_1m'] is not None]
    r3=[r['front_end_signed_fx_return_3m'] for r in rows if r['front_end_signed_fx_return_3m'] is not None]
    return {'n':len(rows),'mean_1m':mean(r1),'n_1m':len(r1),'mean_3m':mean(r3),'n_3m':len(r3)}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--alignment-result',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    src=json.load(open(a.alignment_result,encoding='utf-8'))
    assert src['schema']=='GMFQ_G4USD_FRONT_END_MACRO_CB_ALIGNMENT_V1'
    assert src['state_results']['CONTRADICTORY']['n']==67
    rows=enrich(src['observations'])
    assert len(rows)==67
    pooled={g:summarize([r for r in rows if r['direction_group']==g]) for g in GROUPS}
    per={c:{g:summarize([r for r in rows if r['currency']==c and r['direction_group']==g]) for g in GROUPS} for c in CCYS}
    h=pooled['HAWKISH_DIVERGENCE']; d=pooled['DOVISH_DIVERGENCE']
    score_h=(h['mean_3m'] if h['mean_3m'] is not None else -999)
    score_d=(d['mean_3m'] if d['mean_3m'] is not None else -999)
    winner='HAWKISH_DIVERGENCE' if score_h>=score_d else 'DOVISH_DIVERGENCE'; loser='DOVISH_DIVERGENCE' if winner=='HAWKISH_DIVERGENCE' else 'HAWKISH_DIVERGENCE'
    w=pooled[winner]; l=pooled[loser]
    positive_ccy=sum(1 for c in CCYS if per[c][winner]['mean_3m'] is not None and per[c][winner]['mean_3m']>0)
    winner_counts={c:per[c][winner]['n'] for c in CCYS}; total=sum(winner_counts.values()); max_share=max(winner_counts.values())/total if total else 1.0
    gates={
      'minimum_n_per_direction': min(h['n'],d['n'])>=20,
      'winner_mean_1m_positive': w['mean_1m'] is not None and w['mean_1m']>0,
      'winner_mean_3m_positive': w['mean_3m'] is not None and w['mean_3m']>0,
      'winner_minus_loser_1m_ge_0_001': w['mean_1m'] is not None and l['mean_1m'] is not None and w['mean_1m']-l['mean_1m']>=0.001,
      'winner_minus_loser_3m_ge_0_002': w['mean_3m'] is not None and l['mean_3m'] is not None and w['mean_3m']-l['mean_3m']>=0.002,
      'positive_currencies_at_3m_ge_3': positive_ccy>=3,
      'single_currency_share_le_0_50': max_share<=0.50,
    }
    result={'schema':'GMFQ_G4USD_DIVERGENCE_DIRECTION_DISCOVERY_V4','status':'EXPLORATORY_DIAGNOSTIC_COMPLETE_NOT_EDGE_CERTIFICATION','pooled':pooled,'per_currency':per,'winner_by_3m_mean':winner,'gates':gates,'candidate_generated_for_future_confirmation':all(gates.values()),'observations':rows,'governance':{'edge_certified':False,'production_signal_authorized':False,'sizing_authorized':False,'same_sample_discovery_only':True,'future_unseen_confirmation_required':True,'no_rescue_tuning':True}}
    Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'pooled':pooled,'winner':winner,'gates':gates,'candidate':result['candidate_generated_for_future_confirmation']},indent=2,sort_keys=True))
if __name__=='__main__': main()
