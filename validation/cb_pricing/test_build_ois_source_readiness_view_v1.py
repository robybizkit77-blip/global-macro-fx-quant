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
    pending={c for c in plan['blocked_sources']
             if view['currencies'][c]['operational_status']!='GREEN_OFFICIAL'}
    assert set(report['currencies'])==pending
    assert report['blocked_currency_count']==sum(
        row['operational_status']=='WITHHELD'
        for c,row in view['currencies'].items() if c in pending)
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
    # Simulate a future official approval that happens OUTSIDE this builder.
    # Historical access-plan candidate remains in the registry, but is no
    # longer reported as an unresolved operational obstacle.
    def activate(*codes):
        future_view=deepcopy(view)
        future_official=deepcopy(official)
        for c in codes:
            future_official['currencies'][c]=deepcopy(official['currencies']['GBP'])
            future_view['currencies'][c]=deepcopy(view['currencies']['GBP'])
        v=future_view['summary']
        v['green_official']+=len(codes)
        v['operational_green']+=len(codes)
        v['operational_withheld']-=len(codes)
        result=build(plan,future_view,future_official,rates,chf10,today=today)
        assert not (set(codes)&set(result['currencies'])),codes
        assert set(result['currencies'])==set(report['currencies'])-set(codes)
        assert result['blocked_currency_count']==report['blocked_currency_count']-len(codes)
        assert result['no_automatic_promotions'] and result['prices_omitted']
        return result,future_view
    us_approved,us_view=activate('USD')
    assert len(us_approved['currencies'])==3
    assert 'CHF' in us_approved['currencies']
    ch_approved,_=activate('CHF')
    assert 'government_rates' not in ch_approved['currencies'].get('CHF',{})
    two_approved,_=activate('USD','CHF')
    assert set(two_approved['currencies'])=={'EUR','NZD'}
    # Never accept a forged official flag in the derived operational view
    # without the separately active, certified canonical OIS runtime.
    forged=deepcopy(view)
    forged['currencies']['USD']=deepcopy(us_view['currencies']['USD'])
    # Preserve a coherent derived summary so the negative test reaches the
    # actual official-runtime gate, not an unrelated summary mismatch.
    forged['summary']['green_official']+=1
    forged['summary']['operational_green']+=1
    forged['summary']['operational_withheld']-=1
    try:build(plan,forged,official,rates,chf10,today=today)
    except ValueError as e:assert 'promotion bypassed official runtime' in str(e)
    else:raise AssertionError('Forged USD official source accepted')
    print('OIS_SOURCE_READINESS_DYNAMIC_PENDING_FIFTH_SOURCE_PASS')
    print('OIS_SOURCE_READINESS_FAIL_CLOSED_TEST_GREEN')

if __name__=="__main__":
    main()
