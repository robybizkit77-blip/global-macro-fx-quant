#!/usr/bin/env python3
from __future__ import annotations
import json, pathlib, subprocess, sys, tempfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
REG=json.loads((ROOT/'validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json').read_text())
SERIES=json.loads((ROOT/'live_data/sections/MACRO_SERIES.json').read_text())
BRIDGE=ROOT/'validation/macro_adapter_pit_handoff.py'
CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']
DIMS=['inflation','labour']

def canon_row(c, entry):
    target=f"{entry['series_id']}_history_value"
    rows=SERIES[c]
    exact=[r for r in rows if r.get('id')==target]
    if len(exact)==1:
        return exact[0]
    suffix=[r for r in rows if str(r.get('id') or '').endswith('_'+target)]
    if len(suffix)==1:
        return suffix[0]
    raise RuntimeError(f'{c}: expected one canonical row for {target}; exact={len(exact)} suffix={len(suffix)}')

def period(v):
    s=str(v or '')
    if len(s)>=7 and s[4]=='-': return s[:7]
    return s

def fnum(v):
    try: return float(v)
    except Exception: return None

def main():
    results={}; counts={'UPDATE_AVAILABLE':0,'NO_CHANGE':0,'REVISION_AVAILABLE':0,'SOURCE_BLOCKED':0,'SOURCE_OLDER':0,'ERROR':0}
    with tempfile.TemporaryDirectory(prefix='gmfq-macro-sweep-') as td:
        work=pathlib.Path(td)
        for c in CCYS:
            for d in DIMS:
                key=f'{c}.{d}'; entry=REG['series'][key]; row=canon_row(c,entry)
                out=work/f'{c}_{d}.json'; audit=work/f'{c}_{d}.audit.json'
                cmd=[sys.executable,str(BRIDGE),'--currency',c,'--dimension',d,'--output',str(out),'--audit-output',str(audit)]
                cp=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
                if cp.returncode!=0:
                    results[key]={'status':'SOURCE_BLOCKED','returncode':cp.returncode,'stderr_tail':cp.stderr[-1200:],'stdout_tail':cp.stdout[-1200:],'canonical':{'last_date':row.get('last_date'),'last_value':row.get('last_value')},'authority':entry.get('authority'),'frequency':entry.get('frequency')}
                    counts['SOURCE_BLOCKED']+=1
                    continue
                cand=json.loads(out.read_text()); cp_date=period(cand.get('observation_date')); cur_date=period(row.get('last_date')); cv=fnum(row.get('last_value')); nv=fnum(cand.get('value'))
                if cp_date>cur_date: status='UPDATE_AVAILABLE'
                elif cp_date<cur_date: status='SOURCE_OLDER'
                else:
                    if cv is not None and nv is not None and abs(cv-nv)<=1e-9: status='NO_CHANGE'
                    elif row.get('last_value')==cand.get('value'): status='NO_CHANGE'
                    else: status='REVISION_AVAILABLE'
                counts[status]+=1
                results[key]={'status':status,'authority':entry.get('authority'),'frequency':entry.get('frequency'),'series_id':entry.get('series_id'),'canonical':{'last_date':row.get('last_date'),'last_value':row.get('last_value')},'official':{'observation_date':cand.get('observation_date'),'value':cand.get('value'),'source':cand.get('source'),'source_url':cand.get('provenance',{}).get('source_url'),'transport':cand.get('transport')},'candidate_only':cand.get('candidate_only'),'live_data_written':cand.get('live_data_written')}
    summary={'schema':'GMFQ_MACRO_CURRENT_SWEEP_V1','status':'PASS_READ_ONLY','core_series':16,'counts':counts,'updates':[k for k,v in results.items() if v['status']=='UPDATE_AVAILABLE'],'revisions':[k for k,v in results.items() if v['status']=='REVISION_AVAILABLE'],'blocked':[k for k,v in results.items() if v['status']=='SOURCE_BLOCKED'],'older':[k for k,v in results.items() if v['status']=='SOURCE_OLDER'],'no_change':[k for k,v in results.items() if v['status']=='NO_CHANGE'],'results':results,'writes_live_data':False,'automatic_publication':False}
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    pathlib.Path('/tmp/macro-current-sweep.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    return 0
if __name__=='__main__': raise SystemExit(main())
