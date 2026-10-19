#!/usr/bin/env python3
"""Source-readiness: audited provenance and no hidden official rate promotion."""
from __future__ import annotations
import json
from copy import deepcopy
from datetime import date
from pathlib import Path
from build_ois_source_readiness_view_v1 import ACCESS, VIEW, OFFICIAL, RATES, CHF_SPOT, build

def main():
    plan,view,official,rates,chf10=[json.loads(Path(p).read_text(encoding="utf8"))
        for p in (ACCESS, VIEW, OFFICIAL, RATES, CHF_SPOT)]
    today=date.today().isoformat()
    report=build(plan,view,official,rates,chf10,today=today)
    assert report['status']=='READ_ONLY_SOURCE_READINESS'
    assert set(report['currencies'])=={'USD','EUR','CHF','NZD'}
    assert report['blocked_currency_count']==sum(
        row['operational_status']=='WITHHELD' for row in view['currencies'].values())
    assert report['prices_omitted'] is True
    assert all(report[k] is True for k in (
        'no_core_score_effect','no_bias_effect','no_sizing_effect',
        'no_backtest_effect','no_automatic_promotions'))
    for k,row in report['currencies'].items():
        assert row['status']==view['currencies'][k]['operational_status']
        assert row['dates_joinable'] is False and row['price_or_curve_embedded'] is False
        assert row['source_url'].startswith('https://')
        assert not row['usable_for_policy_pricing'] and not row['backtest_eligible_as_official']
        assert row['source_reviewed_as_of']==plan['reviewed_as_of']
        assert row['activation_requirement'] and row['obstacle']
        assert set(row['indicative_quote_dates']).issubset({'3m','6m','12m'})
    swiss=report['currencies']['CHF']['government_rates']
    assert swiss['has_new_verified_2y'] is False and swiss['cross_date_spread_allowed'] is False
    assert swiss['last_paired_2y10y_as_of']==rates['CHF']['date']
    assert swiss['separate_10y_snb_as_of'] in (chf10['as_of'],None)
    if '2026-10-19'==today:
        assert swiss['separate_10y_snb_as_of']=='2026-10-19'
    # Adversarial: data missing and unvalidated source must fail, never invent a 2Y.
    changed=deepcopy(view)
    changed['currencies']['EUR']['horizons']['3m']['rate']=3.5
    try:build(plan,changed,official,rates,chf10,today=today)
    except ValueError as e:assert 'withheld OIS level leak' in str(e)
    else:raise AssertionError('False EUR OIS price admitted')
    changed=deepcopy(plan)
    changed['governance']['no_automatic_promotions']=False
    try:build(changed,view,official,rates,chf10,today=today)
    except ValueError as e:assert 'may not change runtime' in str(e)
    else:raise AssertionError('Source promotion bypass admitted')
    future=deepcopy(rates)
    future['CHF']['date']='2099-01-01'
    try:build(plan,view,official,future,chf10,today=today)
    except ValueError as e:assert 'future-dated' in str(e)
    else:raise AssertionError('Future official CHF snapshot accepted')
    ignored=deepcopy(chf10)
    ignored['has_current_2y']=True
    sample=build(plan,view,official,rates,ignored,today=today)
    assert sample['currencies']['CHF']['government_rates']['separate_10y_snb_as_of'] is None
    print('OIS_SOURCE_READINESS_FAIL_CLOSED_TEST_GREEN')

if __name__=="__main__":
    main()
