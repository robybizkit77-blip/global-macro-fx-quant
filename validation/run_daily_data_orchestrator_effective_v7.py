#!/usr/bin/env python3
import json,subprocess,sys
from pathlib import Path
BASE=Path('validation/run_daily_data_orchestrator_effective_v6.py')
OVERRIDE=Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_AUD_BROAD_MONEY_REVISION_AWARE_V1_2026-10-13.json')
POLICY='validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json'

def main():
    p=subprocess.run([sys.executable,str(BASE)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if p.returncode: raise SystemExit(p.stdout)
    d=json.loads(p.stdout); o=json.loads(OVERRIDE.read_text(encoding='utf-8')); r=o['effective_row']; delta=o['coverage_delta']
    if o.get('schema')!='GMFQ_LIQUIDITY_POLICY_OVERRIDE_V1' or o['supersedes']!={'policy':POLICY,'subseries':'AUD.money'}: raise SystemExit('invalid AUD.money override')
    checks=[r.get('automation_ready') is True,r.get('controlled_apply_proven') is True,r.get('revision_aware_append_only') is True,r.get('historical_runtime_values_frozen') is True,r.get('new_observation_transform')=='ROUND_1DP',r.get('series_key')=='DMABMS',r.get('historical_overlap_count')==127,r.get('historical_rounded_1dp_match_count')==48,r.get('historical_current_vintage_mismatch_count_after_1dp')==79,r.get('official_last_date')=='2026-08',abs(float(r.get('official_last_value'))-3510.1)<1e-9,int(delta.get('automation_ready_subseries',0))==1,int(delta.get('mapping_pending_subseries',0))==-1]
    if not all(checks): raise SystemExit('AUD.money override proof drifted')
    if not Path(r['collector']).exists() or not Path(r['applier']).exists(): raise SystemExit('AUD.money collector/applier missing')
    liq=d['lanes']['LIQUIDITY']
    if liq.get('automation_ready_subseries')!=18 or liq.get('mapping_pending_subseries')!=8: raise SystemExit(f'unexpected V6 coverage {liq}')
    liq['verified_subseries']=19; liq['unresolved_subseries']=7; liq['automation_ready_subseries']=19; liq['mapping_pending_subseries']=7
    liq.setdefault('source_policy_overrides',[]).append(str(OVERRIDE))
    liq.update({'aud_money_automation_ready':True,'aud_money_controlled_apply_proven':True,'aud_money_revision_aware_append_only':True,'aud_money_series_key':'DMABMS','aud_money_collector':r['collector'],'aud_money_applier':r['applier'],'aud_money_apply_proof_run_id':r['apply_proof_run_id'],'aud_money_official_tail':{'date':r['official_last_date'],'value':r['official_last_value']}})
    liq['reason']='26/26 official source families mapped; 19/26 automation-ready after AUD broad-money revision-aware append-only promotion. Remaining 7 stay fail-closed.'
    d['effective_liquidity_overlay_v7']={'schema':'GMFQ_DAILY_DATA_ORCHESTRATOR_EFFECTIVE_LIQUIDITY_OVERLAY_V7','version':'2026-10-13-aud-money-ready','base_overlay_ready':18,'base_overlay_pending':8,'ready':19,'pending':7,'total':26,'runtime_mutated':False,'publication_performed':False}
    print(json.dumps(d,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
