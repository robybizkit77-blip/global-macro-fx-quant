#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
from datetime import date, timedelta

import discover_cot_conservative_availability_calendar_v1 as base

POLICY='validation/COT_ULTRACONSERVATIVE_PIT_POLICY_V1_2026-10-11.json'

def later(a:str,b:str)->str:
    return max(date.fromisoformat(a),date.fromisoformat(b)).isoformat()

def transform(row:dict)->dict:
    r=dict(row)
    report=date.fromisoformat(r['report_date'])
    buffer_date=(report+timedelta(days=14)).isoformat()
    if r['availability_class']=='WITHHELD_UNRESOLVED_2018_2019_SHUTDOWN':
        r['research_available_from']=None
        r['research_pit_eligible']=False
        r['research_availability_class']='WITHHELD_OFFICIAL_SCHEDULE_KNOWN_ACTUAL_PUBLICATION_UNPROVEN'
        return r
    if r['actual_release_date']:
        actual_plus_one=(date.fromisoformat(r['actual_release_date'])+timedelta(days=1)).isoformat()
        r['research_available_from']=later(buffer_date,actual_plus_one)
        r['research_availability_class']='EXPLICIT_ACTUAL_DATE_WITH_14D_MINIMUM_BUFFER'
    else:
        r['research_available_from']=buffer_date
        r['research_availability_class']='OFFICIAL_STANDARD_RULE_WITH_14D_ANTI_LOOKAHEAD_BUFFER'
    r['research_pit_eligible']=True
    return r

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); args=ap.parse_args()
    policy=json.load(open(POLICY,encoding='utf-8'))
    dates=[]
    for y in base.YEARS: dates.extend(base.fetch_year(y))
    dates=sorted(set(dates))
    rows=[transform(base.candidate_row(d)) for d in dates]
    eligible=[r for r in rows if r['research_pit_eligible']]
    withheld=[r for r in rows if not r['research_pit_eligible']]
    out={
      'schema':'GMFQ_COT_ULTRACONSERVATIVE_PIT_CALENDAR_V1',
      'status':'RESEARCH_PIT_ELIGIBLE_SUBSET_READY',
      'policy_schema':policy['schema'],
      'scope':{'report_dates_total':len(rows),'eligible':len(eligible),'withheld':len(withheld)},
      'rules':{
        'normal_minimum_lag_calendar_days':14,
        'explicit_actual_release_override':'max(report_date+14d, actual_release_date+1d)',
        'unproven_shutdown_action':'WITHHOLD'
      },
      'edge_test_authorized_on_eligible_subset':len(eligible)>=policy['eligibility_intent']['minimum_required_rows_before_edge_test'],
      'production_signal_authorized':False,
      'sizing_authorized':False,
      'withheld_report_dates':[r['report_date'] for r in withheld],
      'rows':rows,
    }
    assert out['scope']=={'report_dates_total':458,'eligible':448,'withheld':10}
    assert out['edge_test_authorized_on_eligible_subset'] is True
    assert out['withheld_report_dates']==[
      '2018-12-24','2018-12-31','2019-01-08','2019-01-15','2019-01-22',
      '2019-01-29','2019-02-05','2019-02-12','2019-02-19','2019-02-26']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:out[k] for k in ('status','scope','edge_test_authorized_on_eligible_subset','withheld_report_dates')},indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
