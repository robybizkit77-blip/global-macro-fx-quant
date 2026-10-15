#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ois_estimated_snapshot_v1 import append_changed_snapshots, load_history

ROOT = Path(__file__).resolve().parents[2]
VIEW = json.loads((ROOT / 'live_data/sections/OIS_OPERATIONAL_VIEW.json').read_text(encoding='utf-8'))

assert VIEW['status'] == 'GREEN_8_OF_8'
assert VIEW['summary']['operational_green'] == 8
for ccy in ('USD','EUR','CHF','NZD'):
    assert VIEW['currencies'][ccy]['operational_status'] == 'GREEN_ESTIMATED'

with tempfile.TemporaryDirectory() as td:
    p = Path(td) / 'history.jsonl'
    r1 = append_changed_snapshots(VIEW, '2026-10-15T08:00:00Z', p)
    assert r1['appended'] == 4, r1
    r2 = append_changed_snapshots(VIEW, '2026-10-16T08:00:00Z', p)
    assert r2['appended'] == 0, r2
    rows = load_history(p)
    assert len(rows) == 4
    changed = json.loads(json.dumps(VIEW))
    changed['currencies']['USD']['horizons']['3m']['rate'] = 4.05
    changed['currencies']['USD']['horizons']['3m']['policy_delta_bp'] = 17.5
    r3 = append_changed_snapshots(changed, '2026-10-16T08:00:00Z', p)
    assert r3['appended'] == 1 and r3['currencies'] == ['USD'], r3
    rows = load_history(p)
    assert len(rows) == 5

print('PASS OIS estimated snapshot/repricing V1')
