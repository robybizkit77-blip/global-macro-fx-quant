#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import urllib.parse
import urllib.request
from pathlib import Path

RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
OUT=Path('validation/liquidity-eur-nfc-loans-revision-diagnostic.json')
BASE='https://data-api.ecb.europa.eu/service/data/BSI'
KEY='M.U2.N.A.A20.A.1.U2.2240.Z01.E'
SERIES_ID='BSI.'+KEY


def fetch():
    qs=urllib.parse.urlencode({'format':'csvdata','startPeriod':'2024-01'})
    url=f'{BASE}/{KEY}?{qs}'
    req=urllib.request.Request(url,headers={'User-Agent':'global-macro-fx-quant/1.0','Accept':'text/csv,application/vnd.sdmx.data+csv;version=2.0.0'})
    with urllib.request.urlopen(req,timeout=45) as r:text=r.read().decode('utf-8-sig')
    src={}
    for row in csv.DictReader(io.StringIO(text)):
        d=(row.get('TIME_PERIOD') or '')[:7]; raw=row.get('OBS_VALUE')
        if d and raw not in (None,''):src[d]=float(raw)
    if not src:raise SystemExit('ECB NFC loans source returned no observations')
    return url,src


def main():
    liq=json.loads(RUNTIME.read_text(encoding='utf-8'))
    row=liq['EUR']['credit']
    rt={str(d)[:7]:float(v) for d,v in zip(row['dates'],row['values'])}
    url,src=fetch()
    overlap=sorted(set(rt)&set(src))
    mismatches=[{'date':d,'runtime':rt[d],'current_vintage':src[d],'diff':rt[d]-src[d]} for d in overlap if abs(rt[d]-src[d])>1e-6]
    exact=[d for d in overlap if abs(rt[d]-src[d])<=1e-6]
    runtime_last=str(row['last_date'])[:7]
    latest=max(src)
    new=[{'date':d,'value':src[d]} for d in sorted(src) if d>runtime_last]
    recent12=[d for d in overlap if d>=sorted(overlap)[max(0,len(overlap)-12)]] if overlap else []
    recent12_exact=sum(1 for d in recent12 if abs(rt[d]-src[d])<=1e-6)
    report={
      'schema':'GMFQ_LIQUIDITY_EUR_NFC_LOANS_REVISION_DIAGNOSTIC_V1',
      'status':'DIAGNOSTIC_ONLY_NO_PROMOTION',
      'source':{'publisher':'European Central Bank / ESCB','series_id':SERIES_ID,'url':url,'frequency':'MONTHLY'},
      'runtime':{'count':len(rt),'last_date':runtime_last,'last_value':float(row['last_value'])},
      'proof':{
        'overlap_count':len(overlap),'exact_match_count':len(exact),'mismatch_count':len(mismatches),'mismatches':mismatches,
        'runtime_last_present_in_source':runtime_last in src,
        'runtime_last_matches_current_vintage':runtime_last in src and abs(float(row['last_value'])-src[runtime_last])<=1e-6,
        'source_value_on_runtime_last':src.get(runtime_last),
        'recent12_count':len(recent12),'recent12_exact_count':recent12_exact,
        'mismatch_dates':[x['date'] for x in mismatches]
      },
      'latest_date':latest,'latest_value':src[latest],
      'candidate_update_available':bool(new),'new_observations':new,
      'revision_aware_apply_safe':bool(runtime_last in src and abs(float(row['last_value'])-src[runtime_last])<=1e-6),
      'interpretation':'Historical current-vintage mismatches are tolerated only diagnostically. Promotion requires the stored runtime last observation to match the official current vintage exactly; controlled apply must remain append-only and must never rewrite historical runtime revisions.',
      'runtime_mutated':False,'publication_performed':False,'promotion_performed':False
    }
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
