#!/usr/bin/env python3
"""Build EUR CB-pricing activation candidate from official Eurex FST3 history."""
from __future__ import annotations
import argparse,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
META=ROOT/'validation'/'cb_pricing'/'EUR_ECB_POLICY_METADATA_2026-10-15.json'

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
    s=json.loads(a.snapshot.read_text(encoding='utf-8')); m=json.loads(META.read_text(encoding='utf-8'))
    if s.get('schema')!='GMFQ_CB_PRICING_SOURCE_SNAPSHOT_V1' or s.get('currency')!='EUR': raise SystemExit('invalid EUR snapshot')
    req=('official_source','direct_settlements','no_interpolation','homogeneous_contracts','current_real','previous_real','week_real')
    if not all(s.get('validation',{}).get(k) is True for k in req): raise SystemExit('EUR snapshot validation incomplete')
    if s.get('source')!='Eurex · Three-Month Euro STR Futures (FST3)': raise SystemExit('unexpected EUR source')
    if m.get('schema')!='GMFQ_CB_POLICY_METADATA_V1' or m.get('currency')!='EUR': raise SystemExit('invalid ECB policy metadata')
    if not all(m.get('validation',{}).get(k) is True for k in ('official_source','policy_rate_validated','meeting_path_validated')): raise SystemExit('ECB policy metadata incomplete')
    policy=float(m['policy_rate']); meetings=m['meeting_path']; h={}
    for k in ('3m','6m','12m'):
        rate=float(s['observations']['current'][k]); h[k]={'rate':rate,'change_1d_bp':float(s['change_1d_bp'][k]),'change_1w_bp':float(s['change_1w_bp'][k]),'policy_delta_bp':round((rate-policy)*100,4)}
    c={'schema':'GMFQ_CB_PRICING_CANDIDATE_V1','currency':'EUR','status':'READY_FOR_CONTROLLED_ACTIVATION_PROOF','as_of':s['as_of'],'source':s['source'],'source_url':s['source_url'],'instrument':s['instrument'],'quotation':s['quotation'],'policy_rate':policy,'meeting_path':meetings,'contract_mapping':s['contract_mapping'],'horizons':h,
       'cuts_hikes_priced':{f'{k}_bp':h[k]['policy_delta_bp'] for k in h},'direction':classify({k:h[k]['policy_delta_bp'] for k in h}),'change_direction_1d':classify(s['change_1d_bp']),'change_direction_1w':classify(s['change_1w_bp']),'observations':s['observations'],
       'validation':{'source_validated':True,'asof_validated':True,'meeting_path_validated':True,'policy_rate_validated':True,'changes_validated':True,'current_real':True,'previous_real':True,'week_real':True,'no_interpolation':True,'homogeneous_contracts':True,'controlled_activation_only':True,'runtime_mutated':False,'payload_mutated':False,'weekly_reference_note':f"1W uses official Eurex session {s['observations']['weekly_reference']['date']} versus {s['as_of']} under the >=5-calendar-day rule."},
       'provenance':{'collector':'validation/cb_pricing/collect_eur_eurex_fst3.py','method':'Direct official Eurex FST3 daily settlement prices transformed as 100 minus settlement; fixed Dec-26/Mar-27/Sep-27 quarterly contracts; no interpolation.','request_urls':s['provenance'],'weekly_reference_rule':s['validation']['weekly_reference_rule'],'policy_metadata':'validation/cb_pricing/EUR_ECB_POLICY_METADATA_2026-10-15.json'}}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(c,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); print(json.dumps(c,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
