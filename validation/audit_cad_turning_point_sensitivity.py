#!/usr/bin/env python3
import json
from pathlib import Path

SRC=Path('validation/PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1_2026-10-02.json')
OUT=Path('validation/CAD_TURNING_POINT_SENSITIVITY_AUDIT_2026-10-03.json')
rows=json.loads(SRC.read_text())['comparisons']
changed=[r for r in rows if r.get('macro_turning_changed')]

def count(pred):
    sub=[r for r in changed if pred(r)]
    return {'n':len(sub),'pct_of_turning_changes':round(100*len(sub)/len(changed),2) if changed else None,
            'examples':[r['checkpoint'] for r in sub][:20]}

report={
 'schema':'GMFQ_CAD_TURNING_POINT_SENSITIVITY_AUDIT_V1',
 'engine_ref':'engine-freeze-v1-2026-10-02',
 'rules_fingerprint':'3356baf0',
 'totals':{'checkpoints':len(rows),'macro_turning_changes':len(changed)},
 'decomposition':{
   'with_macro_polarity_flip':count(lambda r:r.get('macro_polarity_changed')),
   'without_macro_polarity_flip':count(lambda r:not r.get('macro_polarity_changed')),
   'with_growth_direction_change':count(lambda r:r.get('growth_direction_changed')),
   'with_labour_direction_change':count(lambda r:r.get('labour_direction_changed')),
   'with_any_block_direction_change':count(lambda r:r.get('growth_direction_changed') or r.get('labour_direction_changed')),
   'with_no_block_direction_change':count(lambda r:not r.get('growth_direction_changed') and not r.get('labour_direction_changed')),
   'with_both_block_direction_changes':count(lambda r:r.get('growth_direction_changed') and r.get('labour_direction_changed'))
 },
 'interpretation':{
   'purpose':'Separate turning-point revision sensitivity caused by true block-direction changes from timing/state changes that occur without a block-direction flip.',
   'no_model_change':True
 }
}
OUT.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
