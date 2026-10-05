#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, pathlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
PAYLOAD=ROOT/'payload'
SECTIONS=ROOT/'live_data'/'sections'
OLD=ROOT/'live_data'/'manifest.json'
PARTS=[PAYLOAD/f'part-{i:02d}.txt' for i in range(16)]
TRANSFORMED={'V247_COT_STORIES','RATES_AUDIT_METADATA'}

def sha(b:bytes)->str: return hashlib.sha256(b).hexdigest()

def main()->int:
    old=json.loads(OLD.read_text())
    part_bytes=[p.read_bytes() for p in PARTS]
    runtime=b''.join(part_bytes)
    rows=[]; failures=[]
    for entry in old.get('sections',[]):
        key=entry['key']; file=entry['file']; raw=(SECTIONS/file).read_bytes()
        hits=[i for i,b in enumerate(part_bytes) if b.count(raw)]
        total=sum(b.count(raw) for b in part_bytes)
        mode='DERIVED_BUILDER_REQUIRED' if key in TRANSFORMED else 'DIRECT_SINGLE_PART'
        row={'key':key,'file':file,'mode':mode,'bytes':len(raw),'sha256':sha(raw),'occurrences_in_payload':total,'part':hits[0] if len(hits)==1 and total==1 else None}
        if mode=='DIRECT_SINGLE_PART' and (total!=1 or len(hits)!=1):
            failures.append(f'{key}: direct section must occur exactly once inside one payload part; total={total}, parts={hits}')
        if mode=='DERIVED_BUILDER_REQUIRED':
            row['direct_update_allowed']=False
        else:
            row['direct_update_allowed']=True
        rows.append(row)
    manifest={
      'schema':'GMFQ_LIVE_DATA_MANIFEST_V2',
      'generated_from_current_payload':True,
      'runtime_sha256':sha(runtime),
      'runtime_bytes':len(runtime),
      'part_count':len(PARTS),
      'direct_section_count':sum(r['mode']=='DIRECT_SINGLE_PART' for r in rows),
      'derived_section_count':sum(r['mode']=='DERIVED_BUILDER_REQUIRED' for r in rows),
      'sections':rows,
      'failures':failures,
      'status':'PASS' if not failures else 'FAIL'
    }
    print(json.dumps(manifest,indent=2,ensure_ascii=False))
    return 0 if not failures else 2

if __name__=='__main__': sys.exit(main())
