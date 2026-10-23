#!/usr/bin/env python3
"""Read-only staging check for an official RBNZ B2 *first* review.

A public-page observation plus its old-snapshot overlap is NOT a second
independent review, and does not authorize any promotion to live Rates.
"""
from __future__ import annotations
import argparse
from datetime import date
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
STAGED=ROOT/"validation/fixtures/rbnz_b2_official_table_2026-10-23_first_review_ONLY.json"
CERTIFIED=ROOT/"validation/fixtures/rbnz_b2_official_table_2026-10-19_review_required.json"
RATES=ROOT/"live_data/sections/NATIVE_RATES_DATA.json"
REGISTRY=ROOT/"validation/RATES_SOURCE_ADAPTERS_V1_2026-10-05.json"
SCHEMA="GMFQ_RBNZ_B2_OFFICIAL_HTML_TABLE_EVIDENCE_V1"
OFFICIAL_URL="https://www.rbnz.govt.nz/en/statistics/series/exchange-and-interest-rates/wholesale-interest-rates"

def validate(candidate:dict, prior:dict, rates:dict, registry:dict)->dict:
    def require(ok,msg):
        if not ok: raise ValueError("NZD_STAGE_SOURCE_GUARD: "+msg)
    require(candidate.get("schema")==SCHEMA and candidate.get("source_url")==OFFICIAL_URL,
            "must be approved official RBNZ B2 summary source")
    require(candidate.get("authority")=="Reserve Bank of New Zealand" and
            candidate.get("status")=="FIRST_REVIEW_COMPLETE_SECOND_INDEPENDENT_REVIEW_PENDING" and
            candidate.get("usable_for_automatic_promotion") is False and
            candidate.get("live_data_promotion_allowed") is False and
            candidate.get("candidate_only") is True and
            candidate.get("independent_approval_reference") is None,
            "one-review staging evidence is not eligible for automatic promotion")
    require(candidate.get("source_release_date")=="2026-10-23" and
            candidate.get("observed_at_rome_date")=="2026-10-23",
            "official snapshot date mismatch")
    require(candidate.get("columns")=={
            "date":"Date",
            "two_year":"Secondary market government bond closing yields (%pa) / 2 year",
            "ten_year":"Secondary market government bond closing yields (%pa) / 10 year"},
            "2Y/10Y must be official government bond closing yields, not swaps")
    row=rates["NZD"];reg=registry["currencies"]["NZD"]
    old=row.get("date")
    require(old=="2026-10-16" and old==reg.get("current_snapshot") and
            candidate.get("snapshot_previously_certified")==old,
            "old live NZD official approved anchor changed")
    require(reg.get("automatic_promotion_allowed") is False and
            reg.get("adapter_status")=="OPERATIONAL_MANUAL_OFFICIAL_VERIFIED__RUNNER_ACCESS_BLOCKED",
            "cannot bypass manual-review policy")
    def index(source):
        rows=source.get("observations")
        require(isinstance(rows,list) and len(rows)>=6,"insufficient full RBNZ B2 history")
        days=[];d={}
        for x in rows:
            require(isinstance(x,dict) and set(x)=={"date","2Y","10Y"},"invalid table columns")
            v=x["date"]
            require(isinstance(v,str) and date.fromisoformat(v).isoformat()==v,
                    "bad observation date")
            require(date.fromisoformat(v).weekday()<5,"non-business-date observation")
            for tenor in ("2Y","10Y"):
                value=x[tenor]
                require(type(value) in (float,int) and math.isfinite(value) and -5<=value<=25,
                        "invalid official yield")
            days.append(v);d[v]=x
        require(days==sorted(set(days)),"duplicated or unordered dates")
        return d
    a=index(candidate);b=index(prior)
    require(old in a and old in b and
            abs(a[old]["2Y"]-row["2Y"])<1e-9 and abs(a[old]["10Y"]-row["10Y"])<1e-9,
            "new source disagrees with approved 16 Oct official closing pair")
    common=sorted(set(a)&set(b))
    require(len(common)>=5,"too few overlapping official older dates")
    for day in common:
        require(all(abs(a[day][t]-b[day][t])<1e-9 for t in ("2Y","10Y")),
                "new capture contradicts independently approved old historical rows")
    new=[d for d in sorted(a) if d>old]
    require(new and new==["2026-10-19","2026-10-20","2026-10-21","2026-10-22"],
            "unexpected or missing staging dates on 23 Oct first source capture")
    last=a[new[-1]]
    return {
        "schema":"GMFQ_NZD_B2_FIRST_REVIEW_STAGING_RECEIPT_V1",
        "status":"PENDING_INDEPENDENT_SECOND_REVIEW",
        "latest_staged_as_of":last["date"],"staged_2Y":last["2Y"],"staged_10Y":last["10Y"],
        "source":"RBNZ official B2 government benchmark closing yield 2Y and 10Y",
        "previously_certified_as_of":old,"old_overlap_rows_verified":len(common),
        "new_dates":new,
        "automatic_promotion_allowed":False,"live_rates_changed":False,
        "macro_scores_changed":False,"pair_rankings_changed":False,
        "additional_requirement":"Obtain independent second official source review and explicit manual approval; preserve current source registry and both existing reviewed fixture policies."
    }

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="/tmp/nzd-b2-new-source-staging.json")
    args=parser.parse_args()
    report=validate(json.loads(STAGED.read_text()),json.loads(CERTIFIED.read_text()),
                    json.loads(RATES.read_text()),json.loads(REGISTRY.read_text()))
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
    return 0

if __name__=="__main__":raise SystemExit(main())
