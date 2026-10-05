#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, pathlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
PAYLOAD=ROOT/'payload'
SECTIONS=ROOT/'live_data'/'sections'
OLD_MANIFEST=ROOT/'live_data'/'manifest.json'
PARTS=[PAYLOAD/f'part-{i:02d}.txt' for i in range(16)]


def sha(b:bytes)->str: return hashlib.sha256(b).hexdigest()

def load_runtime()->bytes:
    missing=[str(p) for p in PARTS if not p.exists()]
    if missing: raise SystemExit('Missing payload parts: '+', '.join(missing))
    return b''.join(p.read_bytes() for p in PARTS)

def build_snapshot():
    runtime=load_runtime()
    old=json.loads(OLD_MANIFEST.read_text())
    section_rows=[]
    failures=[]
    for s in old.get('sections',[]):
        name=s.get('file'); key=s.get('key'); p=SECTIONS/name
        if not p.exists():
            failures.append(f'missing section {name}'); continue
        raw=p.read_bytes()
        first=runtime.find(raw)
        count=runtime.count(raw)
        row={'key':key,'file':name,'bytes':len(raw),'sha256':sha(raw),'occurrences_in_runtime':count,'literal_start_byte':first if first>=0 else None,'literal_end_byte':first+len(raw) if first>=0 else None}
        section_rows.append(row)
        if count!=1:
            failures.append(f'{name}: expected exactly one exact occurrence in current runtime, found {count}')
    part_rows=[]
    offset=0
    for p in PARTS:
        raw=p.read_bytes(); text=raw.decode('utf-8')
        part_rows.append({'file':str(p.relative_to(ROOT)),'chars':len(text),'bytes':len(raw),'sha256':sha(raw),'runtime_start_byte':offset,'runtime_end_byte':offset+len(raw)})
        offset+=len(raw)
    snapshot={'schema':'GMFQ_LIVE_DATA_RUNTIME_SNAPSHOT_V2','generated_from_current_payload':True,'runtime_bytes':len(runtime),'runtime_sha256':sha(runtime),'sections':section_rows,'parts':part_rows,'roundtrip_method':'content-addressed exact-byte section discovery','failures':failures,'status':'PASS' if not failures else 'FAIL'}
    return snapshot,runtime

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--write-snapshot')
    ap.add_argument('--verify-only',action='store_true')
    a=ap.parse_args()
    snapshot,runtime=build_snapshot()
    # A no-op replacement of every uniquely found section must preserve runtime byte-for-byte.
    rebuilt=runtime
    for s in snapshot['sections']:
        if s['occurrences_in_runtime']==1:
            p=SECTIONS/s['file']; raw=p.read_bytes(); start=s['literal_start_byte']; end=s['literal_end_byte']
            rebuilt=rebuilt[:start]+raw+rebuilt[end:]
    snapshot['noop_roundtrip_sha256']=sha(rebuilt)
    snapshot['noop_roundtrip_byte_identical']=rebuilt==runtime
    if not snapshot['noop_roundtrip_byte_identical']:
        snapshot['failures'].append('no-op roundtrip changed runtime bytes')
        snapshot['status']='FAIL'
    if a.write_snapshot:
        pathlib.Path(a.write_snapshot).write_text(json.dumps(snapshot,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(snapshot,indent=2,ensure_ascii=False))
    return 0 if snapshot['status']=='PASS' else 2

if __name__=='__main__': sys.exit(main())
