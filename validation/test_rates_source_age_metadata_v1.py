#!/usr/bin/env python3
"""Prove retained CHF/NZD source dates cannot be described as current.
No official series download, new market observation or core scoring effects.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from build_rates_audit_metadata import build, source_status

ROOT=Path(__file__).resolve().parents[1]
src=json.loads((ROOT/'live_data/sections/NATIVE_RATES_DATA.json').read_text())
out=build(src,'2026-10-23')
assert out['schema']=='GMFQ_RATES_AUDIT_METADATA_V1'
assert set(out['expected_rates'])=={'USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'}
assert out['audit_date']=='2026-10-23'
assert out['rates']['CHF']['current_as_of']=='2026-09-30'
assert out['rates']['CHF']['age_calendar_days']==23
assert out['rates']['CHF']['status']=='VALIDATED_HISTORICAL_SOURCE_BLOCKED'
assert out['rates']['CHF']['action']=='SOURCE_EXPORT_RECOVERY_REQUIRED'
assert out['rates']['CHF']['source_access']=='SNB_EXPORT_BLOCKED'
assert out['rates']['NZD']['current_as_of']=='2026-10-16'
assert out['rates']['NZD']['age_calendar_days']==7
assert out['rates']['NZD']['status']=='MANUAL_REVIEWED_LAGGING'
assert out['rates']['NZD']['action']=='MANUAL_OFFICIAL_REVIEW_REQUIRED'
assert out['rates']['NZD']['source_access']=='RBNZ_B2_MANUAL_DOUBLE_REVIEW'
assert out['rates']['AUD']['status']=='SOURCE_CADENCE_VALIDATED'
assert out['rates']['AUD']['source_access']=='RESERVE_BANK_OF_AUSTRALIA_F2_WEEKLY_FILE'
for c in ('USD','EUR','GBP','JPY','CAD'):
    assert out['rates'][c]['status']=='RECENT_OFFICIAL_OBSERVATION'
    assert out['rates'][c]['action']=='SOURCE_DATE_VALIDATED'
    assert out['rates'][c]['age_calendar_days']>=0
# RBNZ does not become an automatically certified feed simply by
# changing its date to yesterday.
new=copy.deepcopy(src)
new['NZD']['date']='2026-10-22'
z=build(new,'2026-10-23')
assert z['rates']['NZD']['status']=='MANUAL_REVIEWED_RECENT'
assert z['rates']['NZD']['source_access']=='RBNZ_B2_MANUAL_DOUBLE_REVIEW'
assert z['rates']['NZD']['action']=='MANUAL_SOURCE_VERIFIED'
# SNB source block persists; moving a date without fixing the adapter
# cannot magically make the source LIVE_FETCH.
new['CHF']['date']='2026-10-22'
z=build(new,'2026-10-23')
assert z['rates']['CHF']['status']=='VALIDATED_HISTORICAL_SOURCE_BLOCKED'
assert z['rates']['CHF']['action']=='SOURCE_EXPORT_RECOVERY_REQUIRED'
assert source_status('EUR','2026-10-01','2026-10-23')['status']=='OFFICIAL_OBSERVATION_LAGGING'
assert source_status('AUD','2026-10-01','2026-10-23')['status']=='SOURCE_CADENCE_LAGGING'
for fn in (lambda: build(src,'2026-10-01'),lambda: build({},'2026-10-23')):
    try: fn()
    except ValueError: pass
    else: raise AssertionError('Unverified source-date or missing currency must fail closed')
assert 'core_score' not in out and 'bias' not in out
print('RATES_SOURCE_AGE_NO_FALSE_CURRENT_PASS')
