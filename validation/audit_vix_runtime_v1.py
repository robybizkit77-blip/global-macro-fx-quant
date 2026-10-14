#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D_PATH = ROOT / 'live_data' / 'sections' / 'D.json'
MANIFEST_PATH = ROOT / 'live_data' / 'manifest.v2.json'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize_series(obj):
    if isinstance(obj, dict):
        out = {'type': 'object', 'keys': sorted(obj.keys())}
        for k in ('as_of', 'date', 'latest_date', 'value', 'latest_value', 'source', 'source_name', 'status'):
            if k in obj:
                out[k] = obj[k]
        for k in ('dates', 'values', 'history'):
            if isinstance(obj.get(k), list):
                out[f'{k}_length'] = len(obj[k])
                if obj[k]:
                    out[f'{k}_last'] = obj[k][-1]
        return out
    if isinstance(obj, list):
        return {'type': 'array', 'length': len(obj), 'last': obj[-1] if obj else None}
    return {'type': type(obj).__name__, 'value': obj}


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    entries = {x['key']: x for x in manifest.get('sections', [])}
    d_entry = entries.get('D')
    if not d_entry:
        raise SystemExit('manifest.v2 missing D section')
    if d_entry.get('mode') != 'DIRECT_SINGLE_PART' or d_entry.get('part') != 0 or d_entry.get('direct_update_allowed') is not True:
        raise SystemExit(f'unexpected D manifest mapping: {d_entry}')
    if sha256(D_PATH) != d_entry.get('sha256'):
        raise SystemExit('D.json hash drift vs manifest.v2')

    d = json.loads(D_PATH.read_text(encoding='utf-8'))
    risk = d.get('risk')
    if not isinstance(risk, dict):
        raise SystemExit('D.risk missing or not an object')

    vix_key = next((k for k in risk if str(k).upper() == 'VIX'), None)
    receipt = {
        'schema': 'GMFQ_VIX_RUNTIME_AUDIT_V1',
        'runtime_file': 'live_data/sections/D.json',
        'runtime_sha256': sha256(D_PATH),
        'manifest_status': manifest.get('status'),
        'manifest_mode': d_entry.get('mode'),
        'payload_part': d_entry.get('part'),
        'direct_update_allowed': d_entry.get('direct_update_allowed'),
        'risk_keys': sorted(risk.keys()),
        'vix_present': vix_key is not None,
        'vix_key': vix_key,
        'vix_summary': summarize_series(risk[vix_key]) if vix_key is not None else None,
        'risk_summary': {str(k): summarize_series(v) for k, v in risk.items()},
        'runtime_mutated': False,
        'publication_performed': False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
