#!/usr/bin/env python3
"""SNB official CHF daily spot 2Y/10Y validation: no unapproved promotion."""
import copy
import datetime as dt
import json
from check_snb_same_basis_candidate_v1 import parse_candidate, inspect, KEYS

old="2026-09-30"
base={"timeseries":[
    {"metadata":{"key":KEYS["2Y"],"unit":"In percent","frequency":"P1D"},
     "values":[{"date":old,"value":0.287},{"date":"2026-10-20","value":0.303}]},
    {"metadata":{"key":KEYS["10Y"],"unit":"In percent","frequency":"P1D"},
     "values":[{"date":old,"value":0.586},{"date":"2026-10-20","value":0.612}]}
]}
def verify(payload):
    return parse_candidate(payload,certified_date=old,certified_2y=0.287,certified_10y=0.586)
x=verify(base)
assert x["status"]=="REVIEWABLE_NEW_OFFICIAL_PAIR"
assert x["source_as_of"]=="2026-10-20"
assert abs(x["curve_bp"]-30.9)<0.01
assert x["eligible_for_automatic_promotion"] is False
no_update=copy.deepcopy(base)
for row in no_update["timeseries"]: row["values"].pop()
assert verify(no_update)["status"]=="CURRENT_CANONICAL_DATE_RECONCILED"
mismatch=copy.deepcopy(base)
mismatch["timeseries"][0]["values"][0]["value"]=0.4
assert verify(mismatch)["status"]=="SOURCE_BASIS_NOT_RECONCILED"
for bad in [
    {"timeseries":[base["timeseries"][0]]},
    {"timeseries":base["timeseries"]+[base["timeseries"][0]]},
]:
    try:verify(bad)
    except ValueError:pass
    else:raise AssertionError("Must refuse missing/duplicated maturity")
for field,value in (("frequency","P1M"),("unit","CHF"),("key","EPB@SNB.rendeiduebd{EUR,2J}")):
    bad=copy.deepcopy(base)
    bad["timeseries"][0]["metadata"][field]=value
    try:verify(bad)
    except ValueError:pass
    else:raise AssertionError("Must refuse basis/units/frequency mismatch: "+field)
bad=copy.deepcopy(base)
bad["timeseries"][0]["values"][0]["date"]=bad["timeseries"][0]["values"][1]["date"]
try:verify(bad)
except ValueError:pass
else:raise AssertionError("Must refuse duplicate observation dates")
current={"CHF":{"date":old,"2Y":0.287,"10Y":0.586}}
requested=[]
def fake(url):
    requested.append(url)
    return base
audit=inspect(current,fetch=fake,now=dt.date(2026,10,23))
assert audit["candidate"]["status"]=="REVIEWABLE_NEW_OFFICIAL_PAIR"
assert audit["changed_native_rates"] is False
assert audit["changed_macro"] is False
assert audit["auto_promotion"] is False
assert "dimSel=D0%28CHF%29%2CD1%282J%2C10J%29" in requested[0]
assert "fromDate=2026-09-25" in requested[0]
assert "toDate=2026-10-23" in requested[0]
assert all(r["eligible_for_automatic_promotion"] is False for r in [audit["candidate"],verify(no_update),verify(mismatch)])
failed=inspect(current,fetch=lambda url:{"metadata":"only"},now=dt.date(2026,10,23))
assert failed["candidate"]["status"]=="SOURCE_CANDIDATE_WITHHELD"
assert failed["auto_promotion"] is False
assert len(json.dumps(audit))<2000
print("SNB_SAME_BASIS_2Y_10Y_SOURCE_CANDIDATE_PASS")
