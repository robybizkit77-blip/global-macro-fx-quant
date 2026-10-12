#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path

CCYS=('USD','EUR','JPY','CAD','AUD')
DIMS=('inflation','labour')

def load(p:Path):
    return json.loads(p.read_text(encoding='utf-8'))

def sha256(p:Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def same_value(a,b):
    try: return math.isclose(float(a),float(b),rel_tol=0.0,abs_tol=1e-10)
    except Exception: return a==b

def classify_action(summary:dict)->str:
    action=summary.get('series_action')
    if action=='APPEND_NEW':
        return 'APPEND_NEW_ELIGIBLE_FOR_ATOMIC_PIT_REVIEW'
    if action=='REPLACE_EXISTING':
        old=summary.get('current_value')
        new=summary.get('new_value')
        if same_value(old,new):
            return 'NO_CHANGE_ALREADY_CANONICAL'
        return 'REVISION_SAME_PERIOD_WITHHELD_PENDING_RELEASE_PROVENANCE'
    raise RuntimeError(f'unsupported builder series_action: {action!r}')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',required=True,type=Path)
    ap.add_argument('--source-map',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    a=ap.parse_args()
    sm=load(a.source_map)
    streams={x['key']:x for x in sm['streams']}
    rows=[]
    for c in CCYS:
        for d in DIMS:
            key=f'{c}.{d}'
            if key not in streams: raise RuntimeError(f'missing source-map stream {key}')
            root=a.root/c.lower()/d
            cand=root/'candidate.json'; audit=root/'source-audit.json'; summary=root/'built'/'summary.json'
            if not cand.exists() or not audit.exists() or not summary.exists():
                raise RuntimeError(f'missing dry-run evidence for {key}')
            cj=load(cand); aj=load(audit); sj=load(summary)
            if cj.get('currency')!=c or cj.get('dimension')!=d: raise RuntimeError((key,cj))
            if cj.get('macro_series_id')!=streams[key]['macro_series_id']: raise RuntimeError(f'macro_series drift {key}')
            if sj.get('status')!='PASS' or sj.get('live_data_modified') is not False: raise RuntimeError(f'builder failed {key}: {sj}')
            if sj.get('observation_date')!=cj.get('observation_date'): raise RuntimeError(f'date mismatch {key}')
            if bool(aj.get('live_data_written',False)): raise RuntimeError(f'source wrote live data {key}')
            pit_action=classify_action(sj)
            rows.append({
                'key':key,
                'observation_date':cj['observation_date'],
                'value':cj['value'],
                'source':cj.get('source'),
                'source_url':cj.get('source_url'),
                'macro_series_id':cj['macro_series_id'],
                'builder_series_action':sj.get('series_action'),
                'builder_current_value':sj.get('current_value'),
                'builder_new_value':sj.get('new_value'),
                'pit_refresh_classification':pit_action,
                'candidate_sha256':sha256(cand),
                'audit_sha256':sha256(audit),
                'builder_summary_sha256':sha256(summary),
                'builder_status':'PASS',
                'live_data_modified':False,
            })
    if len(rows)!=10: raise RuntimeError(f'expected 10 streams got {len(rows)}')
    counts={}
    for r in rows: counts[r['pit_refresh_classification']]=counts.get(r['pit_refresh_classification'],0)+1
    out={
        'schema':'GMFQ_FORWARD_MACRO_REFRESH_DRY_RUN_RECEIPT_V1',
        'status':'PASS_ALL_10_SOURCE_CANDIDATES_READ_ONLY',
        'stream_count':10,
        'currencies':list(CCYS),
        'dimensions':list(DIMS),
        'classification_counts':counts,
        'streams':rows,
        'pit_promotion_performed':False,
        'shared_boundary_advanced':False,
        'live_data_written':False,
        'production_signal_authorized':False,
        'sizing_authorized':False,
        'revision_rule':'same-period value changes are withheld from forward PIT until release-specific provenance is certified',
        'next_step':'atomic_PIT_review_only_for_APPEND_NEW; revisions remain withheld; then unified readiness recheck',
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(out,indent=2,sort_keys=True))
if __name__=='__main__': main()
