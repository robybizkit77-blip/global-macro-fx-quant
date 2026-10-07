import json
from pathlib import Path
p=Path(__file__).resolve().parent/'POSITIONING_COMPACT_PAYLOAD_V1_2026-10-07.json'
d=json.loads(p.read_text())
assert d['schema']=='GMFQ_POSITIONING_COMPACT_PAYLOAD_V1'
assert d['status']=='RESEARCH_ONLY_PARTIAL_SOURCE_NOT_PROMOTED'
assert set(d['currencies'])=={'USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'}
assert d['source']['canonical_full_cot_dataset_connected'] is False
for c,v in d['currencies'].items():
    assert v['positioning_read'] in {'EXTREME_LONG','EXTREME_SHORT','LONG_BIAS','SHORT_BIAS','NEUTRAL_MID','WITHHELD'}
    assert v['delta_net_1w'] is None
    assert v['net_oi_pct'] is None
    assert v['flow_status']=='WITHHELD_SOURCE_NOT_AVAILABLE'
    assert v['imbalance_alert'] is None
assert d['guards']['fabricates_missing_flow'] is False
assert d['guards']['fabricates_missing_net_oi'] is False
assert d['guards']['trade_signal'] is False
assert d['guards']['changes_engine_rules'] is False
assert d['guards']['changes_live_data'] is False
assert d['guards']['production_promotion'] is False
print('PASS', len(d['currencies']))
