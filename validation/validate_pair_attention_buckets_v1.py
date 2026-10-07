import json
from pathlib import Path

P=Path('validation/PAIR_ATTENTION_BUCKETS_V1_2026-10-07.json')

def main():
    d=json.loads(P.read_text())
    assert d['schema']=='GMFQ_PAIR_ATTENTION_BUCKETS_V1'
    assert d['status']=='RESEARCH_ONLY_DESCRIPTIVE_NOT_PROMOTED'
    assert d['display_policy']['no_numeric_score'] is True
    assert d['display_policy']['no_cross_ranking_within_bucket'] is True
    assert sum(d['counts'].values())==28
    seen=[]
    for k,rows in d['buckets'].items():
        for r in rows:
            seen.append(r['pair'])
            if k=='RULE_SENSITIVE': assert r['robustness']=='RULE_SENSITIVE'
            if k=='WITHHELD': assert r['transmission']=='TRANSMISSION_WITHHELD'
            if k=='CLEAN_ROBUST':
                assert r['transmission']=='TRANSMISSION_CLEAN'
                assert r['robustness']=='ROBUST_ACROSS_RULES'
    assert len(seen)==28 and len(set(seen))==28
    assert all(v is False for v in d['guards'].values())
    print('PASS pair attention buckets',d['counts'])

if __name__=='__main__': main()
