#!/usr/bin/env python3
import json
from pathlib import Path

SRC=Path('validation/EUR_TURNING_PERSISTENCE_AUDIT_2026-10-03.json')
OUT=Path('validation/EUR_TURNING_TWO_CHECKPOINT_CONFIRMATION_AUDIT_2026-10-03.json')

data=json.loads(SRC.read_text())
cases=data['cases']
# map checkpoint -> case, where each case already contains next checkpoint state
by_cp={c['checkpoint']:c for c in cases}

persistent=[]
for c in cases:
    if not c.get('turning_persists_next'):
        continue
    next_case=by_cp.get(c['next_checkpoint'])
    if next_case is None:
        persistent.append({
            'checkpoint':c['checkpoint'],
            'next_checkpoint':c['next_checkpoint'],
            'second_checkpoint':None,
            'confirmed_by_next':bool(c.get('macro_polarity_changes_next')),
            'confirmed_by_second':False,
            'confirmed_within_two':bool(c.get('macro_polarity_changes_next')),
            'second_available':False
        })
        continue
    confirmed_next=bool(c.get('macro_polarity_changes_next'))
    confirmed_second=bool(next_case.get('macro_polarity_changes_next'))
    persistent.append({
        'checkpoint':c['checkpoint'],
        'next_checkpoint':c['next_checkpoint'],
        'second_checkpoint':next_case['next_checkpoint'],
        'confirmed_by_next':confirmed_next,
        'confirmed_by_second':confirmed_second,
        'confirmed_within_two':bool(confirmed_next or confirmed_second),
        'second_available':True
    })

usable=[x for x in persistent if x['second_available']]
n=len(usable)
next_n=sum(x['confirmed_by_next'] for x in usable)
within_n=sum(x['confirmed_within_two'] for x in usable)
report={
  'schema':'GMFQ_EUR_TURNING_TWO_CHECKPOINT_CONFIRMATION_AUDIT_V1',
  'engine_ref':'engine-freeze-v1-2026-10-02',
  'rules_fingerprint':'3356baf0',
  'source':str(SRC),
  'summary':{
    'persistent_turning_cases_total':len(persistent),
    'persistent_turning_cases_with_second_checkpoint':n,
    'confirmed_by_next_checkpoint':next_n,
    'confirmed_by_next_checkpoint_pct':round(100*next_n/n,2) if n else None,
    'confirmed_within_two_checkpoints':within_n,
    'confirmed_within_two_checkpoints_pct':round(100*within_n/n,2) if n else None,
    'not_confirmed_within_two_checkpoints':n-within_n,
    'not_confirmed_within_two_checkpoints_pct':round(100*(n-within_n)/n,2) if n else None
  },
  'cases':persistent,
  'limitations':[
    'EUR PIT coverage remains partial: Retail volume and negotiated wages are withheld and excluded.',
    'This reuses the canonical EUR turning persistence audit and measures confirmation timing only.',
    'Descriptive validation only; not a trading backtest.'
  ],
  'interpretation_guardrail':'Do not alter weights, thresholds, or turning rules from this partial EUR PIT sample.',
  'no_model_change':True
}
OUT.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['summary'],indent=2))
