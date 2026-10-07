#!/usr/bin/env python3
import json, hashlib
from datetime import datetime, timezone
from pathlib import Path

LEDGER = Path('validation/FORWARD_SNAPSHOT_LEDGER_V1_2026-10-07.json')
PAYLOAD = Path('validation/DASHBOARD_PAIR_RENDER_PAYLOAD_V1_2026-10-07.json')

ledger = json.loads(LEDGER.read_text(encoding='utf-8'))
payload = json.loads(PAYLOAD.read_text(encoding='utf-8'))

pairs = payload.get('pairs', {})
assert len(pairs) == 28, f'expected 28 pairs, got {len(pairs)}'

# Stable, economically meaningful fingerprint only. Presentation text and timestamps are excluded.
semantic = {}
for pair in sorted(pairs):
    p = pairs[pair] or {}
    semantic[pair] = {
        'macro_anchor': p.get('macro_anchor') or p.get('macro') or p.get('fundamental_anchor_macro'),
        'state': p.get('state'),
        'robustness_badge': p.get('robustness_badge'),
    }

fingerprint = hashlib.sha256(json.dumps(semantic, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

state_counts = {
    'TRANSMISSION_CLEAN': 0,
    'TRANSMISSION_PARTIAL': 0,
    'TRANSMISSION_DIVERGENT': 0,
    'TRANSMISSION_WITHHELD': 0,
}
robustness_counts = {'ROBUST_ACROSS_RULES': 0, 'RULE_SENSITIVE': 0}
focus = {
    'clean_robust': [],
    'divergent_robust': [],
    'partial_robust': [],
    'rule_sensitive': [],
    'withheld': [],
}

for pair, p in sorted(pairs.items()):
    st = p.get('state')
    rb = p.get('robustness_badge')
    if st not in state_counts:
        raise AssertionError((pair, 'bad state', st))
    state_counts[st] += 1
    if rb not in robustness_counts:
        raise AssertionError((pair, 'bad robustness', rb))
    robustness_counts[rb] += 1
    if st == 'TRANSMISSION_WITHHELD':
        focus['withheld'].append(pair)
    elif rb == 'RULE_SENSITIVE':
        focus['rule_sensitive'].append(pair)
    elif st == 'TRANSMISSION_CLEAN':
        focus['clean_robust'].append(pair)
    elif st == 'TRANSMISSION_DIVERGENT':
        focus['divergent_robust'].append(pair)
    elif st == 'TRANSMISSION_PARTIAL':
        focus['partial_robust'].append(pair)

last = ledger['snapshots'][-1]
last_fp = last.get('semantic_fingerprint')

# Backward-compatible dedupe for the manually seeded first snapshot.
def equivalent_to_seeded_last():
    return (
        last.get('state_counts') == state_counts and
        last.get('robustness_counts') == robustness_counts and
        all(last.get('focus_buckets', {}).get(k, []) == focus[k] for k in focus)
    )

if last_fp == fingerprint or (last_fp is None and equivalent_to_seeded_last()):
    print('NO_NEW_SNAPSHOT: semantic state unchanged')
    raise SystemExit(0)

now = datetime.now(timezone.utc).replace(microsecond=0)
iso = now.isoformat().replace('+00:00','Z')
snapshot_id = f'{iso}__AUTO_V1'

snap = {
    'snapshot_id': snapshot_id,
    'captured_at': iso,
    'source_payload': str(PAYLOAD),
    'semantic_fingerprint': fingerprint,
    'pair_count': 28,
    'state_counts': state_counts,
    'robustness_counts': robustness_counts,
    'focus_buckets': focus,
    'historical_evidence_status': last.get('historical_evidence_status', {}),
    'forward_outcomes': {'t_plus_5': None, 't_plus_20': None, 't_plus_60': None},
    'frozen': True,
}
ledger['snapshots'].append(snap)
LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(f'APPENDED_FORWARD_SNAPSHOT {snapshot_id} {fingerprint[:12]}')
