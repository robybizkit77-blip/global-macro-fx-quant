#!/usr/bin/env python3
import json
from pathlib import Path

HIST = Path('validation/CURRENCY_CROSS_DISPERSION_HISTORY_V1_2026-10-07.json')
OUT = Path('validation/CURRENCY_WHAT_CHANGED_V1_2026-10-07.json')


def n(d, k): return int(d.get(k, 0) or 0)

def compare(prev, cur):
    # Descriptive only. No universal score: use ordered checks on interpretable count changes.
    pm, cm = prev['macro_relative'], cur['macro_relative']
    pt, ct = prev['transmission_states'], cur['transmission_states']
    pr, cr = prev['robustness'], cur['robustness']

    changes = {
        'favored_delta': n(cm,'favored') - n(pm,'favored'),
        'opposed_delta': n(cm,'opposed') - n(pm,'opposed'),
        'clean_delta': n(ct,'TRANSMISSION_CLEAN') - n(pt,'TRANSMISSION_CLEAN'),
        'partial_delta': n(ct,'TRANSMISSION_PARTIAL') - n(pt,'TRANSMISSION_PARTIAL'),
        'divergent_delta': n(ct,'TRANSMISSION_DIVERGENT') - n(pt,'TRANSMISSION_DIVERGENT'),
        'withheld_delta': n(ct,'TRANSMISSION_WITHHELD') - n(pt,'TRANSMISSION_WITHHELD'),
        'robust_delta': n(cr,'ROBUST_ACROSS_RULES') - n(pr,'ROBUST_ACROSS_RULES'),
        'rule_sensitive_delta': n(cr,'RULE_SENSITIVE') - n(pr,'RULE_SENSITIVE'),
    }
    if all(v == 0 for v in changes.values()):
        label = 'STABILE'
    elif changes['divergent_delta'] > 0 and changes['clean_delta'] <= 0:
        label = 'DIVERGENZA_IN_AUMENTO'
    elif changes['clean_delta'] > 0 or (changes['favored_delta'] > 0 and changes['divergent_delta'] <= 0):
        label = 'IN_MIGLIORAMENTO'
    elif changes['clean_delta'] < 0 or changes['favored_delta'] < 0 or changes['divergent_delta'] > 0:
        label = 'IN_PEGGIORAMENTO'
    else:
        label = 'CAMBIAMENTO_MISTO'
    return label, changes

hist = json.loads(HIST.read_text())
snaps = hist['snapshots']
res = {
    'schema':'GMFQ_CURRENCY_WHAT_CHANGED_V1',
    'status':'RESEARCH_ONLY_DESCRIPTIVE_NOT_PROMOTED',
    'comparison_available': len(snaps) >= 2,
    'currencies':{},
    'guards':{
        'changes_engine_rules':False,
        'changes_live_data':False,
        'changes_oos_baseline':False,
        'production_promotion':False,
        'creates_universal_score':False,
        'retroactive_tuning':False,
    }
}
if len(snaps) < 2:
    latest = snaps[-1]
    res['current_snapshot_id'] = latest['snapshot_id']
    for c in sorted(latest['currencies']):
        res['currencies'][c] = {'label':'BASELINE','deltas':None,'note_it':'Primo snapshot: nessun confronto precedente disponibile.'}
else:
    prev, cur = snaps[-2], snaps[-1]
    res['previous_snapshot_id'] = prev['snapshot_id']
    res['current_snapshot_id'] = cur['snapshot_id']
    for c in sorted(cur['currencies']):
        label, deltas = compare(prev['currencies'][c], cur['currencies'][c])
        res['currencies'][c] = {'label':label,'deltas':deltas}
OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False) + '\n')
print(res['status'], 'comparison=', res['comparison_available'])
