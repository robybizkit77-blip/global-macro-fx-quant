#!/usr/bin/env python3
import json
import re
import subprocess
from pathlib import Path

CERT = Path('live_data/sections/CERT53.json')
OUT = Path('validation/CERT53_MACRO_ANCHOR_PROVENANCE_AUDIT_V1_2026-10-07.json')


def sh(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def tracked_files():
    return sh('git','ls-files').splitlines()


def writes_files(text: str) -> bool:
    pats = [r'write_text\s*\(', r'write_bytes\s*\(', r'json\.dump\s*\(',
            r'open\s*\([^\n]{0,180}["\']w["\']']
    return any(re.search(p, text) for p in pats)


def main():
    cert = json.loads(CERT.read_text())
    pairs_obj = cert.get('pairs', {})
    pair_count = len(pairs_obj) if isinstance(pairs_obj, (list,dict)) else 0

    refs=[]; applicators=[]; regenerators=[]
    upstream_tokens=('MACRO_SERIES','MACRO_THERMOMETER_DATA','macro_series_id','growth','labour','inflation')
    for name in tracked_files():
        p=Path(name)
        if not p.is_file() or p in {CERT,OUT}: continue
        if p.suffix.lower() not in {'.py','.yml','.yaml','.js','.json','.md','.txt','.html'}: continue
        try: text=p.read_text(errors='ignore')
        except Exception: continue
        if 'CERT53' not in text and 'fundamental_anchor_macro' not in text: continue
        refs.append(name)
        # Applicator: can replace/write CERT53 but may accept an externally prepared candidate.
        if 'CERT53' in text and writes_files(text): applicators.append(name)
        # Economic regenerator must both construct/assign the anchor and depend on macro inputs.
        constructs_anchor = bool(re.search(r'fundamental_anchor_macro\s*[:=]', text))
        reads_macro = any(tok in text for tok in upstream_tokens)
        if constructs_anchor and reads_macro and writes_files(text): regenerators.append(name)

    try: log=sh('git','log','--follow','--format=%H|%aI|%s','--',str(CERT)).splitlines()
    except subprocess.CalledProcessError: log=[]

    governance=cert.get('governance',{}) if isinstance(cert.get('governance'),dict) else {}
    meta=cert.get('meta',{}) if isinstance(cert.get('meta'),dict) else {}
    certified_at=cert.get('certified_at') or governance.get('certified_at') or meta.get('certified_at')
    certification_state=cert.get('certification_state') or governance.get('certification_state') or meta.get('certification_state')

    status='LIVE_ECONOMIC_REGENERATOR_FOUND_REQUIRES_REVIEW' if regenerators else 'NO_LIVE_ECONOMIC_REGENERATOR_FOUND'
    out={
      'schema':'GMFQ_CERT53_MACRO_ANCHOR_PROVENANCE_AUDIT_V1',
      'status':status,
      'source_file':str(CERT),'pair_count':pair_count,
      'certification_state':certification_state,'certified_at':certified_at,
      'git_history':log,'repository_references':sorted(refs),
      'cert53_applicators':sorted(applicators),'applicator_count':len(applicators),
      'economic_regenerator_candidates':sorted(regenerators),'economic_regenerator_count':len(regenerators),
      'classification_note':'A safe CERT53 candidate applicator is not a Macro economic regenerator. A regenerator must construct fundamental_anchor_macro from explicit Macro inputs.',
      'known_safe_refresh_path':{
        'path':'validation/run_cert53_refresh_v1.py',
        'role':'APPLICATOR_ONLY',
        'requires_prebuilt_candidate':True,
        'derives_macro_anchor':False
      },
      'frozen_engine_architecture':{
        'canonical_pair_macro_source':'compare canonical currency Macro states',
        'legacy_pair_macro_override_allowed':False,
        'note':'Frozen runtime explicitly prevents legacy relative pair Macro readings from overriding the canonical currency engine.'
      },
      'interpretation':{
        'does_not_claim_cert53_wrong':True,
        'claim':'CERT53 has a safe refresh/apply mechanism, but no repository component was found that economically regenerates fundamental_anchor_macro from current canonical Macro inputs.',
        'macro_ingest_apply':'BLOCKED_UNTIL_CURRENT_CANONICAL_CURRENCY_MACRO_REGENERATION_EXISTS',
        'next_required_artifact':'CURRENT_CANONICAL_CURRENCY_MACRO_REGENERATION_CONTRACT_V1'
      },
      'guards':{'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False,'production_promotion':False,'predictive_claim':False}
    }
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':status,'pair_count':pair_count,'applicators':len(applicators),'economic_regenerators':len(regenerators),'history_entries':len(log)},ensure_ascii=False))

if __name__=='__main__': main()
