import json
from pathlib import Path

SRC=Path('validation/PAIR_COMPACT_PAYLOAD_V1_2026-10-07.json')
OUT=Path('validation/PAIR_ATTENTION_BUCKETS_V1_2026-10-07.json')

def main():
    src=json.loads(SRC.read_text())
    buckets={
        'CLEAN_ROBUST':[],
        'PARTIAL_ROBUST':[],
        'DIVERGENT_ROBUST':[],
        'RULE_SENSITIVE':[],
        'WITHHELD':[]
    }
    for pair,p in src['pairs'].items():
        state=p['transmission']
        robust=p['robustness']
        if state=='TRANSMISSION_WITHHELD':
            key='WITHHELD'
        elif robust=='RULE_SENSITIVE':
            key='RULE_SENSITIVE'
        elif state=='TRANSMISSION_CLEAN':
            key='CLEAN_ROBUST'
        elif state=='TRANSMISSION_PARTIAL':
            key='PARTIAL_ROBUST'
        elif state=='TRANSMISSION_DIVERGENT':
            key='DIVERGENT_ROBUST'
        else:
            raise ValueError((pair,state,robust))
        buckets[key].append({
            'pair':pair,
            'macro_anchor':p['macro_anchor'],
            'transmission':state,
            'robustness':robust,
            'layers':p['layers'],
            'what_changed':p['what_changed'],
            'forward':p['forward'],
            'research_evidence':p['research_evidence']
        })
    for rows in buckets.values():
        rows.sort(key=lambda x:x['pair'])
    out={
        'schema':'GMFQ_PAIR_ATTENTION_BUCKETS_V1',
        'status':'RESEARCH_ONLY_DESCRIPTIVE_NOT_PROMOTED',
        'purpose':'Non-numeric attention buckets for a future compact dashboard. This is not a ranking, score, trade signal, or predictive claim.',
        'display_priority':['CLEAN_ROBUST','PARTIAL_ROBUST','DIVERGENT_ROBUST','RULE_SENSITIVE','WITHHELD'],
        'display_policy':{
            'no_numeric_score':True,
            'no_cross_ranking_within_bucket':True,
            'show_clean_first_as_current_coherence_not_expected_return':True,
            'show_divergent_as_diagnostic_attention_not_trade_reversal':True,
            'rule_sensitive_must_show_warning':True,
            'withheld_must_not_be_forced_directional':True
        },
        'counts':{k:len(v) for k,v in buckets.items()},
        'buckets':buckets,
        'guards':{
            'changes_engine_rules':False,
            'changes_live_data':False,
            'changes_oos_baseline':False,
            'production_promotion':False,
            'creates_universal_score':False,
            'predictive_claim':False
        }
    }
    assert sum(out['counts'].values())==28
    OUT.write_text(json.dumps(out,indent=2)+"\n")

if __name__=='__main__': main()
