#!/usr/bin/env python3
import json
from pathlib import Path

MACRO=Path('validation/PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1_2026-10-02.json')
GROWTH=Path('validation/PIT_SIGNAL_SENSITIVITY_CA_GROWTH_FULL_2020_2026_V1_2026-10-02.json')
LABOUR=Path('validation/PIT_SIGNAL_SENSITIVITY_CA_LABOUR_FULL_2020_2026_V1_2026-10-02.json')
OUT=Path('validation/CAD_MACRO_INTERNAL_DIVERGENCE_PROPAGATION_AUDIT_2026-10-03.json')

macro=json.loads(MACRO.read_text())['comparisons']
growth=json.loads(GROWTH.read_text())['comparisons']
labour=json.loads(LABOUR.read_text())['comparisons']

def idx(rows): return {r['checkpoint']:r for r in rows}
mi,gi,li=idx(macro),idx(growth),idx(labour)

# Proxy internal divergence from block-level first-release instability flags already established:
# classify a checkpoint as Growth-fragile if Growth direction changes PIT vs revised;
# Labour-fragile analogously. Then measure propagation into overall Macro polarity change.
# This is descriptive propagation, not causal attribution.
common=sorted(set(mi)&(set(gi)|set(li)))
rows=[]
for d in common:
    m=mi[d]
    g=gi.get(d)
    l=li.get(d)
    gd=bool(g and g.get('direction_changed'))
    ld=bool(l and l.get('direction_changed'))
    mf=bool(m.get('polarity_changed') or m.get('direction_changed'))
    mt=bool(m.get('turning_changed'))
    rows.append({'checkpoint':d,'growth_fragile':gd,'labour_fragile':ld,'macro_flip':mf,'macro_turning_change':mt})

def stats(pred):
    sub=[r for r in rows if pred(r)]
    return {'n':len(sub),'macro_flips':sum(r['macro_flip'] for r in sub),'macro_flip_pct':round(100*sum(r['macro_flip'] for r in sub)/len(sub),2) if sub else None,'macro_turning_changes':sum(r['macro_turning_change'] for r in sub),'macro_turning_change_pct':round(100*sum(r['macro_turning_change'] for r in sub)/len(sub),2) if sub else None}

report={
 'schema':'GMFQ_CAD_MACRO_INTERNAL_DIVERGENCE_PROPAGATION_AUDIT_V1',
 'engine_ref':'engine-freeze-v1-2026-10-02',
 'rules_fingerprint':'3356baf0',
 'method_note':'Descriptive propagation from block-level PIT-vs-revised direction fragility into overall Macro polarity/turning changes. This does not change model rules and does not infer causality.',
 'groups':{
   'growth_fragile_any':stats(lambda r:r['growth_fragile']),
   'labour_fragile_any':stats(lambda r:r['labour_fragile']),
   'growth_only_fragile':stats(lambda r:r['growth_fragile'] and not r['labour_fragile']),
   'labour_only_fragile':stats(lambda r:r['labour_fragile'] and not r['growth_fragile']),
   'both_fragile':stats(lambda r:r['growth_fragile'] and r['labour_fragile']),
   'neither_fragile':stats(lambda r:not r['growth_fragile'] and not r['labour_fragile'])
 },
 'examples_macro_flip_with_growth_fragility':[r['checkpoint'] for r in rows if r['growth_fragile'] and r['macro_flip']][:20],
 'examples_macro_flip_with_labour_fragility':[r['checkpoint'] for r in rows if r['labour_fragile'] and r['macro_flip']][:20],
 'no_model_change':True
}
OUT.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
