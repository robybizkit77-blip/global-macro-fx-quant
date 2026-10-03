#!/usr/bin/env python3
import json
from pathlib import Path

SRC=Path('validation/PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1_2026-10-02.json')
OUT=Path('validation/CAD_TURNING_TWO_CHECKPOINT_CONFIRMATION_AUDIT_2026-10-03.json')
rows=json.loads(SRC.read_text())['comparisons']

# We study first-release turning states only at checkpoints where PIT and revised disagree
# about turning. A turning is "persistent" if first-release turning is still active at t+1.
# Then test whether Macro polarity changes relative to t within t+1 or t+2.
frag=[]
for i,r in enumerate(rows):
    if not r.get('macro_turning_changed'):
        continue
    if not r['first_release'].get('turning_present'):
        continue
    if i+1>=len(rows):
        continue
    tpol=r['first_release'].get('macro_polarity')
    n1=rows[i+1]
    persists=bool(n1['first_release'].get('turning_present'))
    if not persists:
        continue
    pol1=n1['first_release'].get('macro_polarity')
    changed1=(pol1!=tpol)
    changed2=False
    n2=None
    if i+2<len(rows):
        n2=rows[i+2]
        pol2=n2['first_release'].get('macro_polarity')
        changed2=(pol2!=tpol)
    frag.append({
        'checkpoint':r['checkpoint'],
        'next_checkpoint':n1['checkpoint'],
        'second_checkpoint':n2['checkpoint'] if n2 else None,
        't0_macro_polarity':tpol,
        't1_macro_polarity':pol1,
        'confirmed_by_t1':changed1,
        'confirmed_by_t2':bool(changed1 or changed2)
    })

n=len(frag)
c1=sum(x['confirmed_by_t1'] for x in frag)
c2=sum(x['confirmed_by_t2'] for x in frag)
report={
  'schema':'GMFQ_CAD_TURNING_TWO_CHECKPOINT_CONFIRMATION_AUDIT_V1',
  'engine_ref':'engine-freeze-v1-2026-10-02',
  'rules_fingerprint':'3356baf0',
  'method_note':'Among PIT-vs-revised turning disagreements where first-release turning remains active at the next union-release checkpoint, test whether first-release Macro polarity changes from the original checkpoint by t+1 or t+2. Descriptive only; no model change.',
  'totals':{
    'persistent_turning_cases':n,
    'macro_confirmation_by_t1':c1,
    'macro_confirmation_by_t1_pct':round(100*c1/n,2) if n else None,
    'macro_confirmation_by_t2':c2,
    'macro_confirmation_by_t2_pct':round(100*c2/n,2) if n else None,
    'not_confirmed_by_t2':n-c2,
    'not_confirmed_by_t2_pct':round(100*(n-c2)/n,2) if n else None
  },
  'cases':frag,
  'no_model_change':True
}
OUT.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['totals'],indent=2))
