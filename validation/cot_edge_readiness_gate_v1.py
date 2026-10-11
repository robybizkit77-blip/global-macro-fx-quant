#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--availability-discovery',required=True)
    ap.add_argument('--output',required=True)
    a=ap.parse_args()
    d=json.load(open(a.availability_discovery,encoding='utf-8'))
    assert d['status']=='DISCOVERY_PASS'
    total=d['scope']['report_dates']
    withheld=d['withheld_report_dates']
    candidate_only=d['class_counts'].get('OFFICIAL_STANDARD_THIRD_BUSINESS_DAY_CONSERVATIVE_NEXT_DAY__ACTUAL_NOT_INDIVIDUALLY_PROVEN',0)
    explicit_actual = total - withheld - candidate_only
    gates={
      'no_withheld_rows': withheld==0,
      'all_used_rows_have_individually_proven_actual_release_date': candidate_only==0,
      'publication_availability_fully_certified': withheld==0 and candidate_only==0,
    }
    result={
      'schema':'GMFQ_COT_EDGE_READINESS_V1',
      'status':'READY_FOR_PREDECLARED_EDGE_TEST' if all(gates.values()) else 'BLOCKED_TEMPORAL_PIT_NOT_FULLY_CERTIFIED',
      'counts':{'report_dates':total,'withheld':withheld,'candidate_only_standard_rule':candidate_only,'explicit_actual_or_special_case':explicit_actual},
      'gates':gates,
      'edge_test_authorized':all(gates.values()),
      'policy':{'production_signal_authorized':False,'sizing_authorized':False,'fail_closed':True}
    }
    Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=='__main__': main()
