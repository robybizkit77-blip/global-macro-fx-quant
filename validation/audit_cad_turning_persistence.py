#!/usr/bin/env python3
import json
from pathlib import Path

SRC=Path('validation/PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1_2026-10-02.json')
OUT=Path('validation/CAD_TURNING_PERSISTENCE_AUDIT_2026-10-03.json')
rows=json.loads(SRC.read_text())['comparisons']

# A fragile turning checkpoint is one where PIT vs revised disagree on turning_present.
# Persistence test: inspect next union-release checkpoint and ask whether the first-release turning state
# persists and whether macro polarity subsequently changes in the direction implied by the first-release state.
frag=[]
for i,r in enumerate(rows[:-1]):
    if not r.get('macro_turning_changed'):
        continue
    nxt=rows[i+1]
    cur_turn=bool(r['first_release']['turning_present'])
    next_turn=bool(nxt['first_release']['turning_present'])
    cur_pol=r['first_release']['macro_polarity']
    next_pol=nxt['first_release']['macro_polarity']
    frag.append({
        'checkpoint':r['checkpoint'],
        'next_checkpoint':nxt['checkpoint'],
        'first_release_turning_now':cur_turn,
        'first_release_turning_next':next_turn,
        'turning_persists_next': cur_turn and next_turn,
        'turning_reverts_next': cur_turn and not next_turn,
        'macro_polarity_now':cur_pol,
        'macro_polarity_next':next_pol,
        'macro_polarity_changes_next':cur_pol!=next_pol
    })

active=[x for x in frag if x['first_release_turning_now']]
persist=sum(x['turning_persists_next'] for x in active)
revert=sum(x['turning_reverts_next'] for x in active)
polchg=sum(x['macro_polarity_changes_next'] for x in active)
report={
 'schema':'GMFQ_CAD_TURNING_PERSISTENCE_AUDIT_V1',
 'engine_ref':'engine-freeze-v1-2026-10-02',
 'rules_fingerprint':'3356baf0',
 'method_note':'For PIT-vs-revised turning disagreements, evaluate the next union-release checkpoint using the first-release path only. Descriptive persistence test; no model changes.',
 'totals':{
   'fragile_turning_disagreements':len(frag),
   'fragile_first_release_turning_active':len(active),
   'persists_next_checkpoint':persist,
   'persists_next_pct':round(100*persist/len(active),2) if active else None,
   'reverts_next_checkpoint':revert,
   'reverts_next_pct':round(100*revert/len(active),2) if active else None,
   'macro_polarity_changes_next_checkpoint':polchg,
   'macro_polarity_changes_next_pct':round(100*polchg/len(active),2) if active else None
 },
 'examples_persist':[x['checkpoint'] for x in active if x['turning_persists_next']][:20],
 'examples_revert':[x['checkpoint'] for x in active if x['turning_reverts_next']][:20],
 'no_model_change':True
}
OUT.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
