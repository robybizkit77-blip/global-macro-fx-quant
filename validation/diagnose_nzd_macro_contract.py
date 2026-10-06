#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
heat=json.loads((ROOT/'live_data/sections/MACRO_THERMOMETER_DATA.json').read_text())
series=json.loads((ROOT/'live_data/sections/MACRO_SERIES.json').read_text())
print(json.dumps({
 'currency':'NZD',
 'heatmap':heat['currencies']['NZD'],
 'series_candidates':[
  {'id':r.get('id'),'label':r.get('label'),'frequency':r.get('frequency'),'unit':r.get('unit'),'observations':len(r.get('observations') or [])}
  for r in series['NZD'] if isinstance(r,dict)
 ]
},ensure_ascii=False,indent=2))
