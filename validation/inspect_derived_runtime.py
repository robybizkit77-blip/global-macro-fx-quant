#!/usr/bin/env python3
from __future__ import annotations
import json, pathlib, re
ROOT=pathlib.Path(__file__).resolve().parents[1]
parts=sorted((ROOT/'payload').glob('part-*.txt'))
text=''.join(p.read_text() for p in parts)
needles={
  'cot_identifier':'V247_COT_STORIES',
  'rates_identifier':'RATES_AUDIT_METADATA',
  'cot_phrase':'Stock, flusso e percentile sono aggiornati dal medesimo record CFTC',
  'rates_schema':'GMFQ_RATES_AUDIT_METADATA_V1',
  'post_gate_anchor':'gmfq-post-gate-final-audit-20260930',
  'source_policy':'FINAL_SOURCE_POLICY_AUDIT',
}
out={'runtime_chars':len(text),'parts':len(parts),'matches':{}}
for k,n in needles.items():
    poss=[m.start() for m in re.finditer(re.escape(n),text)]
    out['matches'][k]={'count':len(poss),'positions':poss[:10]}
# capture small context safely around identifiers/phrases
ctx={}
for k,v in out['matches'].items():
    if v['positions']:
        pos=v['positions'][0]
        ctx[k]=text[max(0,pos-250):pos+700]
out['context']=ctx
print(json.dumps(out,indent=2,ensure_ascii=False))
