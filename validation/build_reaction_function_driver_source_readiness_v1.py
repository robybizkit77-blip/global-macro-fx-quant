#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/'validation/DASHBOARD_REACTION_FUNCTION_CONTRACT_V2_2026-10-07.json'
PROFILE=ROOT/'validation/CURRENT_CANONICAL_CURRENCY_MACRO_PROFILE_V2_2026-10-07.json'
REG=ROOT/'validation/MACRO_SOURCE_RELEASE_REGISTRY_V1_2026-10-07.json'
NZD=ROOT/'validation/NZD_RBNZ_REACTION_FEASIBILITY_V1_2026-10-07.json'
CHF=ROOT/'validation/CHF_REACTION_READINESS_V1_2026-10-07.json'
CHF_SPEC=ROOT/'validation/CHF_SNB_REACTION_FUNCTION_SPEC_V1_2026-10-07.md'
OUT=ROOT/'validation/REACTION_FUNCTION_DRIVER_SOURCE_READINESS_V1_2026-10-07.json'

DIRECT={'growth':'growth','growth_context':'growth','labour':'labour','labour_context':'labour','inflation':'inflation','headline_inflation':'inflation'}

def registry_index(reg):
    return {(r['currency'],r['dimension']):r for r in reg['series']}

def direct_row(ccy,driver,block,idx):
    dim='labour' if block=='labour' else 'inflation' if block=='inflation' else 'growth'
    src=idx.get((ccy,dim))
    # Growth blocks are canonical-profile available but not covered by the current inflation+labour source registry.
    if src is None:
        return {
          'driver':driver,'status':'AVAILABLE_CANONICAL_PROFILE_SOURCE_REGISTRY_INCOMPLETE','local_path':'validation/CURRENT_CANONICAL_CURRENCY_MACRO_PROFILE_V2_2026-10-07.json',
          'profile_block':block,'source_series':None,'source_provider':None,'historical_pit_status':'NOT_ASSESSED_IN_CORE_RELEASE_REGISTRY',
          'live_ingress_status':'NOT_ASSESSED_IN_CORE_RELEASE_REGISTRY','note':'Canonical profile block exists; exact upstream release adapter is outside the current inflation+labour source registry.'
        }
    pit=src['historical_pit']['status']
    live='DAILY_READY' if src['status']=='DAILY_READY' else src['status']
    status='AVAILABLE_RESEARCH_PIT' if pit=='PASS_RESEARCH_PIT' else ('WITHHELD_SOURCE_ACCESS_GAP' if 'WITHHELD' in pit else 'AVAILABLE_RUNTIME_NOT_DAILY_READY')
    return {
      'driver':driver,'status':status,'local_path':'validation/CURRENT_CANONICAL_CURRENCY_MACRO_PROFILE_V2_2026-10-07.json',
      'profile_block':block,'source_series':src['series_id'],'source_provider':src['source'],'runtime_as_of':src.get('runtime_as_of'),
      'historical_pit_status':pit,'historical_pit_artifact':src['historical_pit'].get('artifact'),'live_ingress_status':live,
      'note':'Runtime/profile availability is kept separate from historical PIT quality and live ingress readiness.'
    }

def distinct_row(ccy,driver):
    # No fabricated proxies. Only exact branch-local source evidence is surfaced.
    if ccy=='NZD' and driver=='slack':
        return {
          'driver':driver,'status':'WITHHELD_SOURCE_ACCESS_GAP','local_path':'validation/NZD_RBNZ_REACTION_FEASIBILITY_V1_2026-10-07.json',
          'source_series':'Stats NZ Labour Market Statistics / unemployment as predeclared slack state','source_provider':'Stats NZ',
          'historical_pit_status':'PUBLIC_BROWSER_VERIFIED_AUTOMATION_BLOCKED','live_ingress_status':'WITHHELD_SOURCE_ACCESS_GAP',
          'note':'Reaction feasibility predeclares latest-known unemployment as slack input, but reproducible first-release materialization is blocked.'
        }
    if ccy=='CHF' and driver=='labour':
        return {
          'driver':driver,'status':'WITHHELD_VINTAGE_REQUIRED','local_path':'validation/CHF_REACTION_READINESS_V1_2026-10-07.json',
          'source_series':'CH_UNEMP_RATE / SECO seasonally adjusted unemployment','source_provider':'SECO via SNB data portal',
          'historical_pit_status':'WITHHELD_VINTAGE_REQUIRED','live_ingress_status':'SOURCE_ADAPTER_REQUIRED',
          'note':'Current SA history is recomputed; archived first-release vintages are required.'
        }
    if ccy=='CHF' and driver=='exchange_rate_channel':
        return {
          'driver':driver,'status':'PARTIAL_RESEARCH_SOURCE_AVAILABLE','local_path':'validation/CHF_SNB_REACTION_FUNCTION_SPEC_V1_2026-10-07.md',
          'supporting_artifacts':['validation/CHF_SNB_FX_TRANSACTIONS_V1_2026-10-07.json'],
          'source_series':'CHF G8 basket pressure + official SNB FX transaction volumes','source_provider':'ECB price matrix + SNB',
          'historical_pit_status':'FX_TRANSACTIONS_PASS_OFFICIAL_QUARTERLY_PIT_POLICY__PRICE_CAUSAL_TIMING_REQUIRED','live_ingress_status':'NOT_PROMOTED',
          'note':'FX channel is not sight deposits. Official FX transactions plus contemporaneous CHF pressure are required; no single scalar proxy is allowed.'
        }
    if ccy=='CHF' and driver in {'inflation_forecast','economic_conditions'}:
        return {
          'driver':driver,'status':'WITHHELD_NO_EXACT_MATERIALIZED_DRIVER','local_path':'validation/CHF_SNB_REACTION_FUNCTION_SPEC_V1_2026-10-07.md',
          'source_series':None,'source_provider':'SNB/SFSO/SECO conceptual source family only',
          'historical_pit_status':'NOT_MATERIALIZED_AS_EXACT_DRIVER','live_ingress_status':'NOT_READY',
          'note':'Dedicated CHF spec defines the causal role, but this exact higher-level driver is not materialized as a reproducible branch-local series.'
        }
    # EUR/GBP/JPY wages/services and CAD core inflation: theory/evidence may exist, but no exact materialized branch-local driver file was found.
    return {
      'driver':driver,'status':'WITHHELD_NO_EXACT_REPO_SOURCE_ARTIFACT','local_path':None,'source_series':None,'source_provider':None,
      'historical_pit_status':'NOT_VERIFIABLE_FROM_CURRENT_BRANCH_ARTIFACTS','live_ingress_status':'NOT_READY',
      'note':'Required by the reaction contract, but no exact branch-local materialized source artifact is available. Narrative/evidence labels do not count as a source series.'
    }

def main():
    contract=json.loads(CONTRACT.read_text())['currency_contracts']
    profile=json.loads(PROFILE.read_text())['currencies']
    reg=json.loads(REG.read_text())
    idx=registry_index(reg)
    rows={}
    for ccy,spec in contract.items():
        drivers=[]
        for d in spec['macro_drivers']:
            block=DIRECT.get(d)
            if block and block in profile[ccy]['blocks']:
                drivers.append(direct_row(ccy,d,block,idx))
            else:
                drivers.append(distinct_row(ccy,d))
        exact_ready=sum(1 for r in drivers if r['status'] in {'AVAILABLE_RESEARCH_PIT','AVAILABLE_RUNTIME_NOT_DAILY_READY','AVAILABLE_CANONICAL_PROFILE_SOURCE_REGISTRY_INCOMPLETE'})
        blocked=sum(1 for r in drivers if r['status'].startswith('WITHHELD'))
        partial=sum(1 for r in drivers if r['status'].startswith('PARTIAL'))
        rows[ccy]={
          'currency':ccy,'central_bank':spec['central_bank'],'reaction_function':spec['reaction_function'],'evidence_status':spec['evidence_status'],
          'drivers':drivers,'driver_count':len(drivers),'available_or_runtime_count':exact_ready,'partial_count':partial,'withheld_count':blocked,
          'reaction_input_status':'WITHHELD_MISSING_EXACT_DRIVER' if blocked else ('PARTIAL_SOURCE_CHAIN' if partial else 'SOURCE_FAMILIES_MAPPED'),
          'cb_implication':'WITHHELD_NOT_COMPUTED','production_gate':False
        }
    out={
      'schema':'GMFQ_REACTION_FUNCTION_DRIVER_SOURCE_READINESS_V1','status':'RESEARCH_ONLY_SOURCE_MAP__NO_CB_IMPLICATION',
      'purpose':'Map every reaction-function driver to an exact branch-local source/provenance status. Runtime availability, historical PIT quality and live-ingress readiness are separate. Missing drivers are never proxied or treated as neutral.',
      'global_live_ingress':{'core_registry_status':reg['status'],'core_series':reg['summary']['core_series'],'daily_ready':reg['summary']['daily_ready']},
      'currencies':rows,
      'guards':{'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False,'production_promotion':False,'predictive_claim':False,'proxy_substitution':False,'computes_cb_implication':False,'missing_as_neutral':False}
    }
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'status':'PASS','currency_status':{c:r['reaction_input_status'] for c,r in rows.items()},'daily_ready':reg['summary']['daily_ready']}))

if __name__=='__main__': main()
