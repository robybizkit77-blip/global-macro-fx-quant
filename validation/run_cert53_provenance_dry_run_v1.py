#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
CERT53=ROOT/'live_data/sections/CERT53.json'
PART=ROOT/'payload/part-00.txt'
PROV_DIR=ROOT/'live_data/provenance/cert53'
UPDATER=ROOT/'validation/update_live_direct_section.py'
OUT=ROOT/'validation/CERT53_PROVENANCE_DRY_RUN_V1_2026-10-07.json'

def sha(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main()->int:
    before_cert=sha(CERT53)
    before_part=sha(PART)
    before_prov=sorted(str(p.relative_to(ROOT)) for p in PROV_DIR.glob('*.json')) if PROV_DIR.exists() else []

    current=json.loads(CERT53.read_text(encoding='utf-8'))
    assert len(current.get('pairs',{}))==28
    candidate=dict(current)
    candidate['_dry_run_probe']={
        'schema':'GMFQ_CERT53_PROVENANCE_DRY_RUN_MARKER_V1',
        'synthetic':True,
        'must_never_be_applied':True
    }

    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        candidate_path=td/'CERT53.candidate.json'
        provenance_path=td/'CERT53.provenance.json'
        candidate_path.write_text(json.dumps(candidate,separators=(',',':'),ensure_ascii=False)+'\n',encoding='utf-8')
        candidate_sha=sha(candidate_path)
        refresh_id='DRYRUN_CERT53_20261007_V1'
        provenance={
            'schema':'GMFQ_CERT53_REFRESH_PROVENANCE_V1',
            'status':'DRY_RUN_ONLY__NOT_APPLIED',
            'section':'CERT53',
            'refresh_id':refresh_id,
            'created_at_utc':datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
            'source_asof':'SYNTHETIC_DRY_RUN__NO_MARKET_DATA_CHANGE',
            'candidate_sha256':candidate_sha,
            'inputs':[{
                'path':'live_data/sections/CERT53.json',
                'sha256':before_cert,
                'role':'DRY_RUN_BASELINE_INPUT'
            }],
            'validation':{
                'candidate_schema_valid':True,
                'pair_count_28':True,
                'source_metadata_checked':True,
                'manual_review_required':True
            },
            'guards':{
                'changes_engine_rules':False,
                'changes_oos_baseline':False,
                'production_promotion':False
            }
        }
        provenance_path.write_text(json.dumps(provenance,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        cmd=[sys.executable,str(UPDATER),'--section','CERT53','--replacement',str(candidate_path),'--provenance',str(provenance_path)]
        cp=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
        if cp.returncode!=0:
            raise SystemExit(f'dry-run updater failed: {cp.stderr or cp.stdout}')
        summary=json.loads(cp.stdout)

    after_cert=sha(CERT53)
    after_part=sha(PART)
    after_prov=sorted(str(p.relative_to(ROOT)) for p in PROV_DIR.glob('*.json')) if PROV_DIR.exists() else []
    checks={
        'updater_status_pass':summary.get('status')=='PASS',
        'applied_false':summary.get('applied') is False,
        'provenance_required':summary.get('provenance_required') is True,
        'provenance_validated':summary.get('provenance_validated') is True,
        'refresh_id_propagated':summary.get('refresh_id')=='DRYRUN_CERT53_20261007_V1',
        'cert53_unchanged':before_cert==after_cert,
        'runtime_part_unchanged':before_part==after_part,
        'provenance_directory_unchanged':before_prov==after_prov,
        'candidate_diff_detected':summary.get('old_section_sha256')!=summary.get('new_section_sha256')
    }
    status='PASS' if all(checks.values()) else 'FAIL'
    result={
        'schema':'GMFQ_CERT53_PROVENANCE_DRY_RUN_V1',
        'status':status,
        'mode':'SYNTHETIC_NO_APPLY',
        'section':'CERT53',
        'pair_count':28,
        'refresh_id':'DRYRUN_CERT53_20261007_V1',
        'checks':checks,
        'before':{'cert53_sha256':before_cert,'runtime_part_sha256':before_part,'provenance_records':before_prov},
        'after':{'cert53_sha256':after_cert,'runtime_part_sha256':after_part,'provenance_records':after_prov},
        'updater_summary':summary,
        'guards':{
            'changes_live_data':False,
            'changes_runtime_payload':False,
            'writes_provenance_record':False,
            'changes_engine_rules':False,
            'production_promotion':False
        }
    }
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if status!='PASS':
        raise SystemExit(1)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
