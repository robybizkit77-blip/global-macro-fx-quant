#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'live_data' / 'manifest.v2.json'
LEGACY_MANIFEST = ROOT / 'live_data' / 'manifest.json'
T0 = ROOT / 'validation' / 'CANONICAL_ENGINE_OOS_T0_V3_2026-10-01.json'
SECTIONS_DIR = ROOT / 'live_data' / 'sections'
PAYLOAD_DIR = ROOT / 'payload'
EXPECTED_FP = '3356baf0'
EXPECTED_MODEL = '9.3-pair-attention-hierarchy'
EXPECTED_PARTS = [PAYLOAD_DIR / f'part-{i:02d}.txt' for i in range(16)]
DERIVED = {'V247_COT_STORIES', 'RATES_AUDIT_METADATA'}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    failures=[]
    details={}
    if not MANIFEST.exists():
        print(json.dumps({'status':'FAIL','failures':['missing manifest.v2.json']},indent=2)); return 2
    manifest=json.loads(MANIFEST.read_text())
    details['manifest_schema']=manifest.get('schema')
    details['legacy_manifest_retained']=LEGACY_MANIFEST.exists()
    details['legacy_manifest_role']='historical extraction/roundtrip metadata only; not live-refresh contract'
    if manifest.get('schema')!='GMFQ_LIVE_DATA_MANIFEST_V2':
        failures.append('manifest v2 schema mismatch')
    if manifest.get('status')!='PASS':
        failures.append('manifest v2 status is not PASS')
    if manifest.get('generated_from_current_payload') is not True:
        failures.append('manifest v2 not generated from current payload')

    parts=[]
    for p in EXPECTED_PARTS:
        if not p.exists() or p.stat().st_size<=0:
            failures.append(f'missing/empty payload {p.name}')
            continue
        parts.append(p.read_bytes())
    if manifest.get('part_count')!=16 or len(parts)!=16:
        failures.append('payload part count mismatch')
    runtime=b''.join(parts)
    actual_runtime_sha=sha256_bytes(runtime)
    details['runtime_sha256']=actual_runtime_sha
    details['runtime_bytes']=len(runtime)
    if manifest.get('runtime_sha256')!=actual_runtime_sha:
        failures.append('runtime sha256 mismatch')
    if manifest.get('runtime_bytes')!=len(runtime):
        failures.append('runtime byte-size mismatch')

    sections=manifest.get('sections') or []
    keys=[s.get('key') for s in sections]
    if len(keys)!=len(set(keys)):
        failures.append('duplicate section keys')
    section_results=[]
    direct_count=0; derived_count=0
    for s in sections:
        key=s.get('key'); name=s.get('file'); mode=s.get('mode')
        p=SECTIONS_DIR/name if name else None
        row={'key':key,'file':name,'mode':mode,'exists':bool(p and p.exists())}
        if not p or not p.exists():
            failures.append(f'missing section {name}')
            section_results.append(row); continue
        raw=p.read_bytes()
        row['actual_bytes']=len(raw)
        row['actual_sha256']=sha256_bytes(raw)
        row['hash_match']=s.get('sha256')==row['actual_sha256']
        row['bytes_match']=s.get('bytes')==len(raw)
        try:
            json.loads(raw.decode('utf-8')); row['json_valid']=True
        except Exception:
            row['json_valid']=False; failures.append(f'invalid json {name}')
        if not row['hash_match']: failures.append(f'hash mismatch {name}')
        if not row['bytes_match']: failures.append(f'byte-size mismatch {name}')

        if key in DERIVED:
            derived_count+=1
            if mode!='DERIVED_BUILDER_REQUIRED': failures.append(f'{key}: derived mode mismatch')
            if s.get('direct_update_allowed') is not False: failures.append(f'{key}: direct update must be false')
        else:
            direct_count+=1
            if mode!='DIRECT_SINGLE_PART': failures.append(f'{key}: direct mode mismatch')
            if s.get('direct_update_allowed') is not True: failures.append(f'{key}: direct update must be true')
            if s.get('occurrences_in_payload')!=1 or not isinstance(s.get('part'),int):
                failures.append(f'{key}: direct section must occur exactly once in one payload part')
        section_results.append(row)
    details['sections']=section_results
    if manifest.get('direct_section_count')!=direct_count:
        failures.append('direct section count mismatch')
    if manifest.get('derived_section_count')!=derived_count:
        failures.append('derived section count mismatch')
    if derived_count!=2:
        failures.append('expected exactly two derived sections')

    if not T0.exists():
        failures.append('canonical OOS T0 missing')
    else:
        t0=json.loads(T0.read_text())
        details['frozen_model_rules_version']=t0.get('model_rules_version')
        details['frozen_rules_fingerprint']=t0.get('rules_fingerprint')
        details['oos_rule']=t0.get('oos_rule')
        if t0.get('model_rules_version')!=EXPECTED_MODEL:
            failures.append('frozen model version mismatch')
        if t0.get('rules_fingerprint')!=EXPECTED_FP:
            failures.append('frozen rules fingerprint mismatch')
        if t0.get('oos_rule')!='ANY_RULE_CHANGE_RESTARTS_OUT_OF_SAMPLE':
            failures.append('OOS rule mismatch')

    status='PASS' if not failures else 'FAIL'
    print(json.dumps({'status':status,'failures':failures,'details':details},indent=2))
    return 0 if not failures else 2

if __name__=='__main__':
    sys.exit(main())
