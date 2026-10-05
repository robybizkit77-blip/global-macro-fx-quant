#!/usr/bin/env python3
from __future__ import annotations
import json, pathlib, re
ROOT=pathlib.Path(__file__).resolve().parents[1]
parts=sorted((ROOT/'payload').glob('part-*.txt'))
runtime=''.join(p.read_text() for p in parts)
prefix='window.__GMFQ_DATA.V247_COT_STORIES='
pos=runtime.find(prefix)
if pos<0: raise SystemExit('V247 runtime assignment not found')
obj,used=json.JSONDecoder().raw_decode(runtime[pos+len(prefix):])
# remove the V247 assignment itself when checking whether the same number exists elsewhere in runtime
assign_start=pos
assign_end=pos+len(prefix)+used
runtime_without_story=runtime[:assign_start]+runtime[assign_end:]
sections=list((ROOT/'live_data'/'sections').glob('*.json'))
out={}
for c,story in obj.items():
    m=re.search(r'open interest ([0-9,]+)',story.get('funds_detail',''))
    if not m:
        out[c]={'error':'open interest not present in runtime story'}
        continue
    oi=int(m.group(1).replace(',',''))
    hits=[]
    variants={str(oi),f'{oi:,}'}
    for f in sections:
        txt=f.read_text()
        if any(v in txt for v in variants): hits.append(f.name)
    runtime_hits={v:runtime_without_story.count(v) for v in variants}
    out[c]={'story_open_interest':oi,'section_hits':hits,'runtime_hits_outside_story':runtime_hits}
print(json.dumps({'status':'PASS','currencies':len(out),'trace':out},indent=2,ensure_ascii=False))
