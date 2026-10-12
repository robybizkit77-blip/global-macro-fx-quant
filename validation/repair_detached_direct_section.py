#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'live_data' / 'manifest.v2.json'
SECTIONS = ROOT / 'live_data' / 'sections'
PARTS = [ROOT / 'payload' / f'part-{i:02d}.txt' for i in range(16)]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_bytes(commit: str, path: str) -> bytes:
    p = subprocess.run(
        ['git', 'show', f'{commit}:{path}'],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if p.returncode != 0:
        raise ValueError(f'cannot read {path} at {commit}')
    return p.stdout


def find_historical_exact(path: str, expected_sha: str) -> tuple[str, bytes]:
    p = subprocess.run(
        ['git', 'rev-list', '--all', '--', path],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    matches: list[tuple[str, bytes]] = []
    for commit in [x.strip() for x in p.stdout.splitlines() if x.strip()]:
        try:
            raw = git_bytes(commit, path)
        except ValueError:
            continue
        if sha(raw) == expected_sha:
            matches.append((commit, raw))
            if len(matches) > 1:
                # Same exact bytes in multiple commits is harmless; one anchor is enough.
                break
    if not matches:
        raise ValueError(f'no historical version of {path} matches manifest sha256={expected_sha}')
    return matches[0]


def main() -> int:
    ap = argparse.ArgumentParser(description='Repair a DIRECT_SINGLE_PART section whose section file advanced without payload/manifest apply.')
    ap.add_argument('--section', required=True)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if manifest.get('schema') != 'GMFQ_LIVE_DATA_MANIFEST_V2' or manifest.get('status') != 'PASS':
        raise SystemExit('tracked manifest is not canonical PASS')
    rows = {x['key']: x for x in manifest.get('sections', [])}
    if args.section not in rows:
        raise SystemExit('unknown section: ' + args.section)
    row = rows[args.section]
    if row.get('mode') != 'DIRECT_SINGLE_PART' or row.get('direct_update_allowed') is not True:
        raise SystemExit('section is not eligible for direct repair')

    rel = f"live_data/sections/{row['file']}"
    current_path = ROOT / rel
    current = current_path.read_bytes()
    current_sha = sha(current)
    expected_sha = row.get('sha256')
    if current_sha == expected_sha:
        raise SystemExit('section is not detached from manifest; use normal direct updater')

    commit, old = find_historical_exact(rel, expected_sha)
    expected_part = row.get('part')
    if not isinstance(expected_part, int) or not (0 <= expected_part < len(PARTS)):
        raise SystemExit('invalid manifest part mapping')

    hits: list[tuple[int, int]] = []
    for i, part in enumerate(PARTS):
        raw = part.read_bytes()
        count = raw.count(old)
        if count:
            hits.append((i, count))
    if hits != [(expected_part, 1)]:
        raise SystemExit(f'historical manifest-anchored bytes do not map exactly once to expected payload part: expected={(expected_part, 1)} hits={hits}')

    part = PARTS[expected_part]
    before = part.read_bytes()
    after = before.replace(old, current, 1)
    if after == before:
        raise SystemExit('repair produced no payload change')
    if after.count(current) != 1:
        raise SystemExit('current section does not occur exactly once after repair')

    result = {
        'schema': 'GMFQ_DETACHED_DIRECT_SECTION_REPAIR_V1',
        'status': 'PASS',
        'section': args.section,
        'section_file': rel,
        'historical_anchor_commit': commit,
        'manifest_old_sha256': expected_sha,
        'current_section_sha256': current_sha,
        'part': expected_part,
        'old_part_sha256': sha(before),
        'new_part_sha256': sha(after),
        'byte_delta': len(after) - len(before),
        'applied': bool(args.apply),
        'changed_files_if_applied': [str(part.relative_to(ROOT))],
    }
    if args.apply:
        part.write_bytes(after)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f'REPAIR_REJECTED: {exc}', file=sys.stderr)
        raise SystemExit(2)
