#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
PAYLOAD=ROOT/'payload'
SECTIONS=ROOT/'live_data'/'sections'
MANIFEST=ROOT/'live_data'/'manifest.v2.json'
PROV_ROOT=ROOT/'live_data'/'provenance'/'cert53'
PARTS=[PAYLOAD/f'part-{i:02d}.txt' for i in range(16)]

def sha(b:bytes)->str: return hashlib.sha256(b).hexdigest()

def validate_cert53_provenance(path:pathlib.Path,candidate_sha:str)->dict:
    try:
        p=json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        raise SystemExit(f'CERT53 provenance is not valid JSON: {e}')
    if p.get('schema')!='GMFQ_CERT53_REFRESH_PROVENANCE_V1':
        raise SystemExit('CERT53 provenance schema mismatch')
    if p.get('status')=='TEMPLATE_NOT_A_REFRESH_RECORD':
        raise SystemExit('CERT53 provenance template cannot be used as a refresh record')
    if p.get('section')!='CERT53':
        raise SystemExit('CERT53 provenance section mismatch')
    rid=p.get('refresh_id')
    if not isinstance(rid,str) or not re.fullmatch(r'[A-Za-z0-9._:-]{8,128}',rid):
        raise SystemExit('CERT53 provenance refresh_id missing/invalid')
    if not p.get('created_at_utc') or not p.get('source_asof'):
        raise SystemExit('CERT53 provenance requires created_at_utc and source_asof')
    if p.get('candidate_sha256')!=candidate_sha:
        raise SystemExit('CERT53 provenance candidate_sha256 does not match replacement bytes')
    inputs=p.get('inputs')
    if not isinstance(inputs,list) or not inputs:
        raise SystemExit('CERT53 provenance requires at least one canonical input')
    for i,row in enumerate(inputs):
        if not isinstance(row,dict) or not row.get('path') or not row.get('role'):
            raise SystemExit(f'CERT53 provenance input {i} incomplete')
        h=row.get('sha256')
        if not isinstance(h,str) or not re.fullmatch(r'[0-9a-f]{64}',h):
            raise SystemExit(f'CERT53 provenance input {i} sha256 invalid')
    v=p.get('validation') or {}
    required=('candidate_schema_valid','pair_count_28','source_metadata_checked','manual_review_required')
    if any(v.get(k) is not True for k in required):
        raise SystemExit('CERT53 provenance validation flags must all be true')
    g=p.get('guards') or {}
    if g.get('changes_engine_rules') is not False or g.get('changes_oos_baseline') is not False or g.get('production_promotion') is not False:
        raise SystemExit('CERT53 provenance guards invalid')
    return p

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--section',required=True)
    ap.add_argument('--replacement',required=True,help='Path to validated replacement JSON')
    ap.add_argument('--provenance',help='Required on --apply for CERT53: GMFQ_CERT53_REFRESH_PROVENANCE_V1 JSON')
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
    try: parsed=json.loads(new.decode('utf-8'))
    except Exception as e: raise SystemExit(f'Replacement is not valid JSON: {e}')
    if args.section=='CERT53':
        if len((parsed or {}).get('pairs',{}))!=28:
            raise SystemExit('CERT53 replacement must contain exactly 28 pairs')
        if args.apply and not args.provenance:
            raise SystemExit('CERT53 --apply requires --provenance; untraceable refresh refused')

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

    provenance=None; provenance_target=None
    if args.section=='CERT53' and args.provenance:
        provenance=validate_cert53_provenance(pathlib.Path(args.provenance),sha(new))
        provenance_target=PROV_ROOT/f"{provenance['refresh_id']}.json"
        if provenance_target.exists():
            raise SystemExit(f'CERT53 provenance refresh_id already exists: {provenance_target}')

    summary={
      'status':'PASS','section':args.section,'part':expected_part,
      'manifest_schema':manifest['schema'],
      'old_section_sha256':sha(old),'new_section_sha256':sha(new),
      'old_part_sha256':sha(raw),'new_part_sha256':sha(updated),
      'byte_delta':len(updated)-len(raw),'changed_payload_parts':[expected_part],
      'derived_builder_used':False,
      'provenance_required': args.section=='CERT53',
      'provenance_validated': provenance is not None
    }
    if provenance:
        summary['refresh_id']=provenance['refresh_id']
        summary['source_asof']=provenance['source_asof']
        summary['provenance_record']=str(provenance_target.relative_to(ROOT))
    if args.apply:
        section_path.write_bytes(new)
        part.write_bytes(updated)
        if provenance:
            PROV_ROOT.mkdir(parents=True,exist_ok=True)
            provenance_target.write_text(json.dumps(provenance,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        summary['applied']=True
        summary['untouched_payload_parts']=[i for i in range(len(PARTS)) if i!=expected_part]
    else:
        summary['applied']=False
    print(json.dumps(summary,indent=2))
    return 0

if __name__=='__main__': sys.exit(main())
