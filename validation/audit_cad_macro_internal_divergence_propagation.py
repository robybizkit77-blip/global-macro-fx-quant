#!/usr/bin/env python3
import json
from pathlib import Path

MACRO=Path('validation/PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1_2026-10-02.json')
OUT=Path('validation/CAD_MACRO_INTERNAL_DIVERGENCE_PROPAGATION_AUDIT_2026-10-03.json')

rows=json.loads(MACRO.read_text())['comparisons']

norm=[]
for m in rows:
    gd=bool(m.get('growth_direction_changed'))
    ld=bool(m.get('labour_direction_changed'))
    mf=bool(m.get('macro_polarity_changed'))
    mt=bool(m.get('macro_turning_changed'))
    norm.append({'checkpoint':m['checkpoint'],'growth_fragile':gd,'labour_fragile':ld,'macro_flip':mf,'macro_turning_change':mt})

def stats(pred):
    sub=[r for r in norm if pred(r)]
    flips=sum(r['macro_flip'] for r in sub)
    turns=sum(r['macro_turning_change'] for r in sub)
    return {
      'n':len(sub),'macro_flips':flips,
      'macro_flip_pct':round(100*flips/len(sub),2) if sub else None,
      'macro_turning_changes':turns,
      'macro_turning_change_pct':round(100*turns/len(sub),2) if sub else None
    }

report={
 'schema':'GMFQ_CAD_MACRO_INTERNAL_DIVERGENCE_PROPAGATION_AUDIT_V2',
 'engine_ref':'engine-freeze-v1-2026-10-02',
 'rules_fingerprint':'3356baf0',
 'method_note':'Uses the canonical CAD Macro replay flags growth_direction_changed, labour_direction_changed, macro_polarity_changed and macro_turning_changed at each union-release checkpoint. Descriptive only; no causal inference and no model change.',
 'totals':{
   'checkpoints':len(norm),
   'macro_flips':sum(r['macro_flip'] for r in norm),
   'macro_turning_changes':sum(r['macro_turning_change'] for r in norm)
 },
 'groups':{
   'growth_fragile_any':stats(lambda r:r['growth_fragile']),
   'labour_fragile_any':stats(lambda r:r['labour_fragile']),
   'growth_only_fragile':stats(lambda r:r['growth_fragile'] and not r['labour_fragile']),
   'labour_only_fragile':stats(lambda r:r['labour_fragile'] and not r['growth_fragile']),
   'both_fragile':stats(lambda r:r['growth_fragile'] and r['labour_fragile']),
   'neither_fragile':stats(lambda r:not r['growth_fragile'] and not r['labour_fragile'])
 },
 'examples_macro_flip_with_growth_fragility':[r['checkpoint'] for r in norm if r['growth_fragile'] and r['macro_flip']][:20],
 'examples_macro_flip_with_labour_fragility':[r['checkpoint'] for r in norm if r['labour_fragile'] and r['macro_flip']][:20],
 'no_model_change':True
}
OUT.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
