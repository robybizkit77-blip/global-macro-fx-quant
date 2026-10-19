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

assert {c for c,r in VIEW['currencies'].items() if r['operational_status']=='GREEN_OFFICIAL'} == {'AUD','CAD','GBP','JPY'}
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
