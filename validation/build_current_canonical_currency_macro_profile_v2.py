#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'live_data/sections/CERT53.json'
OUT=ROOT/'validation/CURRENT_CANONICAL_CURRENCY_MACRO_PROFILE_V2_2026-10-07.json'
CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']
BLOCKS=['growth','labour','inflation']
FIELDS=['state','momentum','direction','velocity_percentile','velocity_class','acceleration_percentile','acceleration_class','persistence','candidate_p70']

def main():
    src=json.loads(SRC.read_text(encoding='utf-8'))
    macro=src.get('macro',{})
    if set(macro)!=set(CCYS):
        raise SystemExit(f'Expected exactly G8 macro keys {CCYS}; got {sorted(macro)}')
    out={
      'schema':'GMFQ_CURRENT_CANONICAL_CURRENCY_MACRO_PROFILE_V2',
      'status':'RESEARCH_ONLY_READ_ONLY_PROFILE__NO_DIRECTIONAL_FX_VOTE',
      'source':str(SRC.relative_to(ROOT)),
      'currencies':{},
      'guards':{
        'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False,
        'production_promotion':False,'predictive_claim':False,'universal_score':False,
        'automatic_fx_direction':False,'legacy_anchor_fit':False
      }
    }
    for c in CCYS:
        m=macro[c]
        blocks=m.get('blocks',{})
        if set(blocks)!=set(BLOCKS):
            raise SystemExit(f'{c}: expected blocks {BLOCKS}; got {sorted(blocks)}')
        clean={}
        for b in BLOCKS:
            row=blocks[b]
            missing=[k for k in FIELDS if k not in row]
            if missing: raise SystemExit(f'{c}/{b}: missing {missing}')
            clean[b]={k:row[k] for k in FIELDS}
        out['currencies'][c]={
          'currency':c,
          'cycle':m.get('cycle'),
          'blocks':clean,
          'fx_directional_vote':'WITHHELD_NOT_DERIVED_AT_MACRO_PROFILE_LAYER',
          'reaction_function_status':'REQUIRED_DOWNSTREAM',
          'interpretation_note':'Profile preserves structural level and impulse separately. Inflation does not cast a direct FX vote.'
        }
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','currencies':len(out['currencies']),'output':str(OUT.relative_to(ROOT))}))

if __name__=='__main__': main()
