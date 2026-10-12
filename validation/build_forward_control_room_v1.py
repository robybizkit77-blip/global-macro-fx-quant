#!/usr/bin/env python3
from __future__ import annotations

import argparse,json
from pathlib import Path

ALLOWED={'WAITING_FOR_UNSEEN_OBSERVATIONS','FORWARD_CONFIRMED_PENDING_PROMOTION_REVIEW','FORWARD_GATE_FAILED_NO_TUNING'}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--sources',required=True,type=Path); ap.add_argument('--readiness',required=True,type=Path); ap.add_argument('--output',required=True,type=Path); a=ap.parse_args()
    s=json.loads(a.sources.read_text(encoding='utf-8')); r=json.loads(a.readiness.read_text(encoding='utf-8'))
    assert s['schema']=='GMFQ_FORWARD_CONTROL_ROOM_SOURCES_V1'
    assert r['schema']=='GMFQ_FORWARD_INPUT_READINESS_V1'
    sr=s['shared_readiness']
    assert r['current_max_certified_decision_point']==sr['max_certified_decision_point']=='2026-10-10'
    assert r['next_required_decision_point']==sr['next_required_decision_point']=='2026-11-10'
    assert r['current_inputs_green']==sr['inputs_green']==15
    assert r['next_decision_point_ready'] is sr['next_ready'] is False

    rows=[]
    ids=set()
    for c in s['candidates']:
        cid=c['candidate_id']; assert cid not in ids; ids.add(cid)
        assert c['status'] in ALLOWED
        assert c['decision_weight']==0
        assert c['production_signal_authorized'] is False
        assert c['sizing_authorized'] is False
        if c['uses_shared_macro_rates_readiness']:
            assert '2026-10-10' in c['latest_input_asof']
        rows.append({
          'candidate_id':cid,
          'display_name':c['display_name'],
          'state':c['status'],
          'forward_boundary':c['forward_boundary'],
          'unseen_signals':c['signals_unseen'],
          'matured_primary':c['matured_primary'],
          'matured_secondary':c['matured_secondary'],
          'max_certified_input_asof':c['latest_input_asof'],
          'input_blocker':c['input_blocker'],
          'next_gate_requirement':c['next_gate_requirement'],
          'source_receipt':{
            'run_id':c['run_id'],'artifact_id':c['artifact_id'],'artifact_sha256':c['artifact_sha256'],
            'forward_pr':c['forward_pr'],'receipt_pr':c['receipt_pr']
          },
          'decision_weight':0,
          'production_signal_authorized':False,
          'sizing_authorized':False,
        })
    assert ids=={'COT_104W_EXTREME_REVERSAL_80_20_V1','RATES_DOVISH_DIVERGENCE_V1','MACRO_TURNING_2Y_CONFIRMED_FX_V1'}

    out={
      'schema':'GMFQ_FORWARD_CONTROL_ROOM_V1',
      'as_of':s['as_of'],
      'status':'RESEARCH_FORWARD_WAITING',
      'shared_input_readiness':{
        'max_certified_decision_point':r['current_max_certified_decision_point'],
        'next_required_decision_point':r['next_required_decision_point'],
        'inputs_green':r['current_inputs_green'],
        'next_ready':r['next_decision_point_ready'],
        'blockers_count':len(r['next_decision_point_blockers']),
        'readiness_artifact':sr,
      },
      'candidate_count':len(rows),
      'candidates':rows,
      'decision_layer_effect':'NONE',
      'bias_effect':'NONE',
      'ranking_effect':'NONE',
      'sizing_effect':'NONE',
      'production_signal_authorized':False,
      'sizing_authorized':False,
      'repository_write_performed':False,
    }
    assert out['candidate_count']==3
    assert all(x['decision_weight']==0 for x in rows)
    assert out['production_signal_authorized'] is out['sizing_authorized'] is False
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'status':out['status'],'shared_input_readiness':out['shared_input_readiness'],'candidates':[{k:x[k] for k in ('candidate_id','state','unseen_signals','matured_primary','input_blocker')} for x in rows]},indent=2))

if __name__=='__main__': main()
