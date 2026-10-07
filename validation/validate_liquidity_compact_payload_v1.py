import json
from pathlib import Path
p=Path(__file__).resolve().parent/'LIQUIDITY_COMPACT_PAYLOAD_V1_2026-10-07.json'
d=json.loads(p.read_text())
assert d['schema']=='GMFQ_LIQUIDITY_COMPACT_PAYLOAD_V1'
assert d['status']=='RESEARCH_ONLY_CONTEXT_NOT_PROMOTED'
assert set(d['currencies'])=={'USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'}
allowed={'ESPANSIONE','CONTRAZIONE','MISTA','WITHHELD'}
for c,v in d['currencies'].items():
    assert v['context_read'] in allowed
    assert set(v['components'])=={'liquidity','money','credit'}
    for x in v['components'].values():
        assert x['status'] in {'AVAILABLE','UNAVAILABLE','INSUFFICIENT_HISTORY'}
        assert x['direction'] in {None,'UP','DOWN','FLAT'}
assert d['guards']['universal_score'] is False
assert d['guards']['fx_directional_override'] is False
assert d['guards']['trade_signal'] is False
assert d['guards']['changes_engine_rules'] is False
assert d['guards']['changes_live_data'] is False
assert d['guards']['production_promotion'] is False
print('PASS', {c:v['context_read'] for c,v in d['currencies'].items()})
