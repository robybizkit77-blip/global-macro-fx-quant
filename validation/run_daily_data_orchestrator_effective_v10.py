#!/usr/bin/env python3
import json,subprocess,sys
from pathlib import Path
BASE=Path('validation/run_daily_data_orchestrator_effective_v9.py')
OVERRIDE=Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_USD_BANK_CREDIT_REVISION_AWARE_V1_2026-10-13.json')
POLICY='validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json'

def main():
 p=subprocess.run([sys.executable,str(BASE)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 if p.returncode: raise SystemExit(p.stdout)
 d=json.loads(p.stdout); o=json.loads(OVERRIDE.read_text()); r=o['effective_row']; delta=o['coverage_delta']
 if o.get('schema')!='GMFQ_LIQUIDITY_POLICY_OVERRIDE_V1' or o['supersedes']!={'policy':POLICY,'subseries':'USD.credit'}: raise SystemExit('invalid USD.credit override')
 checks=[r.get('automation_ready') is True,r.get('controlled_apply_proven') is True,r.get('revision_aware_append_only') is True,r.get('historical_runtime_values_frozen') is True,r.get('new_observation_transform')=='SCALE_0.001',r.get('series_id')=='B1001NCBA',r.get('historical_overlap_count')==300,r.get('historical_current_vintage_exact_match_count')==69,r.get('historical_current_vintage_revision_mismatch_count')==231,r.get('controlled_append_proven') is True,r.get('official_last_date')=='2026-09-30',abs(float(r.get('official_last_value'))-19883.1863)<1e-9,int(delta.get('automation_ready_subseries',0))==1,int(delta.get('mapping_pending_subseries',0))==-1]
 if not all(checks): raise SystemExit('USD.credit override proof drifted')
 if not Path(r['collector']).exists() or not Path(r['applier']).exists(): raise SystemExit('USD.credit collector/applier missing')
 liq=d['lanes']['LIQUIDITY']
 if liq.get('automation_ready_subseries')!=21 or liq.get('mapping_pending_subseries')!=5: raise SystemExit(f'unexpected V9 coverage {liq}')
 liq['verified_subseries']=22; liq['unresolved_subseries']=4; liq['automation_ready_subseries']=22; liq['mapping_pending_subseries']=4
 liq.setdefault('source_policy_overrides',[]).append(str(OVERRIDE))
 liq.update({'usd_credit_automation_ready':True,'usd_credit_controlled_apply_proven':True,'usd_credit_revision_aware_append_only':True,'usd_credit_series_id':r['series_id'],'usd_credit_collector':r['collector'],'usd_credit_applier':r['applier'],'usd_credit_apply_proof_run_id':r['apply_proof_run_id'],'usd_credit_controlled_append_proven':True,'usd_credit_official_tail':{'date':r['official_last_date'],'value':r['official_last_value']}})
 liq['reason']='26/26 official source families mapped; 22/26 automation-ready after USD bank-credit revision-aware append-only promotion. Remaining 4 stay fail-closed.'
 d['effective_liquidity_overlay_v10']={'schema':'GMFQ_DAILY_DATA_ORCHESTRATOR_EFFECTIVE_LIQUIDITY_OVERLAY_V10','version':'2026-10-13-usd-bank-credit-ready','base_overlay_ready':21,'base_overlay_pending':5,'ready':22,'pending':4,'total':26,'runtime_mutated':False,'publication_performed':False}
 print(json.dumps(d,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
