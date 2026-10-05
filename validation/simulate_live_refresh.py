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
    holders=[i for i,b in enumerate(old_parts) if b.count(old_section)]
    total=sum(b.count(old_section) for b in old_parts)
    if total!=1 or len(holders)!=1:
        raise SystemExit(f'OIS_DATA must occur exactly once wholly inside one payload part; total={total}, holders={holders}')
    holder=holders[0]
    data=json.loads(old_section.decode('utf-8'))
    if MARKER_KEY in data:
        raise SystemExit('dry-run marker already present')
    data[MARKER_KEY]=MARKER_VALUE
    new_section=json.dumps(data,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    new_parts=list(old_parts)
    new_parts[holder]=old_parts[holder].replace(old_section,new_section,1)
    new_runtime=b''.join(new_parts)
    expected_runtime=old_runtime.replace(old_section,new_section,1)
    if new_runtime!=expected_runtime:
        raise SystemExit('single-part propagation did not reproduce expected runtime')
    unchanged=[i for i,(a,b) in enumerate(zip(old_parts,new_parts)) if a==b]
    changed=[i for i,(a,b) in enumerate(zip(old_parts,new_parts)) if a!=b]
    if changed!=[holder] or len(unchanged)!=15:
        raise SystemExit(f'non-minimal payload propagation: changed={changed}')
    delta=len(new_runtime)-len(old_runtime)
    summary={
      'status':'PASS','section':'OIS_DATA','marker_key':MARKER_KEY,
      'payload_part':f'part-{holder:02d}.txt','changed_payload_parts':[f'part-{i:02d}.txt' for i in changed],
      'unchanged_payload_parts':15,
      'old_section_sha256':sha(old_section),'new_section_sha256':sha(new_section),
      'old_runtime_sha256':sha(old_runtime),'new_runtime_sha256':sha(new_runtime),
      'runtime_byte_delta':delta,'parts':16,
      'semantic_fields_changed':False,
      'production_publish':False
    }
    if args.apply:
        SECTION.write_bytes(new_section)
        PARTS[holder].write_bytes(new_parts[holder])
        check=b''.join(p.read_bytes() for p in PARTS)
        if check!=new_runtime: raise SystemExit('post-write runtime mismatch')
        for i,p in enumerate(PARTS):
            if i!=holder and p.read_bytes()!=old_parts[i]:
                raise SystemExit(f'unexpected mutation outside holder: {p.name}')
        parsed=json.loads(SECTION.read_text())
        if parsed.get(MARKER_KEY)!=MARKER_VALUE: raise SystemExit('marker write failed')
    print(json.dumps(summary,indent=2))
    return 0

if __name__=='__main__': sys.exit(main())
