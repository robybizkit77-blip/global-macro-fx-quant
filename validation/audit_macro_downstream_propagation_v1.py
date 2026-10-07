#!/usr/bin/env python3
from __future__ import annotations
import json, pathlib
from datetime import datetime, timezone

ROOT=pathlib.Path(__file__).resolve().parents[1]
VAL=ROOT/'validation'
MANIFEST=ROOT/'live_data'/'manifest.v2.json'
D=ROOT/'live_data'/'sections'/'D.json'
CERT=ROOT/'live_data'/'sections'/'CERT53.json'
HEAT=ROOT/'live_data'/'sections'/'MACRO_THERMOMETER_DATA.json'
SERIES=ROOT/'live_data'/'sections'/'MACRO_SERIES.json'
OUT=VAL/'MACRO_DOWNSTREAM_PROPAGATION_AUDIT_V1_2026-10-07.json'


def scan_paths(obj, path='$', out=None):
    if out is None: out=[]
    if isinstance(obj, dict):
        for k,v in obj.items():
            p=f'{path}.{k}'
            kl=str(k).lower()
            if any(t in kl for t in ('macro','fundamental_anchor','heat','inflation','unemployment','labour')):
                preview=v if isinstance(v,(str,int,float,bool,type(None))) else type(v).__name__
                out.append({'path':p,'preview':preview})
            scan_paths(v,p,out)
    elif isinstance(obj,list):
        for i,v in enumerate(obj[:200]):
            scan_paths(v,f'{path}[{i}]',out)
    return out


def script_scan():
    rows=[]
    for p in sorted(VAL.glob('*.py')):
        txt=p.read_text(encoding='utf-8',errors='ignore')
        reads_heat='MACRO_THERMOMETER_DATA' in txt
        reads_series='MACRO_SERIES' in txt
        touches_d=('D.json' in txt or "'D'" in txt or '"D"' in txt)
        touches_cert='CERT53' in txt
        if reads_heat or reads_series or touches_d or touches_cert:
            rows.append({
                'path':str(p.relative_to(ROOT)),
                'reads_macro_heatmap':reads_heat,
                'reads_macro_series':reads_series,
                'references_D':touches_d,
                'references_CERT53':touches_cert,
            })
    return rows


def main():
    manifest=json.loads(MANIFEST.read_text())
    entries={x['key']:x for x in manifest['sections']}
    candidate=(VAL/'build_macro_candidate.py').read_text(encoding='utf-8')
    signed=(VAL/'build_dashboard_pair_signed_inputs_v1.py').read_text(encoding='utf-8')
    scans=script_scan()
    bridge=[r for r in scans if (r['reads_macro_heatmap'] or r['reads_macro_series']) and (r['references_D'] or r['references_CERT53'])]
    # exclude diagnostics/self references that do not represent a writer; conservative classification below.
    actual_bridge=[]
    for r in bridge:
        if r['path'].endswith('audit_macro_downstream_propagation_v1.py'):
            continue
        txt=(ROOT/r['path']).read_text(encoding='utf-8',errors='ignore')
        if any(tok in txt for tok in ('write_text(', 'write_bytes(', 'dump(', '--apply')):
            actual_bridge.append(r)

    cert=json.loads(CERT.read_text())
    d=json.loads(D.read_text())
    cert_pairs=cert.get('pairs') or {}
    cert_macro={p:(row or {}).get('fundamental_anchor_macro') for p,row in cert_pairs.items()}
    cert_anchor_count=sum(v in {'A','B','MIXED'} for v in cert_macro.values())

    candidate_outputs=('MACRO_SERIES.json' in candidate and 'MACRO_THERMOMETER_DATA.json' in candidate)
    candidate_writes_cert='CERT53' in candidate
    candidate_writes_d='D.json' in candidate
    signed_reads_cert=("CERT53 =" in signed and "fundamental_anchor_macro" in signed)

    gap= not actual_bridge and not candidate_writes_cert and not candidate_writes_d
    status='GAP_BLOCK_MACRO_APPLY' if gap else 'CONNECTED_REVIEW_REQUIRED'
    out={
      'schema':'GMFQ_MACRO_DOWNSTREAM_PROPAGATION_AUDIT_V1',
      'created_at_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
      'status':status,
      'finding':'MACRO_SERIES and MACRO_THERMOMETER_DATA can be rebuilt, but no certified deterministic writer was found that propagates the resulting macro state into D/CERT53.',
      'manifest':{
        k:{'mode':entries[k]['mode'],'part':entries[k].get('part'),'direct_update_allowed':entries[k].get('direct_update_allowed')}
        for k in ('MACRO_SERIES','MACRO_THERMOMETER_DATA','D','CERT53')
      },
      'macro_candidate_builder':{
        'path':'validation/build_macro_candidate.py',
        'produces_macro_series_and_heatmap':candidate_outputs,
        'produces_D':candidate_writes_d,
        'produces_CERT53':candidate_writes_cert,
      },
      'downstream_dependency':{
        'pair_signed_inputs_path':'validation/build_dashboard_pair_signed_inputs_v1.py',
        'reads_CERT53_fundamental_anchor_macro':signed_reads_cert,
        'cert53_pair_count':len(cert_pairs),
        'cert53_pairs_with_macro_anchor':cert_anchor_count,
      },
      'repository_scan':{
        'scripts_with_relevant_references':scans,
        'candidate_bridge_writers':actual_bridge,
      },
      'live_structure_diagnostics':{
        'D_macro_related_paths_sample':scan_paths(d)[:80],
        'CERT53_macro_related_paths_sample':scan_paths(cert)[:80],
      },
      'policy':{
        'macro_apply_allowed':False if gap else False,
        'reason':'Do not permit live macro apply until a deterministic propagation builder updates all downstream macro consumers and passes replay parity.',
        'required_next_artifact':'Certified Macro Propagation Builder V1 with no-op parity + synthetic one-observation propagation test.',
        'schedule_enabled':False,
      },
      'guards':{
        'changes_live_data':False,
        'changes_engine_rules':False,
        'changes_oos_baseline':False,
        'production_promotion':False,
      }
    }
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'status':'PASS','audit_status':status,'bridge_writers':len(actual_bridge),'cert53_pairs':len(cert_pairs),'cert53_macro_anchors':cert_anchor_count},indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
