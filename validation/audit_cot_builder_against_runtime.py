#!/usr/bin/env python3
from __future__ import annotations
import json, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'validation'))
import build_cot_stories as b
parts=sorted((ROOT/'payload').glob('part-*.txt'))
text=''.join(p.read_text() for p in parts)
prefix='window.__GMFQ_DATA.V247_COT_STORIES='
pos=text.find(prefix)
if pos<0: raise SystemExit('V247 assignment not found')
start=pos+len(prefix)
current,end=json.JSONDecoder().raw_decode(text[start:])
src=json.loads((ROOT/'live_data'/'sections'/'V250_COT_CHART_DATA.json').read_text())
d=json.loads((ROOT/'live_data'/'sections'/'D.json').read_text())
built={c:b.build_one(c,src[c]) for c in b.ORDER}
drift=[]
for c in b.ORDER:
    keys=sorted(set(current.get(c,{}))|set(built.get(c,{})))
    for k in keys:
        if current.get(c,{}).get(k)!=built.get(c,{}).get(k):
            drift.append({'currency':c,'field':k,'runtime':current.get(c,{}).get(k),'built':built.get(c,{}).get(k)})
print(json.dumps({
 'status':'PASS',
 'runtime_currencies':len(current),
 'source_keys':{c:sorted(src[c].keys()) for c in b.ORDER},
 'd_cot':{c:d.get('cot',{}).get(c) for c in b.ORDER},
 'last_source':{c:{k:(src[c][k][-1] if isinstance(src[c].get(k),list) and src[c][k] else src[c].get(k)) for k in src[c]} for c in b.ORDER},
 'drift':drift,
 'drift_count':len(drift)
},indent=2,ensure_ascii=False))
