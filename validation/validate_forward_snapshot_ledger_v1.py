#!/usr/bin/env python3
import json
from pathlib import Path

P = Path('validation/FORWARD_SNAPSHOT_LEDGER_V1_2026-10-07.json')
obj = json.loads(P.read_text(encoding='utf-8'))
assert obj['schema'] == 'GMFQ_FORWARD_SNAPSHOT_LEDGER_V1'
assert obj['status'] == 'ACTIVE_RESEARCH_LEDGER'
assert obj['immutability_contract']['append_only'] is True
assert obj['immutability_contract']['retroactive_label_changes_forbidden'] is True
assert obj['evaluation_policy']['no_retroactive_tuning'] is True
assert obj['evaluation_policy']['do_not_change_original_state_after_outcome'] is True
assert obj['engine_commit'] == 'ff52198a75cc67f7dae96fc2bbf65623f170791c'
assert obj['rules_fingerprint'] == '3356baf0'
assert len(obj['snapshots']) >= 1
ids = [s['snapshot_id'] for s in obj['snapshots']]
assert len(ids) == len(set(ids)), 'snapshot IDs must be unique'
for s in obj['snapshots']:
    assert s['frozen'] is True
    assert s['pair_count'] == 28
    assert sum(s['state_counts'].values()) == 28
    assert sum(s['robustness_counts'].values()) == 28
    assert set(s['forward_outcomes']) == {'t_plus_5','t_plus_20','t_plus_60'}
assert all(v is False for v in obj['guards'].values())
print('PASS_FORWARD_SNAPSHOT_LEDGER_V1')
