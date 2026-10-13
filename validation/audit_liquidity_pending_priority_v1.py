#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

POLICY=Path('validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json')
EUR_OVERRIDE=Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_EUR_M3_V1_2026-10-13.json')
AUD_OVERRIDE=Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_AUD_ES_V1_2026-10-13.json')
RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
OUT=Path('validation/liquidity-pending-priority-audit.json')


def load(p): return json.loads(p.read_text(encoding='utf-8'))


def main():
    p=load(POLICY); rt=load(RUNTIME)
    mapped=dict(p.get('mapped') or {})
    for opath in (EUR_OVERRIDE,AUD_OVERRIDE):
        o=load(opath); mapped[o['supersedes']['subseries']]=o['effective_row']
    pending=[]
    for key,row in mapped.items():
        if row.get('automation_ready') is True: continue
        ccy,field=key.split('.',1)
        r=(rt.get(ccy) or {}).get(field) or {}
        dates=list(r.get('dates') or []); vals=list(r.get('values') or [])
        pending.append({
            'subseries':key,
            'label':row.get('label'),
            'status':row.get('status'),
            'series_mapping_status':row.get('series_mapping_status'),
            'publisher':row.get('publisher'),
            'frequency':row.get('frequency'),
            'series_key':row.get('series_key'),
            'candidate_pipeline_ready':row.get('candidate_pipeline_ready'),
            'runtime_count':len(dates),
            'runtime_first_date':dates[0] if dates else None,
            'runtime_last_date':r.get('last_date') or (dates[-1] if dates else None),
            'runtime_last_value':r.get('last_value') if 'last_value' in r else (vals[-1] if vals else None),
            'runtime_label':r.get('label'),
            'has_dates_values':bool(dates and vals and len(dates)==len(vals)),
            'source_url':row.get('source_url'),
            'reason':row.get('reason') or row.get('transport_status') or row.get('collector_status'),
        })
    def score(x):
        s=0
        sm=str(x.get('series_mapping_status') or '')
        st=str(x.get('status') or '')
        if 'EXACT_SERIES' in sm: s+=4
        if x.get('series_key'): s+=3
        if x.get('candidate_pipeline_ready') is True: s+=3
        if x.get('has_dates_values'): s+=1
        if 'REVISION' in sm or 'REVISION' in st: s-=3
        if 'PENDING_EXACT' in sm: s-=2
        if 'AGGREGATION' in sm or 'VARIANT' in sm or 'DIMENSION' in sm: s-=2
        if 'TRANSPORT' in st: s-=1
        return s
    for x in pending:x['priority_score']=score(x)
    pending.sort(key=lambda x:(-x['priority_score'],x['subseries']))
    out={'schema':'GMFQ_LIQUIDITY_PENDING_PRIORITY_AUDIT_V1','effective_ready':len(mapped)-len(pending),'effective_pending':len(pending),'total':len(mapped),'pending':pending,'runtime_mutated':False,'publication_performed':False}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(out,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
