#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'live_data' / 'manifest.json'
SECTIONS_DIR = ROOT / 'live_data' / 'sections'
PAYLOAD_DIR = ROOT / 'payload'
EXPECTED_FP = '3356baf0'
EXPECTED_PARTS = [f'part-{i:02d}.txt' for i in range(16)]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    failures=[]
    details={}
    if not MANIFEST.exists():
        print(json.dumps({'status':'FAIL','failures':['missing manifest']},indent=2)); return 2
    manifest=json.loads(MANIFEST.read_text())
    details['manifest_schema']=manifest.get('schema')
    if manifest.get('schema')!='GMFQ_V490_LIVE_DATA_LAYER_V1':
        failures.append('manifest schema mismatch')

    sections=manifest.get('sections') or []
    keys=[s.get('key') for s in sections]
    if len(keys)!=len(set(keys)):
        failures.append('duplicate section keys')
    section_results=[]
    for s in sections:
        name=s.get('file'); expected=s.get('sha256'); key=s.get('key')
        p=SECTIONS_DIR/name if name else None
        row={'key':key,'file':name,'exists':bool(p and p.exists()),'hash_match':False,'json_valid':False}
        if not p or not p.exists():
            failures.append(f'missing section {name}')
            section_results.append(row); continue
        raw=p.read_bytes()
        actual=sha256_bytes(raw)
        row['hash_match']=(actual==expected)
        if expected and actual!=expected:
            failures.append(f'hash mismatch {name}')
        try:
            json.loads(raw.decode('utf-8'))
            row['json_valid']=True
        except Exception:
            failures.append(f'invalid json {name}')
        section_results.append(row)
    details['sections']=section_results

    payload_results=[]
    for name in EXPECTED_PARTS:
        p=PAYLOAD_DIR/name
        ok=p.exists() and p.stat().st_size>0
        payload_results.append({'file':name,'present_nonempty':ok})
        if not ok: failures.append(f'missing/empty payload {name}')
    details['payload_parts']=payload_results

    # Guard the frozen rules fingerprint wherever current workflows declare it.
    wf_dir=ROOT/'.github'/'workflows'
    fingerprint_mentions=[]
    for p in wf_dir.glob('*.yml'):
        txt=p.read_text(errors='replace')
        if EXPECTED_FP in txt:
            fingerprint_mentions.append(p.name)
    details['fingerprint_mentions']=fingerprint_mentions
    if not fingerprint_mentions:
        failures.append('rules fingerprint not guarded by any workflow')

    details['byte_identical_roundtrip']=manifest.get('byte_identical_roundtrip')
    if manifest.get('byte_identical_roundtrip') is not True:
        failures.append('manifest roundtrip not certified byte-identical')

    status='PASS' if not failures else 'FAIL'
    print(json.dumps({'status':status,'failures':failures,'details':details},indent=2))
    return 0 if not failures else 2

if __name__=='__main__':
    sys.exit(main())
