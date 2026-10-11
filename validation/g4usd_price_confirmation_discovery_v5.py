#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path

CCYS=("EUR","JPY","CAD","AUD")
GROUPS=("PRICE_CONFIRMS_RATES","PRICE_DIVERGES_FROM_RATES")

def sign(v,eps=1e-12): return 1 if v>eps else (-1 if v<-eps else 0)
def mean(xs): return sum(xs)/len(xs) if xs else None

def build(rows):
    by=defaultdict(list)
    for r in rows: by[r['currency']].append(r)
    out=[]
    for c,seq in by.items():
        seq=sorted(seq,key=lambda x:x['asof_date'])
        for i,r in enumerate(seq):
            if i==0: continue
            rs=sign(r['d_diff_2y']); ps=sign(seq[i-1]['target_return'])
            if rs==0 or ps==0: continue
            x=dict(r)
            x['previous_fx_return']=seq[i-1]['target_return']
            x['price_confirmation_group']='PRICE_CONFIRMS_RATES' if ps==rs else 'PRICE_DIVERGES_FROM_RATES'
            x['rates_signed_fx_return_1m']=rs*r['target_return']
            x['rates_signed_fx_return_3m']=None if i+2>=len(seq) else rs*sum(seq[j]['target_return'] for j in (i,i+1,i+2))
            out.append(x)
    return out

def summarize(rows):
    r1=[r['rates_signed_fx_return_1m'] for r in rows if r['rates_signed_fx_return_1m'] is not None]
    r3=[r['rates_signed_fx_return_3m'] for r in rows if r['rates_signed_fx_return_3m'] is not None]
    return {'n':len(rows),'n_1m':len(r1),'mean_1m':mean(r1),'n_3m':len(r3),'mean_3m':mean(r3)}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--alignment-result',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    src=json.load(open(a.alignment_result,encoding='utf-8'))
    assert src['schema']=='GMFQ_G4USD_FRONT_END_MACRO_CB_ALIGNMENT_V1'
    assert len(src['observations'])==256
    rows=build(src['observations'])
    pooled={g:summarize([r for r in rows if r['price_confirmation_group']==g]) for g in GROUPS}
    per={c:{g:summarize([r for r in rows if r['currency']==c and r['price_confirmation_group']==g]) for g in GROUPS} for c in CCYS}
    conf=pooled['PRICE_CONFIRMS_RATES']; div=pooled['PRICE_DIVERGES_FROM_RATES']
    positive_ccy=sum(1 for c in CCYS if per[c]['PRICE_CONFIRMS_RATES']['mean_3m'] is not None and per[c]['PRICE_CONFIRMS_RATES']['mean_3m']>0)
    counts={c:per[c]['PRICE_CONFIRMS_RATES']['n'] for c in CCYS}; total=sum(counts.values()); max_share=max(counts.values())/total if total else 1.0
    gates={
      'minimum_n_per_group': min(conf['n'],div['n'])>=60,
      'confirmed_mean_1m_positive': conf['mean_1m'] is not None and conf['mean_1m']>0,
      'confirmed_mean_3m_positive': conf['mean_3m'] is not None and conf['mean_3m']>0,
      'confirmed_minus_diverged_1m_ge_0_001': conf['mean_1m'] is not None and div['mean_1m'] is not None and conf['mean_1m']-div['mean_1m']>=0.001,
      'confirmed_minus_diverged_3m_ge_0_002': conf['mean_3m'] is not None and div['mean_3m'] is not None and conf['mean_3m']-div['mean_3m']>=0.002,
      'positive_confirmed_currencies_at_3m_ge_3': positive_ccy>=3,
      'single_currency_share_le_0_50': max_share<=0.50,
    }
    result={
      'schema':'GMFQ_G4USD_PRICE_CONFIRMATION_DISCOVERY_V5',
      'status':'EXPLORATORY_DIAGNOSTIC_COMPLETE_NOT_EDGE_CERTIFICATION',
      'pooled':pooled,'per_currency':per,'gates':gates,
      'candidate_generated_for_future_confirmation':all(gates.values()),
      'observations':rows,
      'governance':{
        'edge_certified':False,'production_signal_authorized':False,'sizing_authorized':False,
        'same_sample_discovery_only':True,'future_unseen_confirmation_required':True,'no_rescue_tuning':True
      }
    }
    Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'pooled':pooled,'gates':gates,'candidate':result['candidate_generated_for_future_confirmation']},indent=2,sort_keys=True))
if __name__=='__main__': main()
