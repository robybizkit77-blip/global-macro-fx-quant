#!/usr/bin/env python3
import argparse, json
from collections import Counter, defaultdict
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text())


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--contract', required=True)
    p.add_argument('--ledger', required=True)
    p.add_argument('--output', required=True)
    a=p.parse_args()
    c=load(a.contract); l=load(a.ledger)
    assert c['schema']=='GMFQ_G4USD_DOVISH_DIVERGENCE_FORWARD_SHADOW_CONTRACT_V1'
    assert c['status']=='FROZEN_WAITING_FOR_UNSEEN_OBSERVATIONS'
    assert l['schema']=='GMFQ_G4USD_DOVISH_DIVERGENCE_FORWARD_SHADOW_LEDGER_V1'
    assert l['append_only'] is True
    cutoff=c['historical_cutoff_reference_period']
    allowed=set(c['eligible_currencies'])
    seen=set(); rows=[]
    for r in l['signals']:
        k=(r['currency'], r['reference_period'])
        assert k not in seen; seen.add(k)
        assert r['currency'] in allowed
        assert r['reference_period'] > cutoff
        assert r['state']=='CONTRADICTORY'
        assert float(r['d_diff_2y']) < 0
        assert r['signal_direction'] in ('LOCAL_WEAKER_VS_USD','LOCAL_STRONGER_VS_USD')
        for h in ('outcome_1m','outcome_3m'):
            if h in r and r[h] is not None:
                assert isinstance(r[h], (int,float))
        rows.append(r)
    matured3=[r for r in rows if r.get('outcome_3m') is not None]
    matured1=[r for r in rows if r.get('outcome_1m') is not None]
    by_ccy=defaultdict(list)
    for r in matured3: by_ccy[r['currency']].append(float(r['outcome_3m']))
    n3=len(matured3); ccys=set(r['currency'] for r in matured3)
    m1=(sum(float(r['outcome_1m']) for r in matured1)/len(matured1)) if matured1 else None
    m3=(sum(float(r['outcome_3m']) for r in matured3)/n3) if n3 else None
    positive3=sum(1 for vals in by_ccy.values() if sum(vals)/len(vals)>0)
    counts=Counter(r['currency'] for r in matured3)
    max_share=(max(counts.values())/n3) if n3 else None
    g=c['confirmation_gate']
    gates={
      'minimum_matured_3m_observations': n3>=g['minimum_matured_3m_observations'],
      'minimum_currencies_represented': len(ccys)>=g['minimum_currencies_represented'],
      'pooled_mean_1m_gt_zero': m1 is not None and m1>0,
      'pooled_mean_3m_gt_zero': m3 is not None and m3>0,
      'minimum_currencies_positive_3m': positive3>=g['minimum_currencies_positive_3m'],
      'maximum_single_currency_share': max_share is not None and max_share<=g['maximum_single_currency_share']
    }
    enough=n3>=g['minimum_matured_3m_observations']
    confirmed=enough and all(gates.values())
    out={
      'schema':'GMFQ_G4USD_DOVISH_DIVERGENCE_FORWARD_SHADOW_RECEIPT_V1',
      'status':'FORWARD_CONFIRMED_PENDING_PROMOTION_REVIEW' if confirmed else ('FORWARD_GATE_FAILED_NO_TUNING' if enough else 'WAITING_FOR_UNSEEN_OBSERVATIONS'),
      'signals_total':len(rows),'matured_1m':len(matured1),'matured_3m':n3,
      'currencies_matured_3m':sorted(ccys),'pooled_mean_1m':m1,'pooled_mean_3m':m3,
      'positive_currencies_3m':positive3,'maximum_single_currency_share':max_share,
      'gates':gates,
      'forward_edge_confirmed':confirmed,
      'production_signal_authorized':False,
      'sizing_authorized':False,
      'no_rescue_tuning':True
    }
    Path(a.output).write_text(json.dumps(out, indent=2, sort_keys=True)+'\n')
    print(json.dumps(out, indent=2, sort_keys=True))

if __name__=='__main__': main()
