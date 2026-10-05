#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, pathlib, subprocess, tempfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE='0467d03f500dbaaf640bc653466457c5962e88b5'
FILES=[
 'live_data/sections/MACRO_SERIES.json',
 'live_data/sections/MACRO_THERMOMETER_DATA.json',
 'payload/part-00.txt','payload/part-01.txt','live_data/manifest.v2.json'
]

def b(path): return (ROOT/path).read_bytes()
def h(x): return hashlib.sha256(x).hexdigest()
def git_show(ref,path):
    cp=subprocess.run(['git','show',f'{ref}:{path}'],cwd=ROOT,capture_output=True)
    if cp.returncode: raise SystemExit(cp.stderr.decode(errors='replace'))
    return cp.stdout

def update(section,replacement):
    cp=subprocess.run(['python','validation/update_live_direct_section.py','--section',section,'--replacement',str(replacement),'--apply'],cwd=ROOT,text=True,capture_output=True)
    if cp.returncode: raise SystemExit(cp.stdout+'\n'+cp.stderr)
    return json.loads(cp.stdout)

def rebuild_manifest():
    cp=subprocess.run(['python','validation/build_live_manifest_v2.py'],cwd=ROOT,text=True,capture_output=True)
    if cp.returncode: raise SystemExit(cp.stdout+'\n'+cp.stderr)
    obj=json.loads(cp.stdout)
    if obj.get('status')!='PASS': raise SystemExit('manifest rebuild not PASS')
    (ROOT/'live_data/manifest.v2.json').write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
    return obj

def assert_equal_state(label,expected):
    mismatches=[]
    for p in FILES:
        got=b(p); exp=expected[p]
        if got!=exp: mismatches.append({'file':p,'got':h(got),'expected':h(exp),'got_bytes':len(got),'expected_bytes':len(exp)})
    if mismatches: raise SystemExit(label+' byte mismatch: '+json.dumps(mismatches,indent=2))

candidate={p:b(p) for p in FILES}
base={p:git_show(BASE,p) for p in FILES}
D_before=b('live_data/sections/D.json')

with tempfile.TemporaryDirectory() as td0:
    td=pathlib.Path(td0)
    old_series=td/'old_MACRO_SERIES.json'; old_thermo=td/'old_MACRO_THERMOMETER_DATA.json'
    old_series.write_bytes(base['live_data/sections/MACRO_SERIES.json'])
    old_thermo.write_bytes(base['live_data/sections/MACRO_THERMOMETER_DATA.json'])
    rollback_updates=[update('MACRO_SERIES',old_series),update('MACRO_THERMOMETER_DATA',old_thermo)]
    rollback_manifest=rebuild_manifest()
    assert_equal_state('ROLLBACK_TO_BASE',base)

    cand_series=td/'candidate_MACRO_SERIES.json'; cand_thermo=td/'candidate_MACRO_THERMOMETER_DATA.json'
    cand_series.write_bytes(candidate['live_data/sections/MACRO_SERIES.json'])
    cand_thermo.write_bytes(candidate['live_data/sections/MACRO_THERMOMETER_DATA.json'])
    reapply_updates=[update('MACRO_SERIES',cand_series),update('MACRO_THERMOMETER_DATA',cand_thermo)]
    reapply_manifest=rebuild_manifest()
    assert_equal_state('REAPPLY_CANDIDATE',candidate)

if b('live_data/sections/D.json')!=D_before:
    raise SystemExit('D.json changed during rollback roundtrip')

report={
 'schema_version':'GMFQ_JPN_LABOUR_ROLLBACK_ROUNDTRIP_V1',
 'status':'PASS','base_commit':BASE,
 'files_byte_identical_on_rollback':FILES,
 'files_byte_identical_after_reapply':FILES,
 'rollback_updates':rollback_updates,'reapply_updates':reapply_updates,
 'rollback_manifest_status':rollback_manifest['status'],'reapply_manifest_status':reapply_manifest['status'],
 'D_json_byte_identical':True,
 'production_write':False,'oos_restart':False
}
print(json.dumps(report,indent=2,ensure_ascii=False))
