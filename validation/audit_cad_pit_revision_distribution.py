import json, collections
from pathlib import Path

src=Path('validation/PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1_2026-10-02.json')
data=json.loads(src.read_text(encoding='utf-8'))
rows=data.get('comparisons',[])

yearly=collections.OrderedDict()
transitions=collections.Counter()
turn_only=0
pol_only=0
both=0
neither=0
persistent_flip_runs=[]
current_run=[]

for r in rows:
    y=r['checkpoint'][:4]
    d=yearly.setdefault(y,{'checkpoints':0,'polarity_changes':0,'turning_changes':0,'growth_revision_effect':0,'labour_revision_effect':0})
    d['checkpoints']+=1
    if r.get('macro_polarity_changed'): d['polarity_changes']+=1
    if r.get('macro_turning_changed'): d['turning_changes']+=1
    if r.get('growth_direction_changed'): d['growth_revision_effect']+=1
    if r.get('labour_direction_changed'): d['labour_revision_effect']+=1
    pchg=bool(r.get('macro_polarity_changed'))
    tchg=bool(r.get('macro_turning_changed'))
    if pchg and tchg: both+=1
    elif pchg: pol_only+=1
    elif tchg: turn_only+=1
    else: neither+=1
    if pchg:
        fr=r['first_release']['macro_polarity']
        cr=r['current_revised']['macro_polarity']
        transitions[f'{fr}->{cr}']+=1
        current_run.append(r['checkpoint'])
    else:
        if current_run:
            persistent_flip_runs.append(current_run)
            current_run=[]
if current_run: persistent_flip_runs.append(current_run)

for y,d in yearly.items():
    d['polarity_change_pct']=round(100*d['polarity_changes']/d['checkpoints'],2) if d['checkpoints'] else None
    d['turning_change_pct']=round(100*d['turning_changes']/d['checkpoints'],2) if d['checkpoints'] else None

runs=[{'start':r[0],'end':r[-1],'length':len(r)} for r in persistent_flip_runs]
runs=sorted(runs,key=lambda x:x['length'],reverse=True)

out={
 'schema':'GMFQ_CAD_PIT_REVISION_DISTRIBUTION_AUDIT_V1',
 'source':str(src),
 'engine_ref':'engine-freeze-v1-2026-10-02',
 'totals':{
   'checkpoints':len(rows),
   'polarity_changes':sum(x['polarity_changes'] for x in yearly.values()),
   'turning_changes':sum(x['turning_changes'] for x in yearly.values()),
   'both_polarity_and_turning_changed':both,
   'polarity_only_changed':pol_only,
   'turning_only_changed':turn_only,
   'neither_changed':neither
 },
 'by_year':yearly,
 'polarity_transition_counts':dict(transitions),
 'longest_consecutive_changed_runs':runs[:10],
 'interpretation_rules':{
   'distributed_if_multiple_years':'Revision sensitivity is structural rather than one-off if polarity changes appear across multiple calendar years.',
   'turning_vs_direction':'If polarity-only changes are material, revisions affect persistent directional state, not just timing/turning labels.',
   'no_model_change':'Audit only; do not tune thresholds from these results.'
 }
}
Path('validation/CAD_PIT_REVISION_DISTRIBUTION_AUDIT_2026-10-03.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
