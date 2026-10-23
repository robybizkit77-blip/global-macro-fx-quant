#!/usr/bin/env python3
"""Build, but NEVER publish, a full G8 NZD preview from two separate RBNZ web reads.

The independently downloaded RBNZ XLSX and an explicit reviewer approval
are still missing. This tool is read-only to live_data and the source registry;
it produces a /tmp candidate and a provenance receipt for further review.
"""
from __future__ import annotations
import argparse
import copy
from datetime import date,timedelta
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"validation"))
from check_nzd_rates_reviewed_snapshot_v1 import validate as check_approved_live
from check_nzd_b2_oct22_first_review_v1 import validate as check_first
FIRST=ROOT/"validation/fixtures/rbnz_b2_official_table_2026-10-23_first_review_ONLY.json"
SECOND=ROOT/"validation/fixtures/rbnz_b2_separate_official_web_reread_2026-10-23.json"
PRIOR=ROOT/"validation/fixtures/rbnz_b2_official_table_2026-10-19_review_required.json"
RATES=ROOT/"live_data/sections/NATIVE_RATES_DATA.json"
REGISTRY=ROOT/"validation/RATES_SOURCE_ADAPTERS_V1_2026-10-05.json"
SOURCE="Reserve Bank of New Zealand · B2 government bond closing yields"

def require(value:bool, why:str)->None:
    if not value: raise ValueError("NZD_SECOND_SOURCE_GUARD: "+why)

def check_second(first:dict,second:dict)->dict:
    require(second.get("schema")=="GMFQ_RBNZ_B2_SEPARATE_OFFICIAL_WEB_REREAD_V1",
            "second source schema")
    require(second.get("authority")=="Reserve Bank of New Zealand" and
            second.get("source_url")==
              "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates" and
            second.get("retrieval_path")==
              "https://www.rbnz.govt.nz/en/statistics/series/exchange-and-interest-rates/wholesale-interest-rates",
            "second read must be the same official RBNZ B2 publication")
    require(second.get("source_page_release")=="2026-10-23" and
            second.get("reviewed_date")=="2026-10-23" and
            second.get("retrieval_method")=="SEPARATE_OFFICIAL_WEB_PAGE_TEXT_INSPECTION",
            "separately dated direct web retrieval missing")
    require(second.get("column_group")=="Secondary market government bond closing yields (%pa)" and
            second.get("column_locations")=={"date":0,"two_year":8,"ten_year":10} and
            "not swap rates" in second.get("basis","").lower(),
            "must be government benchmark bond closes, not 2/10-year swap rates")
    require(second.get("status")=="SECOND_OFFICIAL_WEB_READ_MATCHES_FIRST_REVIEW__MANUAL_APPROVAL_PENDING" and
            second.get("independent_xlsx_review_completed") is False and
            second.get("independent_human_reviewer_confirmed") is False and
            second.get("automatic_promotion_allowed") is False and
            second.get("live_data_promotion_allowed") is False and
            second.get("manual_approval_reference") is None,
            "web re-read must NOT masquerade as XLSX/human approval")
    a,b=first.get("observations"),second.get("source_rows")
    require(isinstance(a,list) and isinstance(b,list) and len(a)>=10 and a==b,
            "independent web retrieval disagrees with first RBNZ B2 transcription")
    return {"status":"SEPARATE_WEB_READ_MATCHES_FIRST","rows":len(a),
            "latest":a[-1],"xls_independently_verified":False,
            "manual_approval":False}

def build(first:dict,second:dict,prior:dict,rates:dict,registry:dict)->tuple[dict,dict]:
    # Check current LIVE official same-basis rates independently from the draft.
    approved=check_approved_live(rates,registry,root=ROOT)
    require(approved["as_of"]=="2026-10-16","new candidate unexpected live base")
    source_receipt=check_first(first,prior,rates,registry)
    require(source_receipt["status"]=="PENDING_INDEPENDENT_SECOND_REVIEW",
            "first capture was not valid")
    second_receipt=check_second(first,second)
    current=rates["NZD"]
    prev_date=date.fromisoformat(current["date"])
    new_rows=first["observations"]
    require(new_rows[-1]["date"]=="2026-10-22" and
            new_rows[-1]["2Y"]==3.91 and new_rows[-1]["10Y"]==4.98,
            "source release changed; review prior to further updates")
    out=copy.deepcopy(rates)
    obj=out["NZD"]
    for tenor,hist_key in (("2Y","history2"),("10Y","history10")):
        hist=obj[hist_key]
        ds=hist["dates"];vs=hist["values"]
        require(len(ds)==len(vs) and ds==sorted(set(ds)) and ds[-1]==current["date"],
                tenor+" history not canonical before staging")
        combined=dict(zip(ds,vs))
        # Older missing intervals from source already reviewed in PR #382,
        # newer intervals from both web reads; never revise existing history.
        for row in prior["observations"]+new_rows:
            d=row["date"];v=row[tenor]
            if d in combined:
                require(type(combined[d]) in (float,int) and
                        abs(combined[d]-v)<1e-9,
                        "source revises existing "+tenor+" history date "+d)
            else:
                combined[d]=v
        ordered=sorted(combined.items())
        hist["dates"]=[d for d,v in ordered]
        hist["values"]=[v for d,v in ordered]
        hist["last_date"]="2026-10-22"
        hist["last_value"]=new_rows[-1][tenor]
        require(hist["dates"][-1]=="2026-10-22",tenor+" tail not last")
    end=new_rows[-1]
    cutoff=(date.fromisoformat(end["date"])-timedelta(days=7)).isoformat()
    prev={}
    bp={}
    for tenor,hkey in (("2Y","history2"),("10Y","history10")):
        points=list(zip(obj[hkey]["dates"],obj[hkey]["values"]))
        prior_points=[(d,v) for d,v in points if d<=cutoff]
        require(bool(prior_points),"missing prior-week "+tenor+" observation")
        d,v=max(prior_points)
        prev[tenor]=(d,v)
        bp[tenor]=round((end[tenor]-v)*100,1)
    obj["date"]=end["date"]
    obj["2Y"]=end["2Y"];obj["10Y"]=end["10Y"]
    obj["curve_bp"]=round((end["10Y"]-end["2Y"])*100,1)
    obj["chg2_bp"]=bp["2Y"];obj["chg10_bp"]=bp["10Y"]
    obj["curve_state"]=("Bear steepening" if bp["10Y"]>bp["2Y"] else
                        "Bear flattening" if bp["10Y"]<bp["2Y"] else "Parallel bear shift")
    obj["source"]=SOURCE+" · 2026-10-22 · SEPARATE WEB READ ONLY · NOT APPROVED"
    obj["quality"]="STAGING_ONLY_NOT_APPROVED"
    obj["freshness_status"]="STAGING_SECOND_WEB_READ_REQUIRES_APPROVAL"
    obj["freshness_note"]="Do not publish. RBNZ daily government benchmark close, second separate HTML retrieval checked; independently downloaded XLSX and explicit manual approval absent."
    for entry in obj["tenors"]:
        if entry["tenor"] in ("2Y","10Y"):
            entry["date"]=end["date"];entry["value"]=end[entry["tenor"]]
    for tenor,key in (("2Y","weekly2_validation"),("10Y","weekly10_validation")):
        d,v=prev[tenor]
        obj[key]={
            "start_date":d,"start_value":v,"end_date":end["date"],
            "end_value":end[tenor],"change_bp":bp[tenor],
            "source":SOURCE+" · 2026-10-22 · WEB-REVIEW CANDIDATE NOT APPROVED",
            "note":"Not live. Same-basis compared to latest observation on/before "+cutoff+"."
        }
    require(all(out[c]==rates[c] for c in rates if c!="NZD"),
            "preview must not mutate any other G8 currency")
    # Explicitly confirm the candidate fails the LIVE reviewed-source contract.
    try:
        check_approved_live(out,registry,root=ROOT)
    except ValueError:
        pass
    else:
        raise ValueError("DRAFT ERRONEOUSLY PASSED LIVE CERTIFICATION")
    receipt={
      "schema":"GMFQ_NZD_OFFICIAL_B2_OCT22_DRAFT_CANDIDATE_V1",
      "status":"PREVIEW_VALIDATED_NOT_APPROVED",
      "first_source_check":source_receipt["status"],
      "second_source_check":second_receipt["status"],
      "second_source_independent_xlsx":False,
      "separate_human_reviewer":False,
      "live_promotion_allowed":False,
      "old_live_as_of":current["date"],"draft_as_of":obj["date"],
      "draft_2Y":obj["2Y"],"draft_10Y":obj["10Y"],
      "weekly_change_bp":{"2Y":bp["2Y"],"10Y":bp["10Y"]},
      "weekly_reference":{k:d for k,(d,v) in prev.items()},
      "curve_state":obj["curve_state"],
      "added_dates_2Y":len(obj["history2"]["dates"])-len(current["history2"]["dates"]),
      "added_dates_10Y":len(obj["history10"]["dates"])-len(current["history10"]["dates"]),
      "unchanged_g8_currencies":sorted(set(rates)-{"NZD"}),
      "approval_required":"Human independent source certification of B2 values plus explicit manual approval PR. Do not update registry or live Rates without both.",
      "production_effect":"NONE"
    }
    return out,receipt

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",default="/tmp/NZD_B2_OCT22_DRAFT_ONLY.json")
    p.add_argument("--receipt",default="/tmp/NZD_B2_OCT22_REVIEW_ONLY.json")
    args=p.parse_args()
    for target in (args.candidate,args.receipt):
        resolved=Path(target).resolve()
        require(str(resolved).startswith("/tmp/"),"outputs must be under /tmp, never live_data")
    def load(path:Path)->dict:return json.loads(path.read_text(encoding="utf-8"))
    candidate,receipt=build(load(FIRST),load(SECOND),load(PRIOR),load(RATES),load(REGISTRY))
    Path(args.candidate).parent.mkdir(parents=True,exist_ok=True)
    Path(args.candidate).write_text(json.dumps(candidate,ensure_ascii=False,separators=(",",":"))+"\n")
    Path(args.receipt).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":raise SystemExit(main())
