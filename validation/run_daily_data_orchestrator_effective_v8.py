#!/usr/bin/env python3
import json,subprocess,sys
from pathlib import Path
BASE=Path('validation/run_daily_data_orchestrator_effective_v7.py')
OVERRIDE=Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_EUR_M3_REVISION_AWARE_V1_2026-10-13.json')
POLICY='validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json'

def main():
    p=subprocess.run([sys.executable,str(BASE)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if p.returncode: raise SystemExit(p.stdout)
    d=json.loads(p.stdout); o=json.loads(OVERRIDE.read_text(encoding='utf-8')); r=o['effective_row']; delta=o['coverage_delta']
    if o.get('schema')!='GMFQ_LIQUIDITY_POLICY_OVERRIDE_V1' or o['supersedes']!={'policy':POLICY,'subseries':'EUR.money'}: raise SystemExit('invalid EUR.money override')
    checks=[r.get('automation_ready') is True,r.get('controlled_apply_proven') is True,r.get('revision_aware_append_only') is True,r.get('historical_runtime_values_frozen') is True,r.get('identity_transform_for_new_observations') is True,r.get('series_key')=='BSI.M.U2.Y.V.M30.X.1.U2.2300.Z01.E',r.get('historical_overlap_count')==32,r.get('historical_exact_match_count')==29,r.get('historical_current_vintage_revision_mismatch_count')==3,r.get('real_append_replay_proven') is True,r.get('replay_appended_date')=='2026-08',abs(float(r.get('replay_appended_value'))-17646463.0)<1e-9,int(delta.get('automation_ready_subseries',0))==1,int(delta.get('mapping_pending_subseries',0))==-1]
    if not all(checks): raise SystemExit('EUR.money override proof drifted')
    if not Path(r['collector']).exists() or not Path(r['applier']).exists(): raise SystemExit('EUR.money collector/applier missing')
    liq=d['lanes']['LIQUIDITY']
    if liq.get('automation_ready_subseries')!=19 or liq.get('mapping_pending_subseries')!=7: raise SystemExit(f'unexpected V7 coverage {liq}')
    liq['verified_subseries']=20; liq['unresolved_subseries']=6; liq['automation_ready_subseries']=20; liq['mapping_pending_subseries']=6
    liq.setdefault('source_policy_overrides',[]).append(str(OVERRIDE))
    liq.update({'eur_m3_automation_ready':True,'eur_m3_controlled_apply_proven':True,'eur_m3_revision_aware_append_only':True,'eur_m3_series_key':r['series_key'],'eur_m3_collector':r['collector'],'eur_m3_applier':r['applier'],'eur_m3_apply_proof_run_id':r['apply_proof_run_id'],'eur_m3_real_append_replay_proven':True,'eur_m3_official_tail':{'date':r['official_last_date'],'value':r['official_last_value']}})
    liq['reason']='26/26 official source families mapped; 20/26 automation-ready after EUR M3 revision-aware append-only promotion. Remaining 6 stay fail-closed.'
    d['effective_liquidity_overlay_v8']={'schema':'GMFQ_DAILY_DATA_ORCHESTRATOR_EFFECTIVE_LIQUIDITY_OVERLAY_V8','version':'2026-10-13-eur-m3-revision-aware-ready','base_overlay_ready':19,'base_overlay_pending':7,'ready':20,'pending':6,'total':26,'runtime_mutated':False,'publication_performed':False}
    print(json.dumps(d,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
