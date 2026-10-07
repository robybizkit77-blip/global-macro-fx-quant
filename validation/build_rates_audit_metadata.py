#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
CURRENT=ROOT/'live_data'/'sections'/'RATES_AUDIT_METADATA.json'
ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']

DEFAULT_POLICY={
 'USD':('CURRENT_OFFICIAL_SAME_BASIS','CURRENT','Validated U.S. Treasury same-basis snapshot retained.'),
 'EUR':('CURRENT_OFFICIAL_SAME_BASIS','CURRENT','Validated ECB AAA same-basis snapshot retained.'),
 'GBP':('CURRENT_OFFICIAL_SAME_BASIS','CURRENT','Validated Bank of England same-basis snapshot retained.'),
 'JPY':('CURRENT_OFFICIAL_SAME_BASIS','CURRENT','Validated MOF same-basis 2Y/10Y snapshot retained.'),
 'CHF':('WITHHELD_SOURCE_BLOCKED','WITHHOLD','SNB current 2Y/10Y same-basis pair is not available from the validated export path; retain last validated snapshot.'),
 'CAD':('CURRENT_OFFICIAL_SAME_BASIS','CURRENT','Validated Bank of Canada same-basis 2Y/10Y snapshot retained.'),
 'AUD':('CURRENT_BY_SOURCE_CADENCE','CURRENT_BY_SOURCE_CADENCE','Validated RBA F2 observation retained at source-native publication cadence.'),
 'NZD':('CURRENT_OFFICIAL_SAME_BASIS','CURRENT','Validated RBNZ B2 same-basis snapshot retained.')
}

def audit_policy(c:str,row:dict|None):
    if not row:
        return DEFAULT_POLICY[c]
    state=row.get('state')
    mode=row.get('coverage_mode')
    if state=='WITHHOLD':
        return ('WITHHELD_SOURCE_BLOCKED','WITHHOLD',row.get('reason') or DEFAULT_POLICY[c][2])
    if mode=='OFFICIAL_CADENCE_ASSERTION':
        return ('CURRENT_BY_SOURCE_CADENCE','CURRENT_BY_SOURCE_CADENCE',row.get('reason') or DEFAULT_POLICY[c][2])
    if mode=='LIVE_FETCH' and state in {'NO_CHANGE','UPDATE_AVAILABLE'}:
        action='UPDATED' if state=='UPDATE_AVAILABLE' else 'CURRENT'
        return ('CURRENT_OFFICIAL_SAME_BASIS',action,row.get('reason') or DEFAULT_POLICY[c][2])
    return ('REVIEW_REQUIRED',state or 'REVIEW_REQUIRED',row.get('reason') or 'Audit state requires review.')

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--audit-date',required=True)
    ap.add_argument('--audit')
    ap.add_argument('--output')
    ap.add_argument('--audit-current',action='store_true')
    a=ap.parse_args()
    src=json.loads(SRC.read_text())
    audit=json.load(open(a.audit)) if a.audit else None
    if audit and audit.get('status')!='PASS': raise SystemExit('cannot build freshness metadata from failed audit')
    missing=[c for c in ORDER if c not in src]
    if missing: raise SystemExit('Missing currencies: '+','.join(missing))
    expected={}
    rates={}
    audit_rows=(audit or {}).get('currencies',{})
    for c in ORDER:
        d=src[c]
        date=d.get('date')
        if not isinstance(date,str) or len(date)!=10: raise SystemExit(f'{c}: missing valid date')
        if not d.get('source'): raise SystemExit(f'{c}: missing source')
        if not d.get('quality'): raise SystemExit(f'{c}: missing quality')
        status,action,reason=audit_policy(c,audit_rows.get(c))
        expected[c]=date
        rates[c]={'current_as_of':date,'status':status,'action':action,'reason':reason}
    out={
      'schema':'GMFQ_RATES_AUDIT_METADATA_V2',
      'audit_date':a.audit_date,
      'source_context':'Rates freshness metadata derived from the same unified audit used to build the candidate.',
      'expected_rates':expected,
      'rates':rates,
      'audit_summary':(audit or {}).get('summary')
    }
    result={'status':'PASS','currencies':len(ORDER),'audit_date':a.audit_date,'output':out}
    if a.audit_current:
        cur=json.loads(CURRENT.read_text())
        result['matches_current']=cur==out
        if cur!=out:
            drift=[]
            for k in ['schema','audit_date','source_context','expected_rates','rates','audit_summary']:
                if cur.get(k)!=out.get(k): drift.append(k)
            result['current_drift_fields']=drift
    if a.output:
        pathlib.Path(a.output).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0

if __name__=='__main__': sys.exit(main())
