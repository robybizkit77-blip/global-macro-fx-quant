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
        assert changed['currencies'][focus]['horizons']['3m']['policy_delta_bp'] is None
        # Updating a rate should snapshot the level, never create a
        # corresponding CB repricing delta for an estimated futures quote.
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

    # A data-snapshot comparison cannot prove a futures repricing: historical
    # payloads omit listed contract identity, and capture time != quote day.
    prior_live = json.loads(json.dumps(base_row))
    prior_live['horizons']['3m']['rate'] = float(base_row['horizons']['3m']['rate']) - 0.01
    intraday = json.loads(json.dumps(base_row))
    intraday['horizons']['3m']['rate'] = float(base_row['horizons']['3m']['rate']) - 0.02
    historic_week = json.loads(json.dumps(base_row))
    historic_week['horizons']['3m']['rate'] = float(base_row['horizons']['3m']['rate']) - 0.03
    snapshots = [
        make_record(focus, historic_week, '2026-10-10T08:00:00Z'),
        make_record(focus, prior_live, '2026-10-14T09:00:00Z'),
        make_record(focus, intraday, '2026-10-15T01:00:00Z'),
        live_record,
    ]
    r = _estimated_repricing(focus, base_row, snapshots)
    assert r['previous_reference'] is None and r['weekly_reference'] is None, r
    assert r['change_1d_available'] is False and r['change_1w_available'] is False, r
    assert all(x['change_1d_bp'] is None and x['change_1w_bp'] is None
               for x in r['horizon_changes'].values()), r

    # Monday 2 Nov: a clean future capture must NOT make a misleading 1D
    # comparison to Fri 30 Oct or Thu 29 Oct, or a 1W historical snapshot.
    monday = json.loads(json.dumps(base_row))
    monday['as_of'] = '2026-11-02'
    monday['horizons']['6m']['rate'] = float(monday['horizons']['6m']['rate']) + 0.07
    monday_now = make_record(focus, monday, '2026-11-02T20:15:00Z')
    friday = json.loads(json.dumps(base_row))
    friday['as_of'] = '2026-10-30'
    friday['horizons']['6m']['rate'] = float(friday['horizons']['6m']['rate']) - 0.03
    friday_old = make_record(focus, friday, '2026-10-30T20:15:00Z')
    thursday = json.loads(json.dumps(base_row))
    thursday['as_of'] = '2026-10-29'
    thursday_old = make_record(focus, thursday, '2026-10-29T20:15:00Z')
    r = _estimated_repricing(focus, monday, [thursday_old, friday_old, monday_now])
    assert r['previous_reference'] is None and r['weekly_reference'] is None, r
    assert not r['change_1d_available'] and not r['change_1w_available'], r
    assert all(q['change_1d_bp'] is None and q['change_1w_bp'] is None
               for q in r['horizon_changes'].values()), r

    # Historical native-CB estimates remain on their pre-existing method;
    # prevent an unrelated backwards-incompatible governance change.
    native = json.loads(json.dumps(base_row))
    native['method_id'] = 'NATIVE_CB_ESTIMATED_V1'
    native['source'] = 'Native CB informational snapshot'
    previous_native = json.loads(json.dumps(native))
    previous_native['horizons']['3m']['rate'] -= 0.01
    previous_record = make_record(focus, previous_native, '2026-10-14T09:00:00Z')
    current_record = make_record(focus, native, '2026-10-15T08:00:00Z')
    native_result = _estimated_repricing(focus, native, [previous_record,current_record])
    assert native_result['change_1d_available'] is True, native_result
    assert native_result['horizon_changes']['3m']['change_1d_bp'] == 1.0, native_result

else:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'history.jsonl'
        r = append_changed_snapshots(VIEW, '2026-10-15T08:00:00Z', p)
        assert r['status']=='PASS' and r['appended']==0 and r['currencies']==[], r
        assert load_history(p)==[]
    assert not estimated  # Conflict-graded visible levels are not snapshottable.
    print('OIS_ESTIMATED_ZERO_INPUT_FAIL_CLOSED_PASS')

print('PASS OIS estimated snapshot/repricing V2 method isolation')
