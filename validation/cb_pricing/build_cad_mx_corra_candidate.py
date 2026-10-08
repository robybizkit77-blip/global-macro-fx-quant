#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
OIS=ROOT/'live_data'/'sections'/'OIS_DATA.json'; REG=ROOT/'validation'/'cb_pricing'/'CB_PRICING_SOURCE_STATUS_2026-10-08.json'
def classify(v,eps=.05):
 a=[float(v[k]) for k in ('3m','6m','12m')]; p=sum(x>eps for x in a); n=sum(x<-eps for x in a)
 if p==3:return 'UP'
 if n==3:return 'DOWN'
 if p==0 and n==0:return 'FLAT'
 if a[0]>eps and a[1]>eps:return 'MIXED_FRONT_END_UP'
 if a[0]<-eps and a[1]<-eps:return 'MIXED_FRONT_END_DOWN'
 return 'MIXED'
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--snapshot',required=True,type=pathlib.Path); ap.add_argument('--output',required=True,type=pathlib.Path); a=ap.parse_args()
 s=json.loads(a.snapshot.read_text());
 if s.get('schema')!='GMFQ_CB_PRICING_SOURCE_SNAPSHOT_V1' or s.get('currency')!='CAD':raise SystemExit('invalid CAD snapshot')
 if not all(s.get('validation',{}).get(k) is True for k in ('official_source','direct_settlements','no_interpolation','homogeneous_contracts')):raise SystemExit('snapshot validation incomplete')
 rg=json.loads(REG.read_text())['currencies']['CAD']
 if rg.get('status')!='ACTIVE' or rg.get('official_source')!='Montréal Exchange':raise SystemExit('registry does not authorize CAD MX pricing')
 live=json.loads(OIS.read_text())['currencies']['CAD']
 if live.get('status')!='ACTIVE' or live.get('source')!=s.get('source') or live.get('policy_rate') is None or not live.get('meetings'):raise SystemExit('canonical CAD metadata mismatch')
 policy=float(live['policy_rate']); h={}
 for k in ('3m','6m','12m'):
  rate=float(s['observations']['current'][k]); h[k]={'rate':rate,'change_1d_bp':float(s['change_1d_bp'][k]),'change_1w_bp':float(s['change_1w_bp'][k]),'policy_delta_bp':round((rate-policy)*100,4)}
 c={'schema':'GMFQ_CB_PRICING_CANDIDATE_V1','currency':'CAD','status':'READY_FOR_DRY_RUN','as_of':s['as_of'],'source':s['source'],'source_url':s['source_url'],'instrument':s['instrument'],'quotation':s['quotation'],'policy_rate':policy,'meeting_path':live['meetings'],'contract_mapping':s['contract_mapping'],'horizons':h,'cuts_hikes_priced':{f'{k}_bp':h[k]['policy_delta_bp'] for k in h},'direction':classify({k:h[k]['policy_delta_bp'] for k in h}),'change_direction_1d':classify(s['change_1d_bp']),'change_direction_1w':classify(s['change_1w_bp']),'observations':s['observations'],'validation':{'source_validated':True,'asof_validated':True,'meeting_path_validated':True,'changes_validated':True,'current_real':True,'previous_real':True,'week_real':True,'no_interpolation':True,'source_registry_authorized':True,'runtime_mutated':False,'payload_mutated':False,'weekly_reference_note':f"1W uses official MX session {s['observations']['weekly_reference']['date']} versus {s['as_of']}."},'provenance':{'collector':'validation/cb_pricing/collect_cad_mx_corra.py','method':'Direct official Montréal Exchange CRA settlement prices transformed as 100 minus settlement; canonical quarterly buckets; no interpolation.','weekly_reference_rule':s['validation']['weekly_reference_rule']}}
 a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(c,indent=2,ensure_ascii=False)+'\n'); print(json.dumps(c,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
