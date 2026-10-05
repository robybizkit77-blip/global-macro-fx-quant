#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, pathlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
PAYLOAD=ROOT/'payload'
SECTIONS=ROOT/'live_data'/'sections'
MANIFEST=ROOT/'live_data'/'manifest.v2.json'
PARTS=[PAYLOAD/f'part-{i:02d}.txt' for i in range(16)]

def sha(b:bytes)->str: return hashlib.sha256(b).hexdigest()

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--section',required=True)
    ap.add_argument('--replacement',required=True,help='Path to validated replacement JSON')
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args()

    manifest=json.loads(MANIFEST.read_text())
    if manifest.get('schema')!='GMFQ_LIVE_DATA_MANIFEST_V2' or manifest.get('status')!='PASS':
        raise SystemExit('Canonical manifest v2 is not valid/PASS')
    entries={x['key']:x for x in manifest.get('sections',[])}
    if args.section not in entries: raise SystemExit('Unknown section: '+args.section)
    entry=entries[args.section]
    if entry.get('mode')!='DIRECT_SINGLE_PART' or entry.get('direct_update_allowed') is not True:
        raise SystemExit('Derived section requires dedicated builder: '+args.section)

    section_path=SECTIONS/entry['file']
    old=section_path.read_bytes()
    if sha(old)!=entry.get('sha256'):
        raise SystemExit(f'Section hash drift vs manifest v2: {args.section}')

    replacement_path=pathlib.Path(args.replacement)
    new=replacement_path.read_bytes()
    try: json.loads(new.decode('utf-8'))
    except Exception as e: raise SystemExit(f'Replacement is not valid JSON: {e}')

    expected_part=entry.get('part')
    if not isinstance(expected_part,int) or expected_part<0 or expected_part>=len(PARTS):
        raise SystemExit('Invalid part mapping in manifest v2')

    hits=[]
    for i,p in enumerate(PARTS):
        raw=p.read_bytes(); c=raw.count(old)
        if c: hits.append((i,c))
    if hits!=[(expected_part,1)]:
        raise SystemExit(f'Runtime mapping drift vs manifest v2; expected part {expected_part}, hits={hits}')

    part=PARTS[expected_part]; raw=part.read_bytes()
    updated=raw.replace(old,new,1)
    if updated==raw: raise SystemExit('No payload change produced')
    if updated.count(new)!=1: raise SystemExit('Replacement verification failed')

    summary={
      'status':'PASS','section':args.section,'part':expected_part,
      'manifest_schema':manifest['schema'],
      'old_section_sha256':sha(old),'new_section_sha256':sha(new),
      'old_part_sha256':sha(raw),'new_part_sha256':sha(updated),
      'byte_delta':len(updated)-len(raw),'changed_payload_parts':[expected_part],
      'derived_builder_used':False
    }
    if args.apply:
        section_path.write_bytes(new)
        part.write_bytes(updated)
        summary['applied']=True
        summary['untouched_payload_parts']=[i for i in range(len(PARTS)) if i!=expected_part]
    else:
        summary['applied']=False
    print(json.dumps(summary,indent=2))
    return 0

if __name__=='__main__': sys.exit(main())
