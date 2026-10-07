#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, shutil, subprocess, sys, tempfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
SECTIONS=ROOT/'live_data'/'sections'
PAYLOAD=ROOT/'payload'
MANIFEST=ROOT/'live_data'/'manifest.v2.json'
PROV_ROOT=ROOT/'live_data'/'provenance'/'rates'
EXPECTED={'USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'}
REQUIRED={'date','source','quality','2Y','10Y','curve_bp','history2','history10'}

def sha(b:bytes)->str: return hashlib.sha256(b).hexdigest()

def run(*args:str)->None:
    subprocess.run(args,cwd=ROOT,check=True)

def validate_candidate(path:pathlib.Path)->tuple[dict,str]:
    raw=path.read_bytes(); data=json.loads(raw.decode('utf-8'))
    if set(data)!=EXPECTED:
        raise SystemExit(f'Rates candidate currencies mismatch: {sorted(data)}')
    for c,row in data.items():
        if not isinstance(row,dict): raise SystemExit(f'{c}: row must be object')
        miss=REQUIRED-set(row)
        if miss: raise SystemExit(f'{c}: missing {sorted(miss)}')
        if not isinstance(row['source'],str) or not row['source'].strip(): raise SystemExit(f'{c}: source missing')
        if not isinstance(row['date'],str) or not row['date'].strip(): raise SystemExit(f'{c}: date missing')
        for k in ('2Y','10Y','curve_bp'):
            if not isinstance(row[k],(int,float)): raise SystemExit(f'{c}: {k} must be numeric')
    return data,sha(raw)

def validate_prov(path:pathlib.Path,candidate_sha:str)->dict:
    p=json.loads(path.read_text(encoding='utf-8'))
    if p.get('schema')!='GMFQ_RATES_REFRESH_PROVENANCE_V1': raise SystemExit('Rates provenance schema mismatch')
    if p.get('status')=='TEMPLATE_NOT_A_REFRESH_RECORD': raise SystemExit('Rates provenance template cannot be used')
    if p.get('section')!='NATIVE_RATES_DATA': raise SystemExit('Rates provenance section mismatch')
    rid=p.get('refresh_id')
    if not isinstance(rid,str) or not re.fullmatch(r'[A-Za-z0-9._:-]{8,128}',rid): raise SystemExit('Rates refresh_id invalid')
    if p.get('candidate_sha256')!=candidate_sha: raise SystemExit('Rates provenance candidate hash mismatch')
    if not p.get('created_at_utc') or not p.get('source_asof'): raise SystemExit('Rates provenance timestamps missing')
    inputs=p.get('inputs')
    if not isinstance(inputs,list) or len(inputs)<1: raise SystemExit('Rates provenance inputs missing')
    v=p.get('validation') or {}
    for k in ('eight_currencies_present','required_fields_present','source_metadata_checked','freshness_checked','manual_review_required'):
        if v.get(k) is not True: raise SystemExit(f'Rates provenance validation flag false: {k}')
    g=p.get('guards') or {}
    if g.get('changes_engine_rules') is not False or g.get('changes_oos_baseline') is not False or g.get('production_promotion') is not False:
        raise SystemExit('Rates provenance guards invalid')
    return p

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--rates',required=True)
    ap.add_argument('--audit-metadata',required=True)
    ap.add_argument('--provenance',required=True)
    ap.add_argument('--apply',action='store_true')
    ap.add_argument('--confirm-refresh-id')
    a=ap.parse_args()

    rates_path=pathlib.Path(a.rates); meta_path=pathlib.Path(a.audit_metadata); prov_path=pathlib.Path(a.provenance)
    _,candidate_sha=validate_candidate(rates_path)
    json.loads(meta_path.read_text(encoding='utf-8'))
    prov=validate_prov(prov_path,candidate_sha)
    rid=prov['refresh_id']
    target=PROV_ROOT/f'{rid}.json'
    if target.exists(): raise SystemExit('Rates refresh_id already exists')
    if a.apply and a.confirm_refresh_id!=rid:
        raise SystemExit('Rates --apply refused: --confirm-refresh-id must exactly match provenance refresh_id')

    run(sys.executable,'validation/check_live_update_contract.py')
    # preflight direct-section replacement; no write
    run(sys.executable,'validation/update_live_direct_section.py','--section','NATIVE_RATES_DATA','--replacement',str(rates_path))

    summary={'status':'PREFLIGHT_PASS','refresh_id':rid,'candidate_sha256':candidate_sha,'applied':False}
    if not a.apply:
        print(json.dumps(summary,indent=2)); return 0

    protected=[SECTIONS/'NATIVE_RATES_DATA.json',SECTIONS/'RATES_AUDIT_METADATA.json',MANIFEST]
    # include all payload parts because derived metadata may touch a different part
    protected += [PAYLOAD/f'part-{i:02d}.txt' for i in range(16)]
    backup={p:p.read_bytes() for p in protected if p.exists()}
    try:
        run(sys.executable,'validation/update_live_direct_section.py','--section','NATIVE_RATES_DATA','--replacement',str(rates_path),'--apply')
        run(sys.executable,'validation/update_live_derived_sections.py','--rates',str(meta_path),'--apply')
        manifest_bytes=subprocess.check_output([sys.executable,'validation/build_live_manifest_v2.py'],cwd=ROOT)
        MANIFEST.write_bytes(manifest_bytes)
        run(sys.executable,'validation/check_live_update_contract.py')
        PROV_ROOT.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(prov,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        summary.update({'status':'APPLY_PASS','applied':True,'provenance_record':str(target.relative_to(ROOT))})
    except Exception:
        for p,b in backup.items(): p.write_bytes(b)
        if target.exists(): target.unlink()
        raise
    print(json.dumps(summary,indent=2)); return 0

if __name__=='__main__': sys.exit(main())
