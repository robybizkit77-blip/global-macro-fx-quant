#!/usr/bin/env python3
import json
from pathlib import Path

DISP=Path('validation/CURRENCY_CROSS_DISPERSION_V1_2026-10-07.json')
CHG=Path('validation/CURRENCY_WHAT_CHANGED_V1_2026-10-07.json')
EVID=Path('validation/CENTRAL_BANK_REACTION_FUNCTION_EVIDENCE_MAP_V3_2026-10-07.json')
OUT=Path('validation/CURRENCY_COMPACT_PAYLOAD_V1_2026-10-07.json')

d=json.loads(DISP.read_text())
w=json.loads(CHG.read_text())
e=json.loads(EVID.read_text())

def macro_read(m):
    f,o,x=m['favored'],m['opposed'],m['mixed']
    if f>o: return 'PREVALENZA_FAVOREVOLE'
    if o>f: return 'PREVALENZA_SFAVOREVOLE'
    if f==o and f>0: return 'EQUILIBRIO_RELATIVO'
    return 'MISTO'

def transmission_read(t):
    clean=t.get('TRANSMISSION_CLEAN',0)
    partial=t.get('TRANSMISSION_PARTIAL',0)
    div=t.get('TRANSMISSION_DIVERGENT',0)
    wh=t.get('TRANSMISSION_WITHHELD',0)
    if div>=4: return 'DIVERGENZA_DIFFUSA'
    if clean>=2 and div==0: return 'TRASMISSIONE_PIU_COERENTE'
    if clean+partial>=4 and div<=1: return 'CONFERME_PREVALENTI'
    if wh>=4: return 'POCA_VISIBILITA'
    return 'QUADRO_MISTO'

out={
  'schema':'GMFQ_CURRENCY_COMPACT_PAYLOAD_V1',
  'status':'RESEARCH_ONLY_UI_READY_NOT_PROMOTED',
  'purpose':'Minimal currency-level payload for a future compact dashboard. Counts first; no universal score and no absolute bias override.',
  'fields':['macro_relative','transmission','robustness','what_changed','historical_evidence'],
  'currencies':{},
  'guards':{
    'changes_engine_rules':False,
    'changes_live_data':False,
    'changes_oos_baseline':False,
    'production_promotion':False,
    'creates_universal_score':False,
    'overrides_macro_bias':False,
    'predictive_claim':False,
  }
}
for c in sorted(d['currencies']):
    x=d['currencies'][c]
    m=x['macro_relative']; t=x['transmission_states']; r=x['robustness']
    out['currencies'][c]={
      'currency':c,
      'cross_count':7,
      'macro_relative':{'read':macro_read(m),'favored':m['favored'],'opposed':m['opposed'],'mixed':m['mixed']},
      'transmission':{'read':transmission_read(t),'clean':t.get('TRANSMISSION_CLEAN',0),'partial':t.get('TRANSMISSION_PARTIAL',0),'divergent':t.get('TRANSMISSION_DIVERGENT',0),'withheld':t.get('TRANSMISSION_WITHHELD',0)},
      'robustness':{'robust':r.get('ROBUST_ACROSS_RULES',0),'rule_sensitive':r.get('RULE_SENSITIVE',0)},
      'what_changed':w['currencies'][c]['label'],
      'historical_evidence':e['currencies'][c]['evidence_status'],
      'production_rule':e['currencies'][c]['production_rule'],
    }
OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print('BUILT_CURRENCY_COMPACT_PAYLOAD_V1')
