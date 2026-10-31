#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ois_estimated_snapshot_v1 import append_changed_snapshots, load_history, make_record
from build_ois_operational_view_v1 import _estimated_repricing, DAILY_REFERENCE_MIN_AGE, WEEKLY_REFERENCE_MIN_AGE

ROOT = Path(__file__).resolve().parents[2]
VIEW = json.loads((ROOT / 'live_data/sections/OIS_OPERATIONAL_VIEW.json').read_text(encoding='utf-8'))

all_estimated=[c for c,r in VIEW['currencies'].items() if r['operational_status']=='GREEN_ESTIMATED']
assert len(all_estimated)==VIEW['summary']['green_estimated']
estimated=[c for c in all_estimated if VIEW['currencies'][c].get(
    'source_conflict_status') != 'UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT']
for c in set(all_estimated)-set(estimated):
    row=VIEW['currencies'][c]
    assert row['change_1d_available'] is False
    assert row['change_1w_available'] is False
    assert all(row['horizons'][h]['policy_delta_bp'] is None
               and row['horizons'][h]['change_1d_bp'] is None
               and row['horizons'][h]['change_1w_bp'] is None
               for h in ('3m','6m','12m'))

assert int(DAILY_REFERENCE_MIN_AGE.total_seconds() / 3600) == 18
assert WEEKLY_REFERENCE_MIN_AGE.days == 5

# A fully withheld estimated OIS input is a VALID fail-closed result: do not
# fabricate an estimated curve just to satisfy the snapshot append test.
# Repricing fixture below exercises live estimates only when actually available.
if estimated:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'history.jsonl'
        r1 = append_changed_snapshots(VIEW, '2026-10-15T08:00:00Z', p)
        assert r1['appended'] == len(estimated), r1
        r2 = append_changed_snapshots(VIEW, '2026-10-16T08:00:00Z', p)
        assert r2['appended'] == 0, r2
        rows = load_history(p)
        assert len(rows) == len(estimated)
        changed = json.loads(json.dumps(VIEW))
        focus=estimated[0]
        before=float(changed['currencies'][focus]['horizons']['3m']['rate'])
        changed['currencies'][focus]['horizons']['3m']['rate'] = before + 0.05
        changed['currencies'][focus]['horizons']['3m']['policy_delta_bp'] = float(changed['currencies'][focus]['horizons']['3m']['policy_delta_bp']) + 5.0
        r3 = append_changed_snapshots(changed, '2026-10-16T08:00:00Z', p)
        assert r3['appended'] == 1 and r3['currencies'] == [focus], r3
        rows = load_history(p)
        assert len(rows) == len(estimated)+1

    # Any methodology switch must never be interpreted as market repricing.
    base_row = json.loads(json.dumps(VIEW['currencies'][focus]))
    base_row['method_id'] = 'TRADINGVIEW_DATED_FUTURES_SSR_V2'
    base_row['source'] = 'TradingView public server-rendered contract pages · exchange-labelled dated futures'
    legacy_row = json.loads(json.dumps(base_row))
    legacy_row['method_id'] = 'TRADINGVIEW_EXCHANGE_LABELLED_FUTURES_SSR_V1'
    legacy_row['source'] = 'superseded V1 source'
    legacy_record = make_record(focus, legacy_row, '2026-10-14T08:00:00Z')
    live_record = make_record(focus, base_row, '2026-10-15T08:00:00Z')
    r = _estimated_repricing(focus, base_row, [legacy_record, live_record])
    assert r['previous_reference'] is None, r
    assert r['weekly_reference'] is None, r
    assert r['change_1d_available'] is False, r
    assert r['change_1w_available'] is False, r
    assert all(x['change_1d_bp'] is None and x['change_1w_bp'] is None for x in r['horizon_changes'].values()), r

    # A same-method intraday snapshot must NOT be mislabeled as 1D.
    intraday = json.loads(json.dumps(base_row))
    intraday['horizons']['3m']['rate'] = float(base_row['horizons']['3m']['rate']) - 0.02
    intraday_record = make_record(focus, intraday, '2026-10-15T01:00:00Z')
    r = _estimated_repricing(focus, base_row, [intraday_record, live_record])
    assert r['previous_reference'] is None, r
    assert r['change_1d_available'] is False, r
    assert r['horizon_changes']['3m']['change_1d_bp'] is None, r

    # Once a prior-session same-method V2 snapshot exists, 1D becomes legal.
    prior_live = json.loads(json.dumps(base_row))
    prior_live['horizons']['3m']['rate'] = float(base_row['horizons']['3m']['rate']) - 0.01
    prior_live_record = make_record(focus, prior_live, '2026-10-14T09:00:00Z')
    r = _estimated_repricing(focus, base_row, [legacy_record, prior_live_record, intraday_record, live_record])
    assert r['previous_reference'] == '2026-10-14T09:00:00Z', r
    assert r['change_1d_available'] is True, r
    assert r['horizon_changes']['3m']['change_1d_bp'] == 1.0, r

    # Weekly repricing remains unavailable until a same-method observation is >=5 days old.
    week_row = json.loads(json.dumps(base_row))
    week_row['horizons']['3m']['rate'] = float(base_row['horizons']['3m']['rate']) - 0.03
    week_record = make_record(focus, week_row, '2026-10-10T08:00:00Z')
    r = _estimated_repricing(focus, base_row, [week_record, prior_live_record, live_record])
    assert r['weekly_reference'] == '2026-10-10T08:00:00Z', r
    assert r['change_1w_available'] is True, r
    assert r['horizon_changes']['3m']['change_1w_bp'] == 3.0, r

else:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'history.jsonl'
        r = append_changed_snapshots(VIEW, '2026-10-15T08:00:00Z', p)
        assert r['status']=='PASS' and r['appended']==0 and r['currencies']==[], r
        assert load_history(p)==[]
    assert not estimated  # Conflict-graded visible levels are not snapshottable.
    print('OIS_ESTIMATED_ZERO_INPUT_FAIL_CLOSED_PASS')

print('PASS OIS estimated snapshot/repricing V2 method isolation')
