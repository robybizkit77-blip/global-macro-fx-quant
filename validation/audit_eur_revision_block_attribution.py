#!/usr/bin/env python3
import json
from pathlib import Path

SRC=Path('validation/EUR_PIT_REVISION_SENSITIVITY_AUDIT_2026-10-03.json')
OUT=Path('validation/EUR_PIT_REVISION_BLOCK_ATTRIBUTION_2026-10-03.json')

d=json.loads(SRC.read_text())
c=d['changed_checkpoints']
g=set(c['growth']); l=set(c['labour']); m=set(c['macro_polarity']); t=set(c['macro_turning'])

def pct(n,den): return round(100*n/den,2) if den else None
cats={
 'macro_flip_growth_only': sorted(m & g - l),
 'macro_flip_labour_only': sorted(m & l - g),
 'macro_flip_both_blocks': sorted(m & g & l),
 'macro_flip_no_block_direction_change': sorted(m - (g|l)),
 'block_direction_change_no_macro_flip': sorted((g|l)-m),
 'turning_change_without_macro_flip': sorted(t-m),
}
report={
 'schema':'GMFQ_EUR_PIT_REVISION_BLOCK_ATTRIBUTION_V1',
 'engine_ref':d['engine_ref'],
 'rules_fingerprint':d['rules_fingerprint'],
 'source':str(SRC),
 'eligible_pit_core':d['eligible_series'],
 'summary':{
   'usable_macro_checkpoints':d['summary']['usable_macro_checkpoints'],
   'macro_flips':len(m),
   'growth_direction_changes':len(g),
   'labour_direction_changes':len(l),
   'macro_flip_growth_only':len(cats['macro_flip_growth_only']),
   'macro_flip_growth_only_pct_of_macro_flips':pct(len(cats['macro_flip_growth_only']),len(m)),
   'macro_flip_labour_only':len(cats['macro_flip_labour_only']),
   'macro_flip_labour_only_pct_of_macro_flips':pct(len(cats['macro_flip_labour_only']),len(m)),
   'macro_flip_both_blocks':len(cats['macro_flip_both_blocks']),
   'macro_flip_both_blocks_pct_of_macro_flips':pct(len(cats['macro_flip_both_blocks']),len(m)),
   'macro_flip_no_block_direction_change':len(cats['macro_flip_no_block_direction_change']),
   'block_direction_change_no_macro_flip':len(cats['block_direction_change_no_macro_flip']),
   'turning_changes':len(t),
   'turning_change_without_macro_flip':len(cats['turning_change_without_macro_flip']),
   'turning_change_without_macro_flip_pct':pct(len(cats['turning_change_without_macro_flip']),len(t)),
 },
 'checkpoints':cats,
 'limitations':d['limitations'],
 'interpretation_guardrail':'Descriptive attribution only. Do not alter model weights, thresholds, or rules from this partial EUR PIT sample.',
 'no_model_change':True
}
OUT.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['summary'],indent=2))
