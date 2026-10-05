#!/usr/bin/env python3
from pathlib import Path
import json,re

parts=sorted(Path('payload').glob('part-*.txt'))
runtime='\n'.join(p.read_text(errors='replace') for p in parts)
patterns=[
    r'MOLTO_FREDDO',r'FREDDO',r'NORMALE',r'CALDO',r'MOLTO_CALDO',
    r'temperature_label',r'temperature_score',r'MACRO_THERMOMETER_DATA',
    r'D\.macro',r'\.macro\[',r'macro\.JPY',r'labour'
]

def contexts(rx,limit=40,span=260):
    out=[]
    for m in re.finditer(rx,runtime,re.I):
        s=max(0,m.start()-span); e=min(len(runtime),m.end()+span)
        out.append(runtime[s:e].replace('\n',' '))
        if len(out)>=limit: break
    return out

report={'schema_version':'GMFQ_MACRO_RUNTIME_SEMANTICS_TRACE_V1','runtime_chars':len(runtime),'patterns':{}}
for rx in patterns:
    hits=list(re.finditer(rx,runtime,re.I))
    report['patterns'][rx]={'count':len(hits),'contexts':contexts(rx)}

# Extract compact snippets around likely threshold code operators near temperature terms.
threshold_snips=[]
for term in ['MOLTO_FREDDO','MOLTO_CALDO','temperature_label','temperature_score']:
    for m in re.finditer(term,runtime,re.I):
        s=max(0,m.start()-800); e=min(len(runtime),m.end()+800)
        txt=runtime[s:e]
        if any(op in txt for op in ['<20','<=20','< 20','<= 20','<40','< 40','>=80','>= 80','>80','> 80']):
            threshold_snips.append(txt.replace('\n',' '))
report['threshold_candidate_contexts']=threshold_snips[:30]
Path('validation/MACRO_RUNTIME_SEMANTICS_TRACE_2026-10-05.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({
    'runtime_chars':report['runtime_chars'],
    'counts':{k:v['count'] for k,v in report['patterns'].items()},
    'threshold_candidate_count':len(threshold_snips),
    'threshold_candidates':threshold_snips[:8],
    'D_macro_contexts':report['patterns'][r'D\\.macro']['contexts'][:10],
    'thermometer_contexts':report['patterns']['MACRO_THERMOMETER_DATA']['contexts'][:10]
},indent=2,ensure_ascii=False))
