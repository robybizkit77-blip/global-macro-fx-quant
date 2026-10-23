#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
CURRENT=ROOT/'live_data'/'sections'/'RATES_AUDIT_METADATA.json'
ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']

# This is SOURCE AGE metadata, not a license to label a retained source
# snapshot as a current market observation. Audit date != observation date.
from datetime import date

ORDERED_LIVE={'USD','EUR','GBP','JPY','CAD'}
AUD_SOURCE='RESERVE_BANK_OF_AUSTRALIA_F2_WEEKLY_FILE'
NZD_SOURCE='RBNZ_B2_MANUAL_DOUBLE_REVIEW'
CHF_SOURCE='SNB_EXPORT_BLOCKED'
RECENT_MAX_CALENDAR_DAYS=5

def source_status(ccy: str, observation: str, audited: str) -> dict:
    observed=date.fromisoformat(observation)
    check=date.fromisoformat(audited)
    age=(check-observed).days
    if age<0:
        raise ValueError(f'{ccy}: observation date is after audit date')
    if ccy=='CHF':
        return {
            'status':'VALIDATED_HISTORICAL_SOURCE_BLOCKED',
            'action':'SOURCE_EXPORT_RECOVERY_REQUIRED',
            'source_access':CHF_SOURCE,
            'reason':'SNB 2Y/10Y same-basis source export blocked. Last verified observation retained, NOT current.'
        }
    if ccy=='NZD':
        return {
            'status':'MANUAL_REVIEWED_RECENT' if age<=RECENT_MAX_CALENDAR_DAYS else 'MANUAL_REVIEWED_LAGGING',
            'action':'MANUAL_OFFICIAL_REVIEW_REQUIRED' if age>RECENT_MAX_CALENDAR_DAYS else 'MANUAL_SOURCE_VERIFIED',
            'source_access':NZD_SOURCE,
            'reason':'RBNZ B2 reviewed same-date 2Y/10Y. Runner HTTP 403; no automatic promotion or currentness implied.'
        }
    if ccy=='AUD':
        return {
            'status':'SOURCE_CADENCE_VALIDATED' if age<=7 else 'SOURCE_CADENCE_LAGGING',
            'action':'SOURCE_CADENCE_REVIEW' if age>7 else 'SOURCE_CADENCE_ACCEPTED',
            'source_access':AUD_SOURCE,
            'reason':'RBA F2 government yield observations are daily inside a file published weekly; lag must follow publication cadence.'
        }
    if ccy in ORDERED_LIVE:
        return {
            'status':'RECENT_OFFICIAL_OBSERVATION' if age<=RECENT_MAX_CALENDAR_DAYS else 'OFFICIAL_OBSERVATION_LAGGING',
            'action':'SOURCE_DATE_VALIDATED' if age<=RECENT_MAX_CALENDAR_DAYS else 'SOURCE_REFRESH_REVIEW_REQUIRED',
            'source_access':'OFFICIAL_LIVE_FETCH',
            'reason':'Official same-basis yield snapshot; status measures calendar age, not provider latest-release certification.'
        }
    raise ValueError(f'Unknown G8 currency: {ccy}')

def build(src: dict, audit_date: str) -> dict:
    check=date.fromisoformat(audit_date).isoformat()
    if set(src)!=set(ORDER):
        raise ValueError('Expected exactly eight G8 currencies')
    expected={}
    rates={}
    for c in ORDER:
        d=src[c]
        observation=d.get('date')
        if not isinstance(observation,str):
            raise ValueError(f'{c}: missing observation date')
        obs=date.fromisoformat(observation).isoformat()
        if obs!=observation:
            raise ValueError(f'{c}: non-canonical observation date')
        if not d.get('source') or not d.get('quality'):
            raise ValueError(f'{c}: missing official source evidence')
        status=source_status(c,obs,check)
        expected[c]=obs
        rates[c]={
            'current_as_of':obs,
            'age_calendar_days':(date.fromisoformat(check)-date.fromisoformat(obs)).days,
            **status
        }
    return {
        'schema':'GMFQ_RATES_AUDIT_METADATA_V1',
        'audit_date':check,
        'source_context':'Source-date audit with official live vs manual/cadence/blocked distinctions; no core score effect',
        'expected_rates':expected,
        'rates':rates,
        'resolved_audits':{'JPY_RATES':'PASS','CHF_RATES':'PASS','CAD_RATES':'PASS','AUD_RATES':'PASS'}
    }

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--audit-date',required=True)
    ap.add_argument('--output')
    ap.add_argument('--audit-current',action='store_true')
    a=ap.parse_args()
    src=json.loads(SRC.read_text())
    out=build(src,a.audit_date)
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
