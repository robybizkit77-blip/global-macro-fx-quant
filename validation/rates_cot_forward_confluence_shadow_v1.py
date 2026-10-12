#!/usr/bin/env python3
import argparse, json
from collections import Counter, defaultdict
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--contract', required=True)
    p.add_argument('--ledger', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    c = load(a.contract)
    l = load(a.ledger)
    assert c['schema'] == 'GMFQ_RATES_COT_FORWARD_CONFLUENCE_SHADOW_CONTRACT_V1'
    assert c['status'] == 'FROZEN_WAITING_FOR_UNSEEN_OBSERVATIONS'
    assert l['schema'] == 'GMFQ_RATES_COT_FORWARD_CONFLUENCE_SHADOW_LEDGER_V1'
    assert l['append_only'] is True
    allowed = set(c['eligible_currencies'])
    seen = set(); rows = []
    for r in l['signals']:
        key = (r['currency'], r['rates_reference_period'])
        assert key not in seen; seen.add(key)
        assert r['currency'] in allowed
        assert r['rates_reference_period'] > '2026-08'
        assert r['cot_report_date'] > '2026-09-08'
        assert r['rates_state'] == 'CONTRADICTORY'
        assert float(r['d_diff_2y']) < 0
        assert float(r['cot_percentile_104w']) >= 80
        assert r['signal_direction'] == 'LOCAL_WEAKER_VS_USD'
        assert r['cot_research_available_date'] >= r['rates_signal_known_date']
        for h in ('outcome_5d','outcome_1m','outcome_3m'):
            if r.get(h) is not None:
                assert isinstance(r[h], (int,float))
        rows.append(r)
    matured5 = [r for r in rows if r.get('outcome_5d') is not None]
    matured1 = [r for r in rows if r.get('outcome_1m') is not None]
    matured3 = [r for r in rows if r.get('outcome_3m') is not None]
    by_ccy = defaultdict(list)
    for r in matured1:
        by_ccy[r['currency']].append(float(r['outcome_1m']))
    n1 = len(matured1)
    ccys = set(r['currency'] for r in matured1)
    m5 = sum(float(r['outcome_5d']) for r in matured5)/len(matured5) if matured5 else None
    m1 = sum(float(r['outcome_1m']) for r in matured1)/n1 if n1 else None
    hit5 = sum(1 for r in matured5 if float(r['outcome_5d']) > 0)/len(matured5) if matured5 else None
    positive1 = sum(1 for vals in by_ccy.values() if sum(vals)/len(vals) > 0)
    counts = Counter(r['currency'] for r in matured1)
    max_share = max(counts.values())/n1 if n1 else None
    g = c['candidate_generation_gate']
    gates = {
      'minimum_matured_1m_events': n1 >= g['minimum_matured_1m_events'],
      'minimum_currencies_represented': len(ccys) >= g['minimum_currencies_represented'],
      'pooled_mean_5d_gt_zero': m5 is not None and m5 > 0,
      'pooled_mean_1m_gt_zero': m1 is not None and m1 > 0,
      'directional_accuracy_5d_min': hit5 is not None and hit5 >= g['directional_accuracy_5d_min'],
      'minimum_currencies_positive_1m': positive1 >= g['minimum_currencies_positive_1m'],
      'maximum_single_currency_share': max_share is not None and max_share <= g['maximum_single_currency_share']
    }
    enough = n1 >= g['minimum_matured_1m_events']
    generated = enough and all(gates.values())
    out = {
      'schema':'GMFQ_RATES_COT_FORWARD_CONFLUENCE_SHADOW_RECEIPT_V1',
      'status':'FORWARD_CONFLUENCE_CANDIDATE_GENERATED_PENDING_SEPARATE_VALIDATION' if generated else ('FORWARD_CONFLUENCE_GATE_FAILED_NO_TUNING' if enough else 'WAITING_FOR_UNSEEN_OBSERVATIONS'),
      'signals_total':len(rows),
      'matured_5d':len(matured5),
      'matured_1m':n1,
      'matured_3m':len(matured3),
      'currencies_matured_1m':sorted(ccys),
      'pooled_mean_5d':m5,
      'pooled_mean_1m':m1,
      'directional_accuracy_5d':hit5,
      'positive_currencies_1m':positive1,
      'maximum_single_currency_share':max_share,
      'gates':gates,
      'candidate_generated':generated,
      'edge_certified':False,
      'production_signal_authorized':False,
      'sizing_authorized':False,
      'no_rescue_tuning':True
    }
    Path(a.output).write_text(json.dumps(out, indent=2, sort_keys=True)+'\n')
    print(json.dumps(out, indent=2, sort_keys=True))

if __name__ == '__main__':
    main()
