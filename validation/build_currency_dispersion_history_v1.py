#!/usr/bin/env python3
import json, hashlib
from datetime import datetime, timezone
from pathlib import Path

SRC = Path('validation/CURRENCY_CROSS_DISPERSION_V1_2026-10-07.json')
OUT = Path('validation/CURRENCY_CROSS_DISPERSION_HISTORY_V1_2026-10-07.json')

def semantic_currency_view(x):
    out = {}
    for c, d in sorted(x['currencies'].items()):
        out[c] = {
            'macro_relative': d['macro_relative'],
            'transmission_states': d['transmission_states'],
            'robustness': d['robustness'],
            'layer_dispersion': d['layer_dispersion'],
        }
    return out

src = json.loads(SRC.read_text())
view = semantic_currency_view(src)
fingerprint = hashlib.sha256(json.dumps(view, sort_keys=True, separators=(',',':')).encode()).hexdigest()[:16]

if OUT.exists():
    hist = json.loads(OUT.read_text())
else:
    hist = {
        'schema': 'GMFQ_CURRENCY_CROSS_DISPERSION_HISTORY_V1',
        'status': 'ACTIVE_RESEARCH_HISTORY',
        'append_only': True,
        'snapshots': [],
        'guards': {
            'changes_engine_rules': False,
            'changes_live_data': False,
            'changes_oos_baseline': False,
            'production_promotion': False,
            'creates_universal_score': False,
            'retroactive_history_rewrite': False,
        }
    }

if hist['snapshots'] and hist['snapshots'][-1]['semantic_fingerprint'] == fingerprint:
    print('NO_SEMANTIC_CHANGE')
else:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
    hist['snapshots'].append({
        'snapshot_id': f'{now}__CURRENCY_DISPERSION_V1',
        'captured_at': now,
        'semantic_fingerprint': fingerprint,
        'currencies': view,
        'frozen': True,
    })
    OUT.write_text(json.dumps(hist, indent=2, ensure_ascii=False) + '\n')
    print('APPENDED', fingerprint)
