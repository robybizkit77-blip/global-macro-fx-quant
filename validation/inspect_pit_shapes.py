#!/usr/bin/env python3
import json
from pathlib import Path
FILES = [
 'validation/pit_batch/eurostat/EUROSTAT_PIT_READY_V1_2026-10-02.json',
 'validation/pit_batch/eurostat/EUR_EMPLOYMENT_SOURCE_RECONCILIATION_V1_2026-10-02.json',
 'validation/pit_batch/bea/BEA_PIO_PIT_BATCH_V1_2026-10-03.json',
 'validation/pit_batch/census/CENSUS_M3_NEWORDER_PIT_BATCH_V1_2026-10-03.json',
 'validation/pit_batch/fed_g17/FED_G17_INDPRO_PIT_BATCH_READY_V1_2026-10-02.json',
 'validation/PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1_2026-10-02.json'
]
def sample(x):
    if isinstance(x, dict):
        out={}
        for k,v in x.items():
            if isinstance(v,list) and v:
                out[k]={'list_len':len(v),'first_type':type(v[0]).__name__,'first_keys':list(v[0].keys()) if isinstance(v[0],dict) else None}
            elif isinstance(v,dict):
                out[k]={'dict_keys':list(v.keys())[:20]}
            else:
                out[k]=type(v).__name__
        return out
    return type(x).__name__
for f in FILES:
    p=Path(f)
    print('\nFILE',f)
    obj=json.loads(p.read_text())
    print(json.dumps(sample(obj),indent=2,ensure_ascii=False))
    if isinstance(obj,dict) and isinstance(obj.get('series'),dict):
        for sk,sv in obj['series'].items():
            print(' SERIES',sk, json.dumps(sample(sv),ensure_ascii=False))
