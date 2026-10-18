#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIEW = json.loads((ROOT/'live_data/sections/OIS_OPERATIONAL_VIEW.json').read_text())
POLICY = json.loads((ROOT/'validation/cb_pricing/OIS_OPERATIONAL_COVERAGE_POLICY_V1_2026-10-15.json').read_text())
OFFICIAL = json.loads((ROOT/'live_data/sections/OIS_DATA.json').read_text())['currencies']
EST = json.loads((ROOT/'live_data/sections/CB_PRICING_ESTIMATED.json').read_text())['currencies']

assert VIEW['status'] == 'PARTIAL_WITHHELD'
assert VIEW['summary'] == {'g8_total':8,'operational_green':7,'green_official':4,'green_estimated':3,'operational_withheld':1}
assert POLICY['summary']['operational_green'] == 8  # legacy coverage target, not current live freshness
assert POLICY['summary']['operational_withheld'] == 0

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
assert {c for c,r in VIEW['currencies'].items() if r['operational_status']=='GREEN_ESTIMATED'} == {'USD','EUR','CHF'}
assert VIEW['currencies']['NZD']['operational_status']=='WITHHELD'
assert all(h['rate'] is None for h in VIEW['currencies']['NZD']['horizons'].values())
print('PASS OIS operational coverage 7 GREEN 1 WITHHELD')
