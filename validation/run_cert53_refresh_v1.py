#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, pathlib, subprocess, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
UPDATER=ROOT/'validation'/'update_live_direct_section.py'
MANIFEST_BUILDER=ROOT/'validation'/'build_live_manifest_v2.py'
CONTRACT=ROOT/'validation'/'check_live_update_contract.py'
CERT53=ROOT/'live_data'/'sections'/'CERT53.json'
MANIFEST=ROOT/'live_data'/'manifest.v2.json'
PART=ROOT/'payload'/'part-00.txt'
PROV_DIR=ROOT/'live_data'/'provenance'/'cert53'


def sha_bytes(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def sha_path(p:pathlib.Path)->str: return sha_bytes(p.read_bytes())

def run_json(cmd:list[str])->dict:
    cp=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
    if cp.returncode!=0:
        raise RuntimeError((cp.stderr or cp.stdout or 'command failed').strip())
    try: return json.loads(cp.stdout)
    except Exception as e: raise RuntimeError(f'non-JSON command output: {e}: {cp.stdout[:500]}')

def validate_inputs(candidate:pathlib.Path, provenance:pathlib.Path)->tuple[dict,dict]:
    c=json.loads(candidate.read_text(encoding='utf-8'))
    p=json.loads(provenance.read_text(encoding='utf-8'))
    if len((c or {}).get('pairs',{}))!=28: raise SystemExit('CERT53 candidate must contain exactly 28 pairs')
    if p.get('schema')!='GMFQ_CERT53_REFRESH_PROVENANCE_V1': raise SystemExit('provenance schema mismatch')
    if p.get('status')=='TEMPLATE_NOT_A_REFRESH_RECORD': raise SystemExit('template is not a refresh record')
    if p.get('section')!='CERT53': raise SystemExit('provenance section mismatch')
    if p.get('candidate_sha256')!=sha_path(candidate): raise SystemExit('candidate sha mismatch in provenance')
    rid=p.get('refresh_id')
    if not rid: raise SystemExit('refresh_id missing')
    return c,p

def build_manifest()->dict:
    cp=subprocess.run([sys.executable,str(MANIFEST_BUILDER)],cwd=ROOT,text=True,capture_output=True)
    if cp.returncode!=0: raise RuntimeError(cp.stderr or cp.stdout or 'manifest builder failed')
    m=json.loads(cp.stdout)
    if m.get('status')!='PASS': raise RuntimeError('rebuilt manifest is not PASS')
    return m

def verify_cert53_manifest(m:dict, candidate_sha:str)->dict:
    rows=[r for r in m.get('sections',[]) if r.get('key')=='CERT53']
    if len(rows)!=1: raise RuntimeError('manifest must contain exactly one CERT53 row')
    r=rows[0]
    checks={
      'candidate_sha_matches_manifest': r.get('sha256')==candidate_sha,
      'part_is_0': r.get('part')==0,
      'occurs_once': r.get('occurrences_in_payload')==1,
      'direct_update_allowed': r.get('direct_update_allowed') is True,
      'mode_direct_single_part': r.get('mode')=='DIRECT_SINGLE_PART'
    }
    if not all(checks.values()): raise RuntimeError('CERT53 manifest verification failed: '+json.dumps(checks))
    return checks

def main()->int:
    ap=argparse.ArgumentParser(description='Canonical manual CERT53 refresh path. Default is read-only preflight.')
    ap.add_argument('--candidate',required=True)
    ap.add_argument('--provenance',required=True)
    ap.add_argument('--apply',action='store_true')
    ap.add_argument('--confirm-refresh-id',help='Required with --apply and must exactly match provenance refresh_id')
    a=ap.parse_args()
    candidate=pathlib.Path(a.candidate); provenance=pathlib.Path(a.provenance)
    _,prov=validate_inputs(candidate,provenance)
    rid=prov['refresh_id']; candidate_sha=sha_path(candidate)
    if a.apply and a.confirm_refresh_id!=rid:
        raise SystemExit('--apply requires --confirm-refresh-id exactly matching provenance refresh_id')

    before={
      'cert53':CERT53.read_bytes(),
      'part':PART.read_bytes(),
      'manifest':MANIFEST.read_bytes(),
    }
    before_hashes={k:sha_bytes(v) for k,v in before.items()}
    prov_target=PROV_DIR/f'{rid}.json'
    if prov_target.exists(): raise SystemExit(f'provenance refresh_id already exists: {rid}')

    preflight=run_json([sys.executable,str(UPDATER),'--section','CERT53','--replacement',str(candidate),'--provenance',str(provenance)])
    if preflight.get('status')!='PASS' or preflight.get('applied') is not False or preflight.get('provenance_validated') is not True:
        raise SystemExit('CERT53 updater preflight did not pass')

    result={
      'schema':'GMFQ_CERT53_CANONICAL_REFRESH_V1',
      'status':'PREFLIGHT_PASS',
      'mode':'APPLY' if a.apply else 'PREFLIGHT_ONLY',
      'refresh_id':rid,
      'candidate_sha256':candidate_sha,
      'source_asof':prov.get('source_asof'),
      'preflight':preflight,
      'before_sha256':before_hashes,
      'guards':{
        'manual_only':True,
        'explicit_apply_required':True,
        'confirm_refresh_id_required':True,
        'rollback_on_post_apply_failure':True,
        'changes_engine_rules':False,
        'changes_oos_baseline':False,
        'production_promotion':False
      }
    }
    if not a.apply:
        result['live_data_changed']=False
        print(json.dumps(result,indent=2,ensure_ascii=False)); return 0

    try:
        applied=run_json([sys.executable,str(UPDATER),'--section','CERT53','--replacement',str(candidate),'--provenance',str(provenance),'--apply'])
        if applied.get('applied') is not True or applied.get('refresh_id')!=rid:
            raise RuntimeError('updater apply result invalid')
        if sha_path(CERT53)!=candidate_sha: raise RuntimeError('CERT53 bytes do not match candidate after apply')
        if not prov_target.exists(): raise RuntimeError('provenance record missing after apply')
        saved_prov=json.loads(prov_target.read_text(encoding='utf-8'))
        if saved_prov.get('refresh_id')!=rid or saved_prov.get('candidate_sha256')!=candidate_sha:
            raise RuntimeError('saved provenance record mismatch')

        new_manifest=build_manifest()
        manifest_checks=verify_cert53_manifest(new_manifest,candidate_sha)
        MANIFEST.write_text(json.dumps(new_manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        contract=run_json([sys.executable,str(CONTRACT)])
        if contract.get('status')!='PASS': raise RuntimeError('live update contract failed after apply')

        result.update({
          'status':'APPLIED_AND_VERIFIED',
          'live_data_changed':True,
          'updater_apply':applied,
          'manifest_checks':manifest_checks,
          'contract_status':contract.get('status'),
          'after_sha256':{
            'cert53':sha_path(CERT53),'part':sha_path(PART),'manifest':sha_path(MANIFEST),
            'provenance_record':sha_path(prov_target)
          }
        })
        print(json.dumps(result,indent=2,ensure_ascii=False)); return 0
    except Exception as e:
        CERT53.write_bytes(before['cert53'])
        PART.write_bytes(before['part'])
        MANIFEST.write_bytes(before['manifest'])
        if prov_target.exists(): prov_target.unlink()
        rollback_ok=(sha_path(CERT53)==before_hashes['cert53'] and sha_path(PART)==before_hashes['part'] and sha_path(MANIFEST)==before_hashes['manifest'] and not prov_target.exists())
        print(json.dumps({
          **result,
          'status':'ROLLED_BACK_AFTER_FAILURE' if rollback_ok else 'ROLLBACK_FAILURE',
          'live_data_changed':False if rollback_ok else None,
          'error':str(e),
          'rollback_verified':rollback_ok
        },indent=2,ensure_ascii=False))
        return 2

if __name__=='__main__': sys.exit(main())
