#!/usr/bin/env python3
"""Offline guardrails for read-only CHF matched-date backfill staging."""
import copy, datetime as dt, json
from pathlib import Path
from stage_chf_paired_backfill_v1 import stage
from rates.recover_chf_snb_paired_history_v1 import SCHEMA

rates=json.loads(Path("live_data/sections/NATIVE_RATES_DATA.json").read_text())
anchor=rates["CHF"]
base=anchor["date"]
rows=[
 {"date":base,"2Y":anchor["2Y"],"10Y":anchor["10Y"],"curve_bp":round((anchor["10Y"]-anchor["2Y"])*100,3)},
 {"date":"2026-10-16","2Y":0.30,"10Y":0.54,"curve_bp":24.0},
 {"date":"2026-10-29","2Y":0.31,"10Y":0.55,"curve_bp":24.0}
]
e={"schema":SCHEMA,"status":"PAIRED_OFFICIAL_HISTORY_READY_FOR_REVIEW",
 "writes_operational_rates":False,"eligible_for_automatic_promotion":False,
 "historic_gap_backfilled_from_observations_not_interpolated":True,
 "unmatched_or_weekend_dates_fabricated":False,
 "base_date":base,"source_response_sha256":"a"*64,
 "new_paired_rows":2,"paired_source_rows":rows,"matched_paired_rows":3,
 "last_common_date":"2026-10-29","last_common_2Y":0.31,"last_common_10Y":0.55}
before=json.dumps(rates,sort_keys=True)
candidate,receipt=stage(rates,e,dt.date(2026,11,2))
assert candidate["CHF"]["date"]=="2026-10-29"
assert len(candidate["CHF"]["history2"]["dates"])==len(anchor["history2"]["dates"])+2
assert candidate["CHF"]["history10"]["values"][-1]==0.55
assert receipt["eligible_for_automatic_promotion"] is False
assert json.dumps(rates,sort_keys=True)==before
def reject(t):
    try: stage(rates,t,dt.date(2026,11,2))
    except (AssertionError,ValueError,KeyError): return
    raise AssertionError("Unsafe backfill accepted")
for key,value in [("status","SOURCE_BASIS_NOT_RECONCILED"),("eligible_for_automatic_promotion",True),("source_response_sha256","")]:
    z=copy.deepcopy(e);z[key]=value;reject(z)
z=copy.deepcopy(e);z["paired_source_rows"][1]["date"]="2026-10-17";reject(z)
z=copy.deepcopy(e);z["paired_source_rows"][1]["10Y"]=8.0;reject(z)
print("CHF_PAIRED_BACKFILL_STAGING_QA_PASS")
