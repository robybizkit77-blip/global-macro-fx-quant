#!/usr/bin/env python3
import json
from pathlib import Path

P=Path('validation/CENTRAL_BANK_REACTION_FUNCTION_EVIDENCE_MAP_V2_2026-10-07.json')
ENGINE='ff52198a75cc67f7dae96fc2bbf65623f170791c'
FP='3356baf0'

x=json.loads(P.read_text())
assert x['engine_baseline']['commit']==ENGINE
assert x['engine_baseline']['rules_fingerprint']==FP
assert x['engine_baseline']['modified'] is False
assert x['cross_currency_conclusion']['universal_conviction_score']=='REJECTED'
assert x['cross_currency_conclusion']['universal_front_end_gate']=='REJECTED'
assert x['changes_engine_rules'] is False
assert x['changes_live_data'] is False
assert x['changes_oos_baseline'] is False

cc=x['currencies']
assert set(cc)=={'USD','EUR','GBP','JPY','CAD','AUD','NZD','CHF'}
for c,v in cc.items():
    assert v['production_rule'] in {'NO_GATE','WITHHELD'}
    assert v['evidence_status'] in {'SUPPORTED_DIAGNOSTIC','PROMISING_SMALL_SAMPLE','NO_INCREMENTAL_VALUE','WITHHELD'}

assert cc['USD']['evidence_status']=='SUPPORTED_DIAGNOSTIC'
assert cc['CAD']['evidence_status']=='PROMISING_SMALL_SAMPLE'
for c in ('EUR','GBP','JPY'):
    assert cc[c]['evidence_status']=='NO_INCREMENTAL_VALUE'
for c in ('AUD','NZD','CHF'):
    assert cc[c]['evidence_status']=='WITHHELD'

print('PASS central_bank_reaction_evidence_map_v2 guard')
