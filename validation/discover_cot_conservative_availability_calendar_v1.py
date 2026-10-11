#!/usr/bin/env python3
"""Build a non-canonical COT availability *candidate* for 2018-2026.

This discovery quantifies how much official CFTC Legacy Futures Only history could
be used without look-ahead under a conservative policy:
- ordinary rows: CFTC's official third-business-day publication rule, with use
  delayed to the following calendar day;
- explicit CFTC timing exceptions: override the ordinary schedule;
- unresolved exceptional windows: WITHHELD.

The output is NOT a Temporal-PIT certification and never writes runtime/history.
Its purpose is to measure candidate coverage and expose every unresolved date.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import io
import json
import pathlib
import urllib.request
import zipfile
from datetime import date, datetime, timedelta

YEARS=range(2018,2027)
BASE='https://www.cftc.gov/files/dea/history/deacot{year}.zip'
UA='global-macro-fx-quant/cot-conservative-availability-calendar-v1'
CODES={'EUR':'099741','GBP':'096742','JPY':'097741','CHF':'092741','AUD':'232741','NZD':'112741','CAD':'090741','USD':'098662'}

# CFTC explicit actual publication dates from Historical Special Announcements.
EXPLICIT_REPORT_ACTUAL={
    '2018-12-18':'2018-12-21', # last report explicitly stated as published Dec 21 in PR 7864-19
    '2020-12-21':'2020-12-28',
    '2021-06-15':'2021-06-21',
    '2025-09-30':'2025-11-19','2025-10-07':'2025-11-21','2025-10-14':'2025-11-25',
    '2025-10-21':'2025-12-02','2025-10-28':'2025-12-05','2025-11-04':'2025-12-09',
    '2025-11-10':'2025-12-10','2025-11-18':'2025-12-12','2025-11-25':'2025-12-15',
    '2025-12-02':'2025-12-17','2025-12-09':'2025-12-19','2025-12-16':'2025-12-23',
    '2025-12-23':'2025-12-29',
}
ION_ORIGINAL_TO_ACTUAL={
    '2023-02-03':'2023-02-24','2023-02-10':'2023-03-03','2023-02-17':'2023-03-08',
    '2023-02-24':'2023-03-10','2023-03-03':'2023-03-14','2023-03-10':'2023-03-16',
    '2023-03-17':'2023-03-21',
}
# The 2018-2019 shutdown press release provides an expected catch-up schedule,
# not per-report proven actual publication dates. Keep the affected backlog out.
UNRESOLVED_SHUTDOWN_START=date(2018,12,24)
UNRESOLVED_SHUTDOWN_END=date(2019,2,26)
# National Day of Mourning closures explicitly announced by CFTC / federal govt.
AD_HOC_CLOSURES={date(2018,12,5),date(2025,1,9)}


def nth_weekday(year:int,month:int,weekday:int,n:int)->date:
    d=date(year,month,1)
    shift=(weekday-d.weekday())%7
    return d+timedelta(days=shift+7*(n-1))

def last_weekday(year:int,month:int,weekday:int)->date:
    d=date(year,month,calendar.monthrange(year,month)[1])
    return d-timedelta(days=(d.weekday()-weekday)%7)

def observed_fixed(year:int,month:int,day:int)->date:
    d=date(year,month,day)
    if d.weekday()==5: return d-timedelta(days=1)
    if d.weekday()==6: return d+timedelta(days=1)
    return d

def federal_holidays(year:int)->set[date]:
    h={
      observed_fixed(year,1,1),
      nth_weekday(year,1,0,3), # MLK
      nth_weekday(year,2,0,3), # Washington's Birthday
      last_weekday(year,5,0),
      observed_fixed(year,7,4),
      nth_weekday(year,9,0,1),
      nth_weekday(year,10,0,2),
      observed_fixed(year,11,11),
      nth_weekday(year,11,3,4),
      observed_fixed(year,12,25),
    }
    if year>=2021: h.add(observed_fixed(year,6,19))
    # New Year's Day of next year can be observed Dec 31 of current year.
    nxt=observed_fixed(year+1,1,1)
    if nxt.year==year: h.add(nxt)
    return h

def is_business_day(d:date)->bool:
    return d.weekday()<5 and d not in federal_holidays(d.year) and d not in AD_HOC_CLOSURES

def third_business_day_after(report:date)->date:
    d=report; count=0
    while count<3:
        d+=timedelta(days=1)
        if is_business_day(d): count+=1
    return d

def fetch_year(year:int)->list[str]:
    req=urllib.request.Request(BASE.format(year=year),headers={'User-Agent':UA,'Accept':'application/zip,*/*;q=0.8'})
    with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members=[n for n in z.namelist() if not n.endswith('/')]
        if len(members)!=1: raise RuntimeError(f'{year}: unexpected ZIP members {members}')
        text=z.read(members[0]).decode('latin-1')
    per_code={code:set() for code in CODES.values()}
    for row in csv.reader(io.StringIO(text)):
        if len(row)<10: continue
        code=row[3].strip().strip('"')
        if code not in per_code: continue
        d=datetime.strptime(row[2].strip().strip('"'),'%Y-%m-%d').date().isoformat()
        per_code[code].add(d)
    sets=list(per_code.values())
    if not sets or any(s != sets[0] for s in sets[1:]):
        raise RuntimeError(f'{year}: G8 report-date sets differ')
    return sorted(sets[0])

def candidate_row(report_s:str)->dict:
    report=date.fromisoformat(report_s)
    scheduled=third_business_day_after(report)
    scheduled_s=scheduled.isoformat()
    next_day=(scheduled+timedelta(days=1)).isoformat()

    if UNRESOLVED_SHUTDOWN_START <= report <= UNRESOLVED_SHUTDOWN_END:
        return {
          'report_date':report_s,'scheduled_release_date':scheduled_s,'actual_release_date':None,
          'candidate_available_from':None,'availability_class':'WITHHELD_UNRESOLVED_2018_2019_SHUTDOWN',
          'backtest_candidate_eligible':False,
        }

    if report_s in EXPLICIT_REPORT_ACTUAL:
        actual=EXPLICIT_REPORT_ACTUAL[report_s]
        return {
          'report_date':report_s,'scheduled_release_date':scheduled_s,'actual_release_date':actual,
          'candidate_available_from':(date.fromisoformat(actual)+timedelta(days=1)).isoformat(),
          'availability_class':'EXPLICIT_CFTC_ACTUAL_DATE_CONSERVATIVE_NEXT_DAY',
          'backtest_candidate_eligible':True,
        }

    # ION evidence maps original scheduled publication date -> actual publication.
    if scheduled_s in ION_ORIGINAL_TO_ACTUAL:
        actual=ION_ORIGINAL_TO_ACTUAL[scheduled_s]
        return {
          'report_date':report_s,'scheduled_release_date':scheduled_s,'actual_release_date':actual,
          'candidate_available_from':(date.fromisoformat(actual)+timedelta(days=1)).isoformat(),
          'availability_class':'CFTC_ION_ORIGINAL_SCHEDULE_JOIN_TO_EXPLICIT_ACTUAL_DATE',
          'backtest_candidate_eligible':True,
        }

    # Jan 2025 mourning: special announcement proves the week's actual release Jan 13;
    # the standard-rule join identifies Jan 7 as the unique report scheduled Jan 10.
    if report_s=='2025-01-07' and scheduled_s=='2025-01-13':
        # Because Jan 9 is an ad-hoc closure included in the business-day calendar,
        # the third-business-day rule itself lands on Jan 13. No separate inference needed.
        return {
          'report_date':report_s,'scheduled_release_date':scheduled_s,'actual_release_date':'2025-01-13',
          'candidate_available_from':'2025-01-14','availability_class':'STANDARD_RULE_PLUS_EXPLICIT_CFTC_CLOSURE_DELAY_CONFIRMATION',
          'backtest_candidate_eligible':True,
        }

    return {
      'report_date':report_s,'scheduled_release_date':scheduled_s,'actual_release_date':None,
      'candidate_available_from':next_day,
      'availability_class':'OFFICIAL_STANDARD_THIRD_BUSINESS_DAY_CONSERVATIVE_NEXT_DAY__ACTUAL_NOT_INDIVIDUALLY_PROVEN',
      'backtest_candidate_eligible':True,
    }

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); args=ap.parse_args()
    dates=[]
    for y in YEARS: dates.extend(fetch_year(y))
    dates=sorted(set(dates))
    rows=[candidate_row(d) for d in dates]
    classes={}
    for r in rows: classes[r['availability_class']]=classes.get(r['availability_class'],0)+1
    unresolved=[r for r in rows if not r['backtest_candidate_eligible']]
    out={
      'schema':'GMFQ_COT_CONSERVATIVE_AVAILABILITY_CALENDAR_DISCOVERY_V1',
      'status':'DISCOVERY_PASS',
      'authority':'U.S. Commodity Futures Trading Commission (CFTC)',
      'scope':{'start_report_date':rows[0]['report_date'],'end_report_date':rows[-1]['report_date'],'report_dates':len(rows)},
      'policy':{
        'official_standard_rule':'third business day after COT as-of/report date; CFTC weekly release time 3:30 p.m. ET',
        'ordinary_candidate_use':'following calendar day, deliberately later than scheduled release',
        'explicit_date_candidate_use':'following calendar day',
        'exception_overrides_standard_rule':True,
        'actual_release_date_required_for_final_certification':True,
        'standard_rule_rows_are_candidate_only_not_certified_actual_release':True,
        'unresolved_exception_action':'WITHHOLD',
        'production_write':False,
      },
      'class_counts':classes,
      'candidate_eligible_report_dates':sum(r['backtest_candidate_eligible'] for r in rows),
      'withheld_report_dates':len(unresolved),
      'withheld_rows':unresolved,
      'rows':rows,
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:out[k] for k in ('status','scope','class_counts','candidate_eligible_report_dates','withheld_report_dates','withheld_rows')},indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
