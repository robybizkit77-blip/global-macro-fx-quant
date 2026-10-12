#!/usr/bin/env python3
import argparse, json
from pathlib import Path

ALLOWED={"FALSIFIED","INFORMATIVE_ONLY","CANDIDATE_FORWARD_WAITING","FORWARD_CONFLUENCE_WAITING","VALIDATED_PENDING_PROMOTION","PRODUCTION_AUTHORIZED"}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--registry',required=True); p.add_argument('--output',required=True); p.add_argument('--dashboard-sidecar'); a=p.parse_args()
    r=json.loads(Path(a.registry).read_text()); assert r['schema']=='GMFQ_RESEARCH_CANDIDATE_REGISTRY_V1'; assert set(r['allowed_statuses'])==ALLOWED
    ids=set();bad=[];nonzero=[]
    for e in r['entries']:
        assert e['id'] not in ids; ids.add(e['id']); assert e['status'] in ALLOWED
        prod=bool(e.get('production_signal_authorized',False)); size=bool(e.get('sizing_authorized',False)); weight=float(e.get('dashboard_decision_weight',0))
        if e['status']!='PRODUCTION_AUTHORIZED' and (prod or size): bad.append(e['id'])
        if e['status']!='PRODUCTION_AUTHORIZED' and abs(weight)>1e-12: nonzero.append(e['id'])
        if e['status']=='FALSIFIED': assert prod is False and size is False
        if e['status'] in ('CANDIDATE_FORWARD_WAITING','FORWARD_CONFLUENCE_WAITING'): assert prod is False and size is False
    sidecar=[]
    if a.dashboard_sidecar:
        d=json.loads(Path(a.dashboard_sidecar).read_text()); assert d['schema']=='GMFQ_RESEARCH_CANDIDATES_DASHBOARD_V1'; assert d['mode']=='DISPLAY_ONLY_RESEARCH'
        g=d['governance']; assert g['decision_weight']==g['bias_effect']==g['ranking_effect']==g['sizing_effect']==0; assert g['production_authorized'] is False
        for c in d['candidates']:
            assert c['id'] in ids; assert c['decision_weight']==0
            reg=next(e for e in r['entries'] if e['id']==c['id']); assert reg['status']!='PRODUCTION_AUTHORIZED'; sidecar.append(c['id'])
    out={'schema':'GMFQ_RESEARCH_CANDIDATE_REGISTRY_RECEIPT_V1','status':'PASS_REGISTRY_GOVERNANCE' if not bad and not nonzero else 'FAIL_REGISTRY_GOVERNANCE','entries_total':len(r['entries']),'status_counts':{s:sum(1 for e in r['entries'] if e['status']==s) for s in sorted(ALLOWED)},'unauthorized_production_or_sizing_entries':bad,'nonproduction_nonzero_dashboard_weight_entries':nonzero,'dashboard_sidecar_entries':sidecar,'production_signal_authorized_entries':[e['id'] for e in r['entries'] if e.get('production_signal_authorized')],'sizing_authorized_entries':[e['id'] for e in r['entries'] if e.get('sizing_authorized')]}
    Path(a.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n'); print(json.dumps(out,indent=2,sort_keys=True)); raise SystemExit(0 if out['status']=='PASS_REGISTRY_GOVERNANCE' else 1)
if __name__=='__main__': main()
