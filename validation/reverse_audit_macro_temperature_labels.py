#!/usr/bin/env python3
import json
from pathlib import Path

data=json.loads(Path('live_data/sections/MACRO_THERMOMETER_DATA.json').read_text())
rows=[]
for ccy,c in data['currencies'].items():
    for dim in ('inflation','labour'):
        s=c[dim]
        rows.append({'ccy':ccy,'dimension':dim,'percentile':s.get('percentile'),'temperature_score':s.get('temperature_score'),'label':s.get('temperature_label')})
by={}
for r in rows:
    by.setdefault(r['label'],[]).append(r['percentile'])
summary={k:{'min':min(v),'max':max(v),'values':sorted(v)} for k,v in by.items()}
report={'schema_version':'GMFQ_MACRO_TEMPERATURE_LABEL_AUDIT_V1','summary':summary,'rows':sorted(rows,key=lambda r:r['percentile'])}
Path('validation/MACRO_TEMPERATURE_LABEL_AUDIT_2026-10-05.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(report,indent=2,ensure_ascii=False))
