#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, pathlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
PAYLOAD=ROOT/'payload'
SECTION=ROOT/'live_data'/'sections'/'OIS_DATA.json'
PARTS=[PAYLOAD/f'part-{i:02d}.txt' for i in range(16)]
MARKER_KEY='__gmfq_dry_run_marker'
MARKER_VALUE='LIVE_REFRESH_PIPELINE_TEST_2026-10-05'

def sha(b:bytes)->str: return hashlib.sha256(b).hexdigest()

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args()
    old_parts=[p.read_bytes() for p in PARTS]
    old_runtime=b''.join(old_parts)
    old_section=SECTION.read_bytes()
    count=old_runtime.count(old_section)
    if count!=1:
        raise SystemExit(f'OIS_DATA exact runtime occurrence must be 1, got {count}')
    data=json.loads(old_section.decode('utf-8'))
    if MARKER_KEY in data:
        raise SystemExit('dry-run marker already present')
    data[MARKER_KEY]=MARKER_VALUE
    new_section=json.dumps(data,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    start=old_runtime.find(old_section); end=start+len(old_section)
    new_runtime=old_runtime[:start]+new_section+old_runtime[end:]
    # Preserve 16-part loader contract. Keep first 15 byte lengths unchanged; tail absorbs delta.
    sizes=[len(x) for x in old_parts]
    new_parts=[]; pos=0
    for size in sizes[:-1]:
        new_parts.append(new_runtime[pos:pos+size]); pos+=size
    new_parts.append(new_runtime[pos:])
    assert b''.join(new_parts)==new_runtime
    delta=len(new_runtime)-len(old_runtime)
    summary={
      'status':'PASS','section':'OIS_DATA','marker_key':MARKER_KEY,
      'old_section_sha256':sha(old_section),'new_section_sha256':sha(new_section),
      'old_runtime_sha256':sha(old_runtime),'new_runtime_sha256':sha(new_runtime),
      'runtime_byte_delta':delta,'parts':16,
      'semantic_fields_changed':False,
      'production_publish':False
    }
    if args.apply:
        SECTION.write_bytes(new_section)
        for p,b in zip(PARTS,new_parts): p.write_bytes(b)
        # Strong postconditions.
        check=b''.join(p.read_bytes() for p in PARTS)
        if check!=new_runtime: raise SystemExit('post-write runtime mismatch')
        parsed=json.loads(SECTION.read_text())
        if parsed.get(MARKER_KEY)!=MARKER_VALUE: raise SystemExit('marker write failed')
    print(json.dumps(summary,indent=2))
    return 0

if __name__=='__main__': sys.exit(main())
