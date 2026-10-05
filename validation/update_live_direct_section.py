#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, pathlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
PAYLOAD=ROOT/'payload'
SECTIONS=ROOT/'live_data'/'sections'
OLD_MANIFEST=ROOT/'live_data'/'manifest.json'
PARTS=[PAYLOAD/f'part-{i:02d}.txt' for i in range(16)]
TRANSFORMED={'V247_COT_STORIES','RATES_AUDIT_METADATA'}

def sha(b:bytes)->str: return hashlib.sha256(b).hexdigest()

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--section',required=True)
    ap.add_argument('--replacement',required=True,help='Path to validated replacement JSON')
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args()

    manifest=json.loads(OLD_MANIFEST.read_text())
    entries={x['key']:x for x in manifest.get('sections',[])}
    if args.section not in entries: raise SystemExit('Unknown section: '+args.section)
    if args.section in TRANSFORMED: raise SystemExit('Derived section requires dedicated builder: '+args.section)

    entry=entries[args.section]
    section_path=SECTIONS/entry['file']
    old=section_path.read_bytes()
    replacement_path=pathlib.Path(args.replacement)
    new=replacement_path.read_bytes()
    try: json.loads(new.decode('utf-8'))
    except Exception as e: raise SystemExit(f'Replacement is not valid JSON: {e}')

    hits=[]
    for i,p in enumerate(PARTS):
        raw=p.read_bytes(); c=raw.count(old)
        if c: hits.append((i,c))
    if len(hits)!=1 or hits[0][1]!=1:
        raise SystemExit(f'Current section must occur exactly once inside one part; hits={hits}')
    idx=hits[0][0]
    part=PARTS[idx]; raw=part.read_bytes()
    updated=raw.replace(old,new,1)
    if updated==raw: raise SystemExit('No payload change produced')
    if updated.count(new)!=1: raise SystemExit('Replacement verification failed')

    summary={
      'status':'PASS','section':args.section,'part':idx,
      'old_section_sha256':sha(old),'new_section_sha256':sha(new),
      'old_part_sha256':sha(raw),'new_part_sha256':sha(updated),
      'byte_delta':len(updated)-len(raw),'changed_payload_parts':[idx],
      'derived_builder_used':False
    }
    if args.apply:
        section_path.write_bytes(new)
        part.write_bytes(updated)
        untouched=[]
        for i,p in enumerate(PARTS):
            if i!=idx: untouched.append(i)
        summary['applied']=True
        summary['untouched_payload_parts']=untouched
    else:
        summary['applied']=False
    print(json.dumps(summary,indent=2))
    return 0

if __name__=='__main__': sys.exit(main())
