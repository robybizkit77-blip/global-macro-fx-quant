#!/usr/bin/env python3
"""Synthetic next edition only in memory; never writes market data."""
import copy
import json
from datetime import date
from continue_nzd_postroll_observations_v1 import advance, verify_row, ANCHOR, NATIVE, POLICY

def reject(fn):
    try:
        fn()
    except (ValueError, KeyError, TypeError):
        return
    raise AssertionError("unsafe NZD observation accepted")

def main():
    anchor=json.loads(ANCHOR.read_text())
    native=json.loads(NATIVE.read_text())
    native["NZD"]=copy.deepcopy(anchor["canonical_row"])
    initial=anchor["reconciled_source"]
    assert advance(native,initial,anchor,POLICY,date(2026,11,27)) is None
    # Deliberately artificial test fixture, never written into the source feed.
    latest=copy.deepcopy(initial)
    latest["publication_date"]="2026-11-30"
    latest["last_observation_date"]="2026-11-27"
    latest["html_sha256"]="a"*64
    latest["xlsx_sha256"]="b"*64
    latest["observations"].append({"date":"2026-11-27","2Y":3.81,"10Y":4.71})
    latest["html_xlsx_matched_dates"]=latest["html_xlsx_matched_dates"][1:]+["2026-11-27"]
    out=advance(native,latest,anchor,POLICY,date(2026,11,30))
    assert out["NZD"]["date"]=="2026-11-27"
    assert out["NZD"]["legacy_pre_roll"]==native["NZD"]["legacy_pre_roll"]
    assert native["NZD"]["date"]=="2026-11-26"
    verify_row(out["NZD"],anchor,latest,POLICY)
    assert advance(out,latest,anchor,POLICY,date(2026,11,30)) is None
    for k,value in (("benchmark_2Y","Other"),("html_sha256","bad"),("eligible_for_core",True),("publication_date","2099-01-01")):
        altered=copy.deepcopy(latest); altered[k]=value
        reject(lambda:advance(native,altered,anchor,POLICY,date(2026,11,30)))
    altered=copy.deepcopy(latest); altered["observations"][0]["2Y"]+=.01
    reject(lambda:advance(native,altered,anchor,POLICY,date(2026,11,30)))
    altered=copy.deepcopy(latest); altered["html_xlsx_matched_dates"].pop()
    reject(lambda:advance(native,altered,anchor,POLICY,date(2026,11,30)))
    reject(lambda:advance(native,latest,anchor,POLICY,date(2026,12,20)))
    changed=copy.deepcopy(out["NZD"]); changed["2Y"]+=.01
    reject(lambda:verify_row(changed,anchor,latest,POLICY))
    reject(lambda:advance(native,latest,anchor,dict(POLICY,append_only=False),date(2026,11,30)))
    print("NZD_RECURRING_OBSERVATION_TESTS_PASS: synthetic fixture only; no data writes")

if __name__=="__main__":
    main()
