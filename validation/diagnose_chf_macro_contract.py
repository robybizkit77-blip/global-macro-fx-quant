#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
heat=json.loads((ROOT/'live_data/sections/MACRO_THERMOMETER_DATA.json').read_text())
series=json.loads((ROOT/'live_data/sections/MACRO_SERIES.json').read_text())
rows=series['CHF']
out={'currency':'CHF','heatmap':heat['currencies']['CHF'],'series_candidates':[]}
for r in rows:
    if not isinstance(r,dict):
        continue
    text=' '.join(str(r.get(k,'')) for k in ('id','label','name','title','indicator')).lower()
    if any(x in text for x in ('cpi','infl','unemp','disoccup')):
        out['series_candidates'].append({
            'id':r.get('id'),'label':r.get('label') or r.get('name'),'frequency':r.get('frequency'),'unit':r.get('unit'),
            'observations':len(r.get('observations',[])) if isinstance(r.get('observations'),list) else None
        })
print(json.dumps(out,ensure_ascii=False,indent=2))
