#!/usr/bin/env python3
import json
from pathlib import Path
from collections import Counter

SRC=Path('validation/DASHBOARD_PAIR_RENDER_PAYLOAD_V1_2026-10-07.json')
OUT=Path('validation/CURRENCY_CROSS_DISPERSION_V1_2026-10-07.json')
CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']

src=json.loads(SRC.read_text())
pairs=src['pairs']
out={
  'schema':'GMFQ_CURRENCY_CROSS_DISPERSION_V1',
  'status':'RESEARCH_ONLY_DESCRIPTIVE_NOT_PROMOTED',
  'created_at':'2026-10-07',
  'purpose':'Compact currency-level summary derived from each currency\'s seven G8 crosses. No score, no bias inversion, no predictive claim.',
  'currencies':{},
  'guards':{
    'changes_engine_rules':False,
    'changes_live_data':False,
    'changes_oos_baseline':False,
    'production_promotion':False,
    'creates_universal_score':False
  }
}

for ccy in CCYS:
    rows=[]
    macro_fav=macro_opp=macro_mixed=0
    states=Counter(); robust=Counter(); layers={'central_bank':Counter(),'front_end_rates':Counter(),'price':Counter()}
    for pair,p in pairs.items():
        a,b=pair.split('/')
        if ccy not in (a,b):
            continue
        rows.append(pair)
        anchor=p.get('macro_anchor')
        if anchor=='MIXED' or anchor not in ('A','B'):
            macro_mixed+=1
        else:
            fav=a if anchor=='A' else b
            if fav==ccy: macro_fav+=1
            else: macro_opp+=1
        states[p.get('state','UNKNOWN')]+=1
        robust[p.get('robustness_badge','UNKNOWN')]+=1
        for k in layers:
            layers[k][p.get('layers',{}).get(k,{}).get('status','UNKNOWN')]+=1
    assert len(rows)==7, (ccy,rows)
    out['currencies'][ccy]={
      'cross_count':7,
      'macro_relative':{'favored':macro_fav,'opposed':macro_opp,'mixed':macro_mixed},
      'transmission_states':dict(states),
      'robustness':dict(robust),
      'layer_dispersion':{k:dict(v) for k,v in layers.items()},
      'crosses':sorted(rows),
      'display_contract':{
        'show_counts_only':True,
        'do_not_convert_to_score':True,
        'do_not_call_absolute_bias':True,
        'suggested_compact_fields':['macro_relative','transmission_states','robustness']
      }
    }

OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print('BUILT',OUT)
