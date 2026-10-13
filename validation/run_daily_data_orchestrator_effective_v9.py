#!/usr/bin/env python3
import json,subprocess,sys
from pathlib import Path
BASE=Path('validation/run_daily_data_orchestrator_effective_v8.py')
OVERRIDE=Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_AUD_BUSINESS_CREDIT_REVISION_AWARE_V1_2026-10-13.json')
POLICY='validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json'

def main():
    p=subprocess.run([sys.executable,str(BASE)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if p.returncode: raise SystemExit(p.stdout)
    d=json.loads(p.stdout); o=json.loads(OVERRIDE.read_text(encoding='utf-8')); r=o['effective_row']; delta=o['coverage_delta']
    if o.get('schema')!='GMFQ_LIQUIDITY_POLICY_OVERRIDE_V1' or o['supersedes']!={'policy':POLICY,'subseries':'AUD.credit'}: raise SystemExit('invalid AUD.credit override')
    checks=[r.get('automation_ready') is True,r.get('controlled_apply_proven') is True,r.get('revision_aware_append_only') is True,r.get('historical_runtime_values_frozen') is True,r.get('new_observation_transform')=='ROUND_1DP',r.get('series_key')=='DLCACSFBS',r.get('historical_overlap_count')==85,r.get('historical_rounded_1dp_match_count')==56,r.get('historical_current_vintage_revision_mismatch_count')==29,r.get('real_append_replay_proven') is True,r.get('official_last_date')=='2026-08',abs(float(r.get('official_last_value'))-1536.5)<1e-9,int(delta.get('automation_ready_subseries',0))==1,int(delta.get('mapping_pending_subseries',0))==-1]
    if not all(checks): raise SystemExit('AUD.credit override proof drifted')
    if not Path(r['collector']).exists() or not Path(r['applier']).exists(): raise SystemExit('AUD.credit collector/applier missing')
    liq=d['lanes']['LIQUIDITY']
    if liq.get('automation_ready_subseries')!=20 or liq.get('mapping_pending_subseries')!=6: raise SystemExit(f'unexpected V8 coverage {liq}')
    liq['verified_subseries']=21; liq['unresolved_subseries']=5; liq['automation_ready_subseries']=21; liq['mapping_pending_subseries']=5
    liq.setdefault('source_policy_overrides',[]).append(str(OVERRIDE))
    liq.update({'aud_credit_automation_ready':True,'aud_credit_controlled_apply_proven':True,'aud_credit_revision_aware_append_only':True,'aud_credit_series_key':r['series_key'],'aud_credit_collector':r['collector'],'aud_credit_applier':r['applier'],'aud_credit_apply_proof_run_id':r['apply_proof_run_id'],'aud_credit_real_append_replay_proven':True,'aud_credit_official_tail':{'date':r['official_last_date'],'value':r['official_last_value']}})
    liq['reason']='26/26 official source families mapped; 21/26 automation-ready after AUD business-credit revision-aware append-only promotion. Remaining 5 stay fail-closed.'
    d['effective_liquidity_overlay_v9']={'schema':'GMFQ_DAILY_DATA_ORCHESTRATOR_EFFECTIVE_LIQUIDITY_OVERLAY_V9','version':'2026-10-13-aud-business-credit-ready','base_overlay_ready':20,'base_overlay_pending':6,'ready':21,'pending':5,'total':26,'runtime_mutated':False,'publication_performed':False}
    print(json.dumps(d,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
