#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'payload'
SECTIONS = ROOT / 'live_data' / 'sections'
MANIFEST = ROOT / 'live_data' / 'manifest.v2.json'
PARTS = [PAYLOAD / f'part-{i:02d}.txt' for i in range(16)]


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_runtime() -> tuple[bytes, list[bytes]]:
    missing = [str(p.relative_to(ROOT)) for p in PARTS if not p.is_file()]
    if missing:
        raise SystemExit('Missing payload parts: ' + ', '.join(missing))
    part_bytes = [p.read_bytes() for p in PARTS]
    return b''.join(part_bytes), part_bytes


def verify_sections(manifest: dict, runtime: bytes, part_bytes: list[bytes]) -> list[dict]:
    rows = []
    sections = manifest.get('sections') or []
    if len(sections) != 14:
        raise SystemExit(f'Expected 14 manifest sections, got {len(sections)}')

    for spec in sections:
        name = spec.get('file')
        mode = spec.get('mode')
        path = SECTIONS / str(name)
        if not path.is_file():
            raise SystemExit(f'Missing section file: {name}')
        raw = path.read_bytes()
        if len(raw) != spec.get('bytes'):
            raise SystemExit(f'{name}: section byte drift')
        if sha256(raw) != spec.get('sha256'):
            raise SystemExit(f'{name}: section sha drift')

        if mode == 'DIRECT_SINGLE_PART':
            part = spec.get('part')
            if not isinstance(part, int) or not (0 <= part < len(part_bytes)):
                raise SystemExit(f'{name}: invalid declared part {part}')
            runtime_count = runtime.count(raw)
            declared_part_count = part_bytes[part].count(raw)
            if runtime_count != 1 or declared_part_count != 1:
                raise SystemExit(
                    f'{name}: direct occurrence drift runtime={runtime_count} part={declared_part_count}'
                )
            if spec.get('occurrences_in_payload') != 1 or spec.get('direct_update_allowed') is not True:
                raise SystemExit(f'{name}: direct contract metadata drift')
            rows.append({'file': name, 'mode': mode, 'status': 'VERIFIED', 'part': part})
        elif mode == 'DERIVED_BUILDER_REQUIRED':
            if spec.get('part') is not None:
                raise SystemExit(f'{name}: derived section must not declare a direct part')
            if spec.get('occurrences_in_payload') != 0 or spec.get('direct_update_allowed') is not False:
                raise SystemExit(f'{name}: derived contract metadata drift')
            rows.append({'file': name, 'mode': mode, 'status': 'VERIFIED'})
        else:
            raise SystemExit(f'{name}: unsupported manifest mode {mode}')
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if manifest.get('schema') != 'GMFQ_LIVE_DATA_MANIFEST_V2':
        raise SystemExit('Invalid manifest V2 schema')
    if manifest.get('part_count') != 16:
        raise SystemExit('Manifest part_count must remain 16')
    if manifest.get('direct_section_count') != 12 or manifest.get('derived_section_count') != 2:
        raise SystemExit('Manifest section-count contract drift')

    runtime, part_bytes = load_runtime()
    verified = verify_sections(manifest, runtime, part_bytes)
    new_sha = sha256(runtime)
    new_bytes = len(runtime)
    old_sha = manifest.get('runtime_sha256')
    old_bytes = manifest.get('runtime_bytes')
    changed = old_sha != new_sha or old_bytes != new_bytes

    out = dict(manifest)
    out['runtime_sha256'] = new_sha
    out['runtime_bytes'] = new_bytes
    out['generated_from_current_payload'] = True
    out['failures'] = []
    out['status'] = 'PASS'

    if args.apply and changed:
        MANIFEST.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    receipt = {
        'schema': 'GMFQ_LIVE_DATA_MANIFEST_V2_REFRESH_RECEIPT_V1',
        'status': 'UPDATE_AVAILABLE' if changed else 'NO_CHANGE',
        'applied': bool(args.apply and changed),
        'old_runtime_sha256': old_sha,
        'new_runtime_sha256': new_sha,
        'old_runtime_bytes': old_bytes,
        'new_runtime_bytes': new_bytes,
        'sections_verified': len(verified),
        'direct_verified': sum(1 for x in verified if x['mode'] == 'DIRECT_SINGLE_PART'),
        'derived_verified': sum(1 for x in verified if x['mode'] == 'DERIVED_BUILDER_REQUIRED'),
        'policy': 'Verify all 14 section contracts first; update only global runtime sha/bytes.'
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
