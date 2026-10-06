#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FED=ROOT/'validation/USD_FED_REACTION_ROBUSTNESS_V1_2026-10-06.json'
ECB=ROOT/'validation/EUR_REACTION_FUNCTION_DIAGNOSTIC_V2_2026-10-06.json'
OUT=ROOT/'validation/FED_VS_ECB_REACTION_FUNCTION_COMPARISON_V1_2026-10-06.json'
fed=json.loads(FED.read_text(encoding='utf-8')); ecb=json.loads(ECB.read_text(encoding='utf-8'))
fd=fed['state_robustness']['BOTH_DOVISH']; fh=fed['state_robustness']['BOTH_HAWKISH']
res={
 'schema':'GMFQ_FED_VS_ECB_REACTION_FUNCTION_COMPARISON_V1','status':'PASS','created_at':'2026-10-06',
 'purpose':'Cross-country methodological comparison only. Demonstrates whether bank-specific reaction-function states behave differently under PIT-safe inputs. No production promotion.',
 'engine_baseline':{'commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0','modified':False},
 'fed':{
  'mandate':'DUAL_MANDATE',
  'state_definition':'Labour + CPI inflation as separate frozen-style blocks; 2Y observed as transmission state, not gate.',
  'both_dovish_full_20d':fd['full_sample']['20d'],
  'both_dovish_oos_20d':fd['pooled_oos']['20d'],
  'both_hawkish_full_20d':fh['full_sample']['20d'],
  'both_hawkish_oos_20d':fh['pooled_oos']['20d'],
  'conclusion':'BOTH_DOVISH shows materially stronger and more persistent USD weakness than the mirror-image BOTH_HAWKISH state shows USD strength. Reaction is asymmetric.',
 },
 'ecb':{
  'mandate':'PRICE_STABILITY_PRIMARY',
  'state_definition':'Negotiated-wage new-sign regime entries as policy-relevant domestic-inflation mediator; same exact cohort used for all/2Y-aligned/2Y-conflict; 2Y observed over fixed 5-market-day window.',
  'all_same_timing_20d':ecb['all_same_timing']['stats']['20d'],
  'aligned_20d':ecb['aligned']['stats']['20d'],
  'conflict_20d':ecb['conflict']['stats']['20d'],
  'pooled_oos_20d':ecb['walk_forward']['pooled_oos']['20d'],
  'counts':ecb['counts'],
  'conclusion':'Wage mediator alone is not robust OOS. Full-sample 2Y alignment looks better than conflict on the exact same cohort, but samples are too small and pooled OOS of the base cohort remains weak; do not promote a 2Y confirmation rule.'
 },
 'cross_country_findings':[
  'The same generic macro-to-rates confirmation rule does not generalize across Fed and ECB.',
  'Fed dual-mandate downside state is empirically more informative than its hawkish mirror state in this V1 sample.',
  'ECB evidence is more consistent with wages/services as inflation-transmission mediators than with labour as a direct Fed-style driver.',
  'Front-end rates should remain an observed repricing layer, not a universal binary gate.',
  'Bank-specific reaction functions are justified as architecture, but only Fed BOTH_DOVISH is currently a serious OOS candidate; ECB remains diagnostic.'
 ],
 'guardrails':['no parameter fitting','no threshold tuning','no cross-country reweighting','no production rule changes','small ECB sample explicitly retained','PCE still withheld from Fed V1','engine/live_data untouched'],
 'promotion_status':{'FED_BOTH_DOVISH':'CANDIDATE_REQUIRES_FORWARD_OOS','FED_BOTH_HAWKISH':'DESCRIPTIVE_NOT_LOCKED','ECB_WAGES_2Y':'DIAGNOSTIC_NOT_LOCKED'},
 'changes_engine_rules':False,'changes_live_data':False
}
OUT.write_text(json.dumps(res,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,indent=2))
