#!/usr/bin/env python3
from __future__ import annotations
import json, urllib.request, statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COMMON=ROOT/'validation/TRANSMISSION_CONVICTION_COMMON_CORE_REPLAY_V1_2026-10-07.json'
OUT=ROOT/'validation/TRANSMISSION_REGIME_ATTRIBUTION_V1_2026-10-07.json'
BASE='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/e9862cba3f748da121e34d12f8eb64144568d46c/validation/'
ENGINE='ff52198a75cc67f7dae96fc2bbf65623f170791c'; FP='3356baf0'

def get(name):
    with urllib.request.urlopen(BASE+name,timeout=60) as r:return json.loads(r.read().decode())

def stat(rows):
    vals=[r['signed_20d'] for r in rows if r.get('signed_20d') is not None]
    return {'n':len(vals),'hit_rate':sum(x>0 for x in vals)/len(vals) if vals else None,'mean':sum(vals)/len(vals) if vals else None,'median':statistics.median(vals) if vals else None}

common=json.loads(COMMON.read_text())
usd=get('USD_FED_REACTION_STATE_V1_2026-10-06.json')
gbp=get('GBP_FULL_REACTION_STATE_VNEXT_V1_2026-10-06.json')
cad=get('CAD_FULL_REACTION_STATE_VNEXT_V2_2026-10-06.json')
jpy=get('JPY_REACTION_FUNCTION_REPLAY_V1_2026-10-06.json')

# Predeclared macro-coherence definitions from each currency's existing model.
# USD: dual mandate points same direction.
usd_map={r['checkpoint']: r['joint_state'] in ('LABOUR_INFLATION_BOTH_DOVISH','LABOUR_INFLATION_BOTH_HAWKISH') for r in usd['rows']}
# GBP: wages+services and labour all point same direction.
gbp_map={r['checkpoint']: r['state']=='DOMESTIC_LABOUR_ALIGNED' for r in gbp['rows']}
# CAD: frozen macro direction and both core/headline inflation layers point same way.
cad_map={r['checkpoint']: r['joint_inflation_state']=='CORE_HEADLINE_BOTH_ALIGNED' for r in cad['rows']}
# JPY common-core universe is already the frozen directional wages+CPI agreement cohort.
jpy_map={r['checkpoint']: True for r in jpy['directional_samples']}
maps={'USD':usd_map,'GBP':gbp_map,'CAD':cad_map,'JPY':jpy_map}

rows=[]
for r in common['rows']:
    m=maps[r['currency']]
    if r['checkpoint'] not in m: continue
    z=dict(r); z['macro_regime']='COHERENT' if m[r['checkpoint']] else 'OTHER'; rows.append(z)

# Same per-currency OOS convention as common-core: first 40% chronology excluded.
oos=[]
for c in ('USD','GBP','CAD','JPY'):
    rr=sorted([r for r in rows if r['currency']==c],key=lambda x:x['checkpoint'])
    cut=int(len(rr)*0.4); oos.extend(rr[cut:])

def summary(rs):
    out={}
    for regime in ('COHERENT','OTHER'):
        q=[r for r in rs if r['macro_regime']==regime]
        out[regime]={k:stat([r for r in q if r['conviction']==k]) for k in ('MEDIUM','LOW')}
        m=out[regime]['MEDIUM']; l=out[regime]['LOW']
        out[regime]['medium_gt_low_hit']=bool(m['n'] and l['n'] and m['hit_rate']>l['hit_rate'])
        out[regime]['medium_gt_low_mean']=bool(m['n'] and l['n'] and m['mean']>l['mean'])
    return out

by_currency={}
for c in ('USD','GBP','CAD','JPY'):
    rr=[r for r in oos if r['currency']==c]; by_currency[c]=summary(rr)

res={
 'schema':'GMFQ_TRANSMISSION_REGIME_ATTRIBUTION_V1','status':'PASS_DIAGNOSTIC_NOT_PROMOTED','created_at':'2026-10-07',
 'engine_baseline':{'commit':ENGINE,'rules_fingerprint':FP,'modified':False},
 'purpose':'Test whether common-core transmission confirmation works specifically inside predeclared internally coherent macro regimes; no regime mining or tuning.',
 'regime_definitions':{
   'USD':'Labour and inflation BOTH_DOVISH or BOTH_HAWKISH',
   'GBP':'DOMESTIC_LABOUR_ALIGNED only',
   'CAD':'CORE_HEADLINE_BOTH_ALIGNED relative to frozen macro polarity',
   'JPY':'existing directional wages+CPI agreement cohort; all common-core JPY rows coherent by construction'
 },
 'guardrails':['regimes defined before reading this test outcome','same common-core 5-observation post-release classification','same subsequent signed 20d outcome','same 40% chronological OOS exclusion','no threshold/window/weight tuning','no engine/live/OOS baseline changes'],
 'counts':{'rows':len(rows),'oos':len(oos),'coherent_oos':sum(r['macro_regime']=='COHERENT' for r in oos)},
 'pooled_oos':summary(oos),'oos_by_currency':by_currency,'rows':rows,
 'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False
}
OUT.write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps({'counts':res['counts'],'pooled_oos':res['pooled_oos'],'oos_by_currency':by_currency},indent=2))
