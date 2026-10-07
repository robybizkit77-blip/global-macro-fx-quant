#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROFILE=ROOT/'validation/CURRENT_CANONICAL_CURRENCY_MACRO_PROFILE_V2_2026-10-07.json'
CONTRACT=ROOT/'validation/DASHBOARD_REACTION_FUNCTION_CONTRACT_V2_2026-10-07.json'
OUT=ROOT/'validation/MACRO_TO_REACTION_INPUT_READINESS_V1_2026-10-07.json'

# Strict semantic mappings only. No proxy substitution.
DIRECT={
 'growth':'growth','growth_context':'growth','labour':'labour','labour_context':'labour',
 'inflation':'inflation','headline_inflation':'inflation'
}
# These require distinct source families and are intentionally not synthesized from generic blocks.
DISTINCT={'wages','services_inflation','core_inflation','slack','inflation_forecast','economic_conditions','exchange_rate_channel'}

def main():
    p=json.loads(PROFILE.read_text())['currencies']
    c=json.loads(CONTRACT.read_text())['currency_contracts']
    rows={}
    for ccy in sorted(c):
        spec=c[ccy]; available=set(p[ccy]['blocks'])
        mapped=[]; missing=[]
        for drv in spec['macro_drivers']:
            src=DIRECT.get(drv)
            if src and src in available:
                mapped.append({'driver':drv,'profile_block':src,'mapping':'DIRECT_CANONICAL'})
            else:
                missing.append({'driver':drv,'reason':'DISTINCT_SOURCE_REQUIRED' if drv in DISTINCT else 'NO_STRICT_MAPPING'})
        evidence=spec['evidence_status']
        if evidence.startswith('WITHHELD'):
            readiness='WITHHELD_RESEARCH_EVIDENCE'
        elif not missing:
            readiness='FULL_PROFILE_INPUT_COVERAGE'
        else:
            readiness='PARTIAL_PROFILE_INPUT_COVERAGE'
        rows[ccy]={
          'currency':ccy,'central_bank':spec['central_bank'],'reaction_function':spec['reaction_function'],
          'evidence_status':evidence,'required_macro_drivers':spec['macro_drivers'],
          'direct_profile_inputs':mapped,'missing_distinct_inputs':missing,'readiness':readiness,
          'cb_implication':'WITHHELD_NOT_COMPUTED_BY_READINESS_LAYER',
          'production_gate':False
        }
    out={
      'schema':'GMFQ_MACRO_TO_REACTION_INPUT_READINESS_V1',
      'status':'RESEARCH_ONLY_INPUT_COVERAGE__NO_CB_IMPLICATION',
      'purpose':'Show which canonical Macro-profile blocks can feed each currency-specific reaction function directly and which distinct source families are still required. No proxy substitution and no policy implication is computed.',
      'currencies':rows,
      'guards':{
        'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False,
        'production_promotion':False,'predictive_claim':False,'proxy_substitution':False,
        'computes_cb_implication':False,'universal_score':False
      }
    }
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'status':'PASS','readiness':{k:v['readiness'] for k,v in rows.items()}}))

if __name__=='__main__': main()
