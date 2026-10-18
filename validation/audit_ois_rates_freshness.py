#!/usr/bin/env python3
"""Read-only PIT-aware freshness audit; never mutates live sections."""
import datetime as dt, json, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
S=ROOT/'live_data'/'sections'
TODAY=dt.date.today()
def age(raw):
    try:return (TODAY-dt.date.fromisoformat(raw)).days
    except (TypeError,ValueError):return None
def evaluate():
    ois=json.loads((S/'OIS_OPERATIONAL_VIEW.json').read_text())['currencies']
    rates=json.loads((S/'NATIVE_RATES_DATA.json').read_text())
    rows=[];issues=[]
    for c in ('USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'):
        x=ois[c]; a=age(x.get('as_of')); green=str(x.get('operational_status','')).startswith('GREEN')
        horizons=x.get('horizons',{})
        matched=all(isinstance(horizons.get(h),dict) and isinstance(horizons[h].get('rate'),(int,float)) and (horizons[h].get('quote_as_of')==x.get('as_of') or (x.get('operational_status')=='GREEN_OFFICIAL' and not horizons[h].get('quote_as_of'))) for h in ('3m','6m','12m'))
        fresh=a is not None and 0<=a<=5 and matched
        if green and not fresh:issues.append({'layer':'OIS','ccy':c,'issue':'STALE_OR_INCOMPLETE_MARKED_GREEN','age_days':a,'matched_horizons':matched})
        r=rates.get(c,{}); ra=age(r.get('date'))
        if ra is None or ra<0 or ra>5:issues.append({'layer':'RATES','ccy':c,'issue':'STALE_OR_MISSING','age_days':ra})
        rows.append({'ccy':c,'ois_as_of':x.get('as_of'),'ois_status':x.get('operational_status'),'ois_current_complete':fresh,'rates_as_of':r.get('date'),'rates_current':ra is not None and 0<=ra<=5})
    return {'schema':'GMFQ_SOURCE_FRESHNESS_AUDIT_V1','as_of':TODAY.isoformat(),'status':'ISSUES_FOUND' if issues else 'PASS','rows':rows,'issues':issues}
if __name__=='__main__':
    output=evaluate();print(json.dumps(output,indent=2))
    # Diagnostics intentionally non-gating until upstream feeds repaired.
