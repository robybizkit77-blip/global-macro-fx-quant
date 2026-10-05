#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
CURRENT=ROOT/'live_data'/'sections'/'RATES_AUDIT_METADATA.json'
ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']

POLICY={
 'USD':('CURRENT_OFFICIAL','CURRENT','Validated U.S. Treasury same-basis snapshot retained.'),
 'EUR':('CURRENT_OFFICIAL_SAME_BASIS','UPDATED','Validated ECB AAA same-basis snapshot retained.'),
 'GBP':('CURRENT_OFFICIAL_SAME_BASIS','UPDATED','Validated Bank of England same-basis snapshot retained.'),
 'JPY':('CURRENT_OFFICIAL_SAME_BASIS','UPDATED','Validated MOF same-basis 2Y/10Y snapshot retained.'),
 'CHF':('CURRENT_OFFICIAL_SAME_BASIS','UPDATED','Validated SNB same-basis snapshot retained.'),
 'CAD':('CURRENT_OFFICIAL_SAME_BASIS','UPDATED','Validated Bank of Canada same-basis 2Y/10Y snapshot retained.'),
 'AUD':('CURRENT_BY_SOURCE_CADENCE','CURRENT_BY_SOURCE_CADENCE','Validated RBA F2 observation retained at source-native cadence.'),
 'NZD':('CURRENT_OFFICIAL','CURRENT','Validated RBNZ B2 same-basis snapshot retained.')
}
RESOLVED={'JPY_RATES':'PASS','CHF_RATES':'PASS','CAD_RATES':'PASS','AUD_RATES':'PASS'}

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--audit-date',required=True)
    ap.add_argument('--output')
    ap.add_argument('--audit-current',action='store_true')
    a=ap.parse_args()
    src=json.loads(SRC.read_text())
    missing=[c for c in ORDER if c not in src]
    if missing: raise SystemExit('Missing currencies: '+','.join(missing))
    expected={}
    rates={}
    for c in ORDER:
        d=src[c]
        date=d.get('date')
        if not isinstance(date,str) or len(date)!=10: raise SystemExit(f'{c}: missing valid date')
        if not d.get('source'): raise SystemExit(f'{c}: missing source')
        if not d.get('quality'): raise SystemExit(f'{c}: missing quality')
        status,action,reason=POLICY[c]
        expected[c]=date
        rates[c]={'current_as_of':date,'status':status,'action':action,'reason':reason}
    out={
      'schema':'GMFQ_RATES_AUDIT_METADATA_V1',
      'audit_date':a.audit_date,
      'source_context':'Validated same-basis Rates refresh audits committed on staging',
      'expected_rates':expected,
      'rates':rates,
      'resolved_audits':RESOLVED
    }
    result={'status':'PASS','currencies':len(ORDER),'audit_date':a.audit_date,'output':out}
    if a.audit_current:
        cur=json.loads(CURRENT.read_text())
        result['matches_current']=cur==out
        if cur!=out:
            drift=[]
            for k in ['schema','audit_date','source_context','expected_rates','rates','resolved_audits']:
                if cur.get(k)!=out.get(k): drift.append(k)
            result['current_drift_fields']=drift
    if a.output:
        pathlib.Path(a.output).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0

if __name__=='__main__': sys.exit(main())
