#!/usr/bin/env python3
import hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CERT=ROOT/'live_data/sections/CERT53.json'
MAN=ROOT/'live_data/manifest.v2.json'
OUT=ROOT/'validation/CERT53_PROVENANCE_AUDIT_V1_2026-10-07.json'

cert_bytes=CERT.read_bytes()
cert=json.loads(cert_bytes)
man=json.loads(MAN.read_text(encoding='utf-8'))
rows=[x for x in man.get('sections',[]) if x.get('key')=='CERT53']
assert len(rows)==1, f'expected one CERT53 manifest row, got {len(rows)}'
row=rows[0]
actual_sha=hashlib.sha256(cert_bytes).hexdigest()
manifest_match=(row.get('sha256')==actual_sha and row.get('bytes')==len(cert_bytes))
pair_count=len(cert.get('pairs',{}))

# Current file has no canonical file-level source/as-of lineage contract.
file_level_keys=set(cert.keys())
file_level_provenance_present=bool({'source','source_url','as_of','updated_at','generated_at','input_hashes'} & file_level_keys)
status='READY_PROVENANCE' if manifest_match and pair_count==28 and file_level_provenance_present else 'PARTIAL_PROVENANCE'

out={
  'schema':'GMFQ_CERT53_PROVENANCE_AUDIT_V1',
  'status':status,
  'purpose':'Audit whether CERT53 is hash-verified and whether its upstream lineage is explicit enough for autonomous forward-snapshot provenance.',
  'cert53':{
    'path':'live_data/sections/CERT53.json',
    'sha256':actual_sha,
    'bytes':len(cert_bytes),
    'pair_count':pair_count,
    'manifest_sha_match':manifest_match,
    'manifest_mode':row.get('mode'),
    'direct_update_allowed':row.get('direct_update_allowed'),
    'file_level_provenance_present':file_level_provenance_present
  },
  'assessment':{
    'runtime_integrity':'PASS' if manifest_match and pair_count==28 else 'FAIL',
    'upstream_lineage':'PASS' if file_level_provenance_present else 'PARTIAL',
    'automatic_downstream_from_cert53':True,
    'automatic_upstream_ingestion':False,
    'fully_autonomous_claim_allowed':False
  },
  'required_for_ready_provenance':[
    'canonical file-level source/as-of metadata or deterministic builder input manifest',
    'input hashes for the live sections used to construct CERT53',
    'refresh identifier or canonical refresh commit recorded at generation time'
  ],
  'guards':{
    'changes_engine_rules':False,
    'changes_live_data':False,
    'changes_oos_baseline':False,
    'production_promotion':False
  }
}
OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
assert out['assessment']['runtime_integrity']=='PASS'
assert out['status'] in {'PARTIAL_PROVENANCE','READY_PROVENANCE'}
print(json.dumps({'status':'PASS','provenance_status':status,'cert53_sha256':actual_sha,'pair_count':pair_count},indent=2))
