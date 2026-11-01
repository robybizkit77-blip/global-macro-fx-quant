#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIEW = json.loads((ROOT/'live_data/sections/OIS_OPERATIONAL_VIEW.json').read_text())
POLICY = json.loads((ROOT/'validation/cb_pricing/OIS_OPERATIONAL_COVERAGE_POLICY_V1_2026-10-15.json').read_text())
OFFICIAL = json.loads((ROOT/'live_data/sections/OIS_DATA.json').read_text())['currencies']
EST = json.loads((ROOT/'live_data/sections/CB_PRICING_ESTIMATED.json').read_text())['currencies']

from datetime import datetime, timezone
import sys
sys.path.insert(0,str(ROOT/'validation'))
from validate_ois_operational_freshness import check
summary=VIEW['summary']
assert len(VIEW['currencies'])==8
assert set(VIEW['currencies'])=={'USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'}
assert summary['g8_total']==8
assert summary['operational_green']==summary['green_official']+summary['green_estimated']
assert summary['operational_green']+summary['operational_withheld']==8
assert summary['green_official']==sum(r['operational_status']=='GREEN_OFFICIAL' for r in VIEW['currencies'].values())
assert summary['green_estimated']==sum(r['operational_status']=='GREEN_ESTIMATED' for r in VIEW['currencies'].values())
assert summary['operational_withheld']==sum(r['operational_status']=='WITHHELD' for r in VIEW['currencies'].values())
assert VIEW['status']==('PARTIAL_WITHHELD' if summary['operational_withheld'] else 'GREEN_8_OF_8')
assert not check(VIEW,datetime.now(timezone.utc).date())
for ccy, row in VIEW['currencies'].items():
    assert row['operational_status'] in ('GREEN_OFFICIAL','GREEN_ESTIMATED','WITHHELD')
    if row['operational_status'] == 'GREEN_OFFICIAL':
        assert OFFICIAL[ccy]['status'] == 'ACTIVE'
        assert row['backtest_eligible_as_official'] is True
    elif row['operational_status'] == 'GREEN_ESTIMATED':
        assert OFFICIAL[ccy]['status'] == 'WITHHELD'
        assert EST[ccy]['status'] in ('ESTIMATED_ACTIVE','ESTIMATED_PARTIAL')
        assert row['backtest_eligible_as_official'] is False
        assert row['confidence'] in ('A','A/B','B','B/C','C')
        assert any((row['horizons'].get(h) or {}).get('rate') is not None for h in ('3m','6m','12m'))
        assert row['direction_vs_policy'] == 'WITHHELD'
        assert row['policy_repricing_inference_allowed'] is False
        assert row['raw_level_gap_scope'] == 'DESCRIPTIVE_LEVEL_ARITHMETIC_NOT_EXPECTED_CB_RATE'
        assert all(row['horizons'][h]['policy_delta_bp'] is None for h in ('3m','6m','12m'))
        assert all(row['horizons'][h]['raw_level_gap_not_policy_repricing'] is True for h in ('3m','6m','12m'))

# Derive approved official scope from canonical OIS, never a frozen currency list.
# An unauthorized estimated/secondary row cannot count as a certified source.
approved={c for c,o in OFFICIAL.items() if o.get('status')=='ACTIVE'}
displayed={c for c,r in VIEW['currencies'].items()
           if r['operational_status']=='GREEN_OFFICIAL'}
assert displayed==approved, (displayed,approved)
for c in approved:
    assert VIEW['currencies'][c]['quality']=='OFFICIAL_CERTIFIED'
    assert VIEW['currencies'][c]['official_status']=='ACTIVE'
    assert VIEW['currencies'][c]['as_of']==OFFICIAL[c]['as_of']
    assert VIEW['currencies'][c]['horizons']==OFFICIAL[c]['horizons']
for ccy,row in VIEW['currencies'].items():
    if row['operational_status']=='WITHHELD':
        assert all((row['horizons'].get(h) or {}).get('rate') is None for h in ('3m','6m','12m'))
        assert row['change_1d_available'] is False and row['change_1w_available'] is False
print('PASS OIS operational dynamic G8 coverage',summary)

# Missing estimated levels must withhold only that currency, never abort G8.
import tempfile
import importlib.util
spec = importlib.util.spec_from_file_location('ois_builder_failclosed_case', ROOT/'validation/cb_pricing/build_ois_operational_view_v1.py')
import sys
sys.path.insert(0,str(ROOT/'validation/cb_pricing'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
original_est = builder.EST
with tempfile.TemporaryDirectory() as td:
    est_case=json.loads(original_est.read_text(encoding='utf-8'))
    missing=est_case['currencies']['NZD']
    missing['horizons']={h:{'rate':None} for h in ('3m','6m','12m')}
    case=Path(td)/'estimated_missing_nzd.json'
    case.write_text(json.dumps(est_case),encoding='utf-8')
    builder.EST=case
    try:
        recovered=builder.build()
    finally:
        builder.EST=original_est
    assert recovered['summary']['g8_total']==8
    assert recovered['currencies']['NZD']['operational_status']=='WITHHELD'
    assert recovered['currencies']['NZD']['withheld_reason']=='NO_USABLE_OFFICIAL_OR_ESTIMATED_PRICING'
    assert all(recovered['currencies']['NZD']['horizons'][h]['rate'] is None for h in ('3m','6m','12m'))
    assert recovered['summary']['operational_green']+recovered['summary']['operational_withheld']==8
print('PASS OIS missing-estimate fail-closed recovery')
# Per-tenor verified secondary quotes are observational context ONLY.
from datetime import date, timedelta
base_day=date.today()
sample={'currencies': {'USD': {'status': 'LIVE_SECONDARY_READY', 'source': 'fixture',
    'horizons': {
        h: {'rate': 4.0 + n * 0.1, 'contract': 'ZQ' + h, 'symbol': 'CBOT:ZQ' + h,
            'quote_as_of': (base_day - timedelta(days=(1 if h != '6m' else 0))).isoformat(),
            'quote_timestamp_verified': True,
            'quote_timestamp_source': 'SSR_DAILY_BAR_DATA_UPDATE_TIME'}
        for n, h in enumerate(('3m', '6m', '12m'))
    }}}}
ctx=builder._secondary_verified_quotes('USD',sample,base_day)
assert ctx['status']=='INDICATIVE_OBSERVATIONS_NON_OIS',ctx
assert ctx['date_mismatch'] is True,ctx
assert ctx['full_curve_usable'] is False
assert ctx['cross_date_join_allowed'] is False
assert ctx['policy_delta_allowed'] is False
assert ctx['repricing_signal_allowed'] is False
assert ctx['backtest_eligible_as_official'] is False
assert all(set(ctx['horizons'][h])=={'contract','quote_as_of','rate_indicative','source_quality'}
           for h in ('3m','6m','12m'))
bad=json.loads(json.dumps(sample))
bad['currencies']['USD']['horizons']['6m']['quote_timestamp_verified']=False
cut=builder._secondary_verified_quotes('USD',bad,base_day)
assert '6m' not in cut['horizons'] and len(cut['horizons'])==2
bad['currencies']['USD']['horizons']['3m']['quote_as_of']=(base_day-timedelta(days=8)).isoformat()
cut=builder._secondary_verified_quotes('USD',bad,base_day)
assert set(cut['horizons'])=={'12m'}
print('PASS OIS individual quote context fail-closed')

# For withheld production currencies a context must NEVER fill the OIS curve.
for ccy in ('USD','EUR','CHF'):
    row=VIEW['currencies'][ccy]
    ctx=row.get('secondary_quote_context')
    if ctx:
        assert row['operational_status']=='WITHHELD',row
        assert row['backtest_eligible_as_official'] is False
        assert ctx['full_curve_usable'] is False
        assert all(row['horizons'][h]['rate'] is None for h in ('3m','6m','12m'))
        assert all(row['horizons'][h]['policy_delta_bp'] is None for h in ('3m','6m','12m'))

