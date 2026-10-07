#!/usr/bin/env python3
import json
from pathlib import Path
p=Path('validation/CURRENCY_CROSS_DISPERSION_V1_2026-10-07.json')
x=json.loads(p.read_text())
assert x['schema']=='GMFQ_CURRENCY_CROSS_DISPERSION_V1'
assert x['status']=='RESEARCH_ONLY_DESCRIPTIVE_NOT_PROMOTED'
assert set(x['currencies'])=={'USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'}
for c,d in x['currencies'].items():
    assert d['cross_count']==7
    assert sum(d['macro_relative'].values())==7
    assert sum(d['transmission_states'].values())==7
    assert sum(d['robustness'].values())==7
    assert d['display_contract']['do_not_convert_to_score'] is True
    assert d['display_contract']['do_not_call_absolute_bias'] is True
assert all(v is False for v in x['guards'].values())
print('PASS_CURRENCY_CROSS_DISPERSION_V1')
