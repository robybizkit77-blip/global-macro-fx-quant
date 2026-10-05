#!/usr/bin/env python3
from pathlib import Path
import json,re

ROOT=Path('.')
SKIP={'.git'}
TEXT_EXT={'.py','.js','.html','.json','.md','.txt','.yml','.yaml','.csv'}
needles=['D.macro','macro[c]','macro[c]?.','macro.JPY','"labour":1.45','"labour": 1.45','macroSimpleScore','sector_states_it']
repo_hits=[]
for p in ROOT.rglob('*'):
    if not p.is_file() or any(part in SKIP for part in p.parts): continue
    if p.suffix.lower() not in TEXT_EXT: continue
    if p.parts and p.parts[0]=='payload': continue
    try: txt=p.read_text(errors='replace')
    except Exception: continue
    for n in needles:
        for m in re.finditer(re.escape(n),txt,re.I):
            s=max(0,m.start()-500);e=min(len(txt),m.end()+900)
            repo_hits.append({'file':str(p),'needle':n,'context':txt[s:e].replace('\n',' ')})
            if len(repo_hits)>=250: break
        if len(repo_hits)>=250: break
    if len(repo_hits)>=250: break

runtime='\n'.join(p.read_text(errors='replace') for p in sorted(Path('payload').glob('part-*.txt')))
runtime_hits=[]
for pat in [r'window\.__GMFQ_DATA\.D\s*=',r'const D\s*=',r'let D\s*=',r'var D\s*=',r'"JPY"\s*:\s*\{[^{}]{0,1000}"labour"\s*:\s*1\.45',r'macroSimpleScore',r'D\.macro\[c\]\[key\]']:
    for m in re.finditer(pat,runtime,re.I|re.S):
        s=max(0,m.start()-1200);e=min(len(runtime),m.end()+2200)
        runtime_hits.append({'pattern':pat,'context':runtime[s:e].replace('\n',' ')})
        if len(runtime_hits)>=80:break

ms=json.loads(Path('live_data/sections/MACRO_SERIES.json').read_text())
jpy=[]
for i,s in enumerate(ms['JPY']):
    if s.get('frequency')=='M':
        dates=s.get('dates',[]); vals=s.get('values',[])
        jpy.append({'index':i,'label':s.get('label'),'n':len(dates),'first3':dates[:3],'last3':dates[-3:],'last_values':vals[-3:]})

report={
 'schema_version':'GMFQ_D_MACRO_DERIVATION_TRACE_V1',
 'repo_hits':repo_hits,
 'runtime_hits':runtime_hits,
 'jpy_monthly_series_geometry':jpy,
 'summary':{
   'repo_hit_count':len(repo_hits),
   'runtime_hit_count':len(runtime_hits),
   'jpy_monthly_lengths':sorted(set(x['n'] for x in jpy)),
 }
}
Path('validation/D_MACRO_DERIVATION_TRACE_2026-10-05.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({
 'summary':report['summary'],
 'jpy_monthly_series_geometry':jpy,
 'repo_hits':repo_hits[:40],
 'runtime_hits':runtime_hits[:20]
},indent=2,ensure_ascii=False))
