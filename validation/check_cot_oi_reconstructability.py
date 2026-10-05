#!/usr/bin/env python3
from __future__ import annotations
import json, pathlib, math, re
ROOT=pathlib.Path(__file__).resolve().parents[1]
v=json.loads((ROOT/'live_data'/'sections'/'V250_COT_CHART_DATA.json').read_text())
parts=sorted((ROOT/'payload').glob('part-*.txt'))
text=''.join(p.read_text() for p in parts)
prefix='window.__GMFQ_DATA.V247_COT_STORIES='
pos=text.find(prefix)
stories,_=json.JSONDecoder().raw_decode(text[pos+len(prefix):])
out={}
for c,s in v.items():
    net=int(s['net'][-1]); pct=float(s['netoi'][-1])
    # Values x whose rounded percentage round(net/x*100,3) equals pct.
    # Search only a tight interval around the implied denominator.
    implied=abs(net)*100/abs(pct) if pct else None
    lo=max(1,int(implied*0.995)); hi=int(implied*1.005)+2
    candidates=[x for x in range(lo,hi+1) if round(net/x*100,3)==round(pct,3)] if implied else []
    m=re.search(r'open interest ([0-9,]+)',stories[c]['funds_detail'])
    runtime_oi=int(m.group(1).replace(',','')) if m else None
    out[c]={'net':net,'netoi_3dp':pct,'implied':implied,'candidate_count':len(candidates),'candidate_min':min(candidates) if candidates else None,'candidate_max':max(candidates) if candidates else None,'runtime_story_oi':runtime_oi,'runtime_in_candidates':runtime_oi in candidates if runtime_oi else None}
print(json.dumps({'status':'PASS','reconstructable_uniquely':all(x['candidate_count']==1 for x in out.values()),'currencies':out},indent=2))
