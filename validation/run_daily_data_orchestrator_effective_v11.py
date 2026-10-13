#!/usr/bin/env python3
import json,subprocess,sys
from pathlib import Path
BASE=Path('validation/run_daily_data_orchestrator_effective_v10.py')
OVERRIDE=Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_CAD_SETTLEMENT_REVISION_AWARE_V1_2026-10-13.json')
POLICY='validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json'

def main():
 p=subprocess.run([sys.executable,str(BASE)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 if p.returncode: raise SystemExit(p.stdout)
 d=json.loads(p.stdout); o=json.loads(OVERRIDE.read_text()); r=o['effective_row']; delta=o['coverage_delta']
 if o.get('schema')!='GMFQ_LIQUIDITY_POLICY_OVERRIDE_V1' or o['supersedes']!={'policy':POLICY,'subseries':'CAD.liquidity'}: raise SystemExit('invalid CAD.liquidity override')
 checks=[r.get('automation_ready') is True,r.get('controlled_apply_proven') is True,r.get('revision_aware_append_only') is True,r.get('historical_runtime_values_frozen') is True,r.get('series_id')=='ACTUAL',r.get('normalization_rule')=='LAST_AVAILABLE_OFFICIAL_OBSERVATION_IN_COMPLETED_CALENDAR_MONTH',r.get('operational_recent_guard_months')==12,r.get('operational_recent_guard_exact_matches')==12,r.get('historical_overlap_months')==128,r.get('historical_exact_matches')==115,r.get('historical_mismatches_frozen')==13,r.get('real_append_replay_proven') is True,r.get('replay_guard_months')==11,r.get('replay_guard_exact_matches')==11,r.get('runtime_last_month')=='2026-08',abs(float(r.get('runtime_last_value'))-74157.0)<1e-9,r.get('official_latest_completed_month')=='2026-09',abs(float(r.get('official_latest_completed_value'))-83440.0)<1e-9,r.get('official_latest_completed_source_date')=='2026-09-29',int(delta.get('automation_ready_subseries',0))==1,int(delta.get('mapping_pending_subseries',0))==-1]
 if not all(checks): raise SystemExit('CAD.liquidity override proof drifted')
 if not Path(r['collector']).exists() or not Path(r['applier']).exists(): raise SystemExit('CAD.liquidity collector/applier missing')
 liq=d['lanes']['LIQUIDITY']
 if liq.get('automation_ready_subseries')!=22 or liq.get('mapping_pending_subseries')!=4: raise SystemExit(f'unexpected V10 coverage {liq}')
 liq['verified_subseries']=23; liq['unresolved_subseries']=3; liq['automation_ready_subseries']=23; liq['mapping_pending_subseries']=3
 liq.setdefault('source_policy_overrides',[]).append(str(OVERRIDE))
 liq.update({'cad_liquidity_automation_ready':True,'cad_liquidity_controlled_apply_proven':True,'cad_liquidity_revision_aware_append_only':True,'cad_liquidity_series_id':'ACTUAL','cad_liquidity_normalization_rule':r['normalization_rule'],'cad_liquidity_operational_guard':'12/12','cad_liquidity_real_append_replay_proven':True,'cad_liquidity_apply_proof_run_id':r['apply_proof_run_id'],'cad_liquidity_official_tail':{'month':r['official_latest_completed_month'],'source_date':r['official_latest_completed_source_date'],'value':r['official_latest_completed_value']}})
 liq['reason']='26/26 official source families mapped; 23/26 automation-ready after CAD settlement-balances revision-aware append-only promotion. CHF liquidity, CHF credit and JPY liquidity remain fail-closed pending exact provenance.'
 d['effective_liquidity_overlay_v11']={'schema':'GMFQ_DAILY_DATA_ORCHESTRATOR_EFFECTIVE_LIQUIDITY_OVERLAY_V11','version':'2026-10-13-cad-settlement-ready','base_overlay_ready':22,'base_overlay_pending':4,'ready':23,'pending':3,'total':26,'remaining_fail_closed':['CHF.liquidity','CHF.credit','JPY.liquidity'],'runtime_mutated':False,'publication_performed':False}
 print(json.dumps(d,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
