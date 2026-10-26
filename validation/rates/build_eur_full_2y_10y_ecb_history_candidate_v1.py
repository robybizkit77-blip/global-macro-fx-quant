#!/usr/bin/env python3
"""Build an OFFLINE, unpublished ECB EUR 2Y+10Y source-aligned candidate.

Never infer original PIT publication dates. Never apply to live_data, payload,
Core, the site, or other G8 currency rates. Requires both original ECB CSVs.
"""
from __future__ import annotations

import argparse
import copy
import csv
from datetime import date, timedelta
import hashlib
import io
import json
import math
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
CURRENT=ROOT/"live_data/sections/NATIVE_RATES_DATA.json"
START="2025-09-16"
SERIES={
  "2Y":"YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y",
  "10Y":"YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
}
ENDPOINT="https://data-api.ecb.europa.eu/service/data/YC/"
SCHEMA="GMFQ_EUR_2Y_10Y_ECB_FULL_HISTORICAL_CANDIDATE_V1"
DAY_RE=re.compile(r"^\d{4}-\d{2}-\d{2}$")


def strict_day(x):
    if not isinstance(x,str) or not DAY_RE.fullmatch(x):
        raise ValueError("noncanonical original ECB date")
    dt=date.fromisoformat(x)
    if dt.isoformat()!=x:
        raise ValueError("noncanonical original ECB date")
    return dt


def parse_official(raw,tenor,latest):
    if tenor not in SERIES or not isinstance(raw,bytes) or len(raw)<1000:
        raise ValueError("ECB original named-tenor CSV missing or too short")
    try:
        text=raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("ECB official original CSV encoding") from exc
    rows=csv.DictReader(io.StringIO(text))
    if not rows.fieldnames or not {"KEY","TIME_PERIOD","OBS_VALUE"} <= set(rows.fieldnames):
        raise ValueError("ECB original named-series metadata absent")
    out={}
    for row in rows:
        if row["KEY"]!=SERIES[tenor]:
            raise ValueError("ECB series name/tenor mismatch")
        day=strict_day(row["TIME_PERIOD"])
        if not (strict_day(START)<=day<=latest):
            raise ValueError("ECB original row outside verified historical period")
        if day in out:
            raise ValueError("duplicate ECB source observation")
        val=float(row["OBS_VALUE"])
        if not math.isfinite(val) or not (-5<val<25):
            raise ValueError("ECB original source number invalid")
        out[day]=val
    if len(out)<260 or max(out)!=latest:
        raise ValueError("ECB original series incomplete or missing current latest date")
    return out


def existing_history(obj,tenor):
    h=obj.get("history"+tenor[:-1])  # history2/history10
    if not isinstance(h,dict):
        raise ValueError("missing EUR live mirror history")
    dates,values=h.get("dates"),h.get("values")
    if not isinstance(dates,list) or len(dates)!=len(values) or not dates:
        raise ValueError("inconsistent EUR live history")
    parsed={}
    previous=None
    for raw,v in zip(dates,values):
        d=strict_day(raw)
        if previous is not None and d<=previous:
            raise ValueError("unordered EUR live history")
        if type(v) not in (float,int) or not math.isfinite(v):
            raise ValueError("invalid EUR live rate value")
        parsed[d]=v
        previous=d
    if previous!=strict_day(obj["date"]):
        raise ValueError("EUR historic end not equal to rate snapshot as-of")
    return parsed


def classify(d2,d10):
    if d2>0 and d10>0:
        return "Bear steepening" if d10>d2 else "Bear flattening"
    if d2<0 and d10<0:
        return "Bull steepening" if d2<d10 else "Bull flattening"
    return "Movimento misto"


def build_candidate(rates,raw2,raw10):
    if not isinstance(rates,dict) or set(rates)!={"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"}:
        raise ValueError("G8 source object altered")
    src=rates["EUR"]
    if (src.get("quality")!="FULL_CURRENT_OFFICIAL"
       or "European Central Bank" not in src.get("source","")
       or "AAA Svensson" not in src.get("source","")):
        raise ValueError("ECB EUR historical source identity not proven")
    latest=strict_day(src["date"])
    old2=existing_history(src,"2Y");old10=existing_history(src,"10Y")
    if set(old2)!=set(old10):
        raise ValueError("legacy EUR 2Y and 10Y historical dates differ")
    official2=parse_official(raw2,"2Y",latest)
    official10=parse_official(raw10,"10Y",latest)
    if set(official2)!=set(official10):
        raise ValueError("official ECB 2Y and 10Y are not same-day complete")
    if min(official2)!=strict_day(START):
        raise ValueError("official historical archive does not cover legacy first date")
    for tenor,official in (("2Y",official2),("10Y",official10)):
        current=src[tenor]
        if type(current) not in (float,int) or not math.isclose(
                float(current),official[latest],rel_tol=0,abs_tol=0.000005):
            raise ValueError("official original "+tenor+" snapshot disagrees with live current value")
    out=copy.deepcopy(rates)
    eur=out["EUR"]
    reports={}
    for tenor,original,publisher,raw in (
            ("2Y",old2,official2,raw2),("10Y",old10,official10,raw10)):
        overlapping=sorted(set(original)&set(publisher))
        different=[d for d in overlapping if abs(original[d]-publisher[d])>0.000005]
        missing=sorted(set(publisher)-set(original))
        extra=sorted(set(original)-set(publisher))
        if extra:
            raise ValueError("live EUR mirror has dates absent in original ECB publisher")
        hh=eur["history"+tenor[:-1]]
        ordered=sorted(publisher.items())
        hh["dates"]=[d.isoformat() for d,v in ordered]
        hh["values"]=[v for d,v in ordered]
        hh["last_date"]=latest.isoformat()
        hh["last_value"]=publisher[latest]
        reports[tenor]={
            "stored_observations":len(original),
            "official_observations":len(publisher),
            "overlap":len(overlapping),
            "overlap_yield_mismatches":len(different),
            "new_publisher_date_count":len(missing),
            "new_publisher_dates":[d.isoformat() for d in missing],
            "max_mismatch_bp":round(max((abs(original[d]-publisher[d])*100
                                           for d in different),default=0),5),
            "first_mismatch_dates":[d.isoformat() for d in different[:5]],
            "original_csv_sha256":hashlib.sha256(raw).hexdigest(),
            "source_key":SERIES[tenor],
        }
    # Derive 7-calendar-day reference from a true SAME-DAY publisher history.
    cutoff=latest-timedelta(days=7)
    ref=max(d for d in official2 if d<=cutoff and d in official10)
    prev2,prev10=official2[ref],official10[ref]
    delta2=round((official2[latest]-prev2)*100,1)
    delta10=round((official10[latest]-prev10)*100,1)
    eur["chg2_bp"]=delta2
    eur["chg10_bp"]=delta10
    eur["curve_bp"]=round((official10[latest]-official2[latest])*100,1)
    eur["curve_state"]=classify(delta2,delta10)
    label=f"European Central Bank · AAA Svensson spot curve · {latest.isoformat()}"
    for tenor,published,prior,diff in (("2Y",official2,prev2,delta2),
                                       ("10Y",official10,prev10,delta10)):
        eur["weekly"+tenor[:-1]+"_validation"]={
            "start_date":ref.isoformat(),"start_value":prior,
            "end_date":latest.isoformat(),"end_value":published[latest],
            "change_bp":diff,"source":label,
            "note":"Original ECB same-basis "+tenor+
                   " curve; latest observation on/before 7-calendar-day cutoff."
        }
    eur["history2_quality"]="ECB_ORIGINAL_2Y_FULL_HISTORICAL_LATEST_VINTAGE_NOT_PIT"
    eur["history10_quality"]="ECB_ORIGINAL_10Y_FULL_HISTORICAL_LATEST_VINTAGE_NOT_PIT"
    eur["history_status"]="FULL_ECB_SAME_BASIS_2Y_10Y_RESEARCH_CANDIDATE_ONLY"
    eur["history_note"]="Both historical tenors sourced from original ECB SDMX ECB AAA Svensson 2Y/10Y curves; first-release publication instants not independently certified."

    # Source-proof notice to accompany prospective preview and eventual
    # approved live history promotion. The candidate is emphatically NOT
    # the production approval, even if its publisher CSVs match.
    # Freeze the paired original publisher points as an audit fingerprint;
    # the daily updater may append future points but must not rewrite them.
    original_pairing=[
        [d.isoformat(),official2[d],official10[d]]
        for d in sorted(official2)
    ]
    baseline_history_sha256=hashlib.sha256(
        json.dumps(original_pairing,separators=(",",":"),ensure_ascii=False).encode()
    ).hexdigest()
    eur["historical_curve_rebase"]={
        "schema":"GMFQ_EUR_2Y_10Y_HISTORY_REBASE_NOTICE_V1",
        "status":"RESEARCH_CANDIDATE_NOT_PUBLISHED",
        "source_authority":"European Central Bank",
        "instrument":"AAA Svensson euro area government spot 2Y and 10Y",
        "original_history_start":START,
        "original_history_end":latest.isoformat(),
        "original_point_count":len(original_pairing),
        "original_paired_values_sha256":baseline_history_sha256,
        "original_ecb_2y_csv_sha256":hashlib.sha256(raw2).hexdigest(),
        "original_ecb_10y_csv_sha256":hashlib.sha256(raw10).hexdigest(),
        "historical_first_release_pit_certified":False,
        "requires_explicit_release":True,
        "source_rebase_not_market_move":True,
        "chf_reference_beta_recalibration_not_official_chf_yield":True,
    }

    if eur["date"]!=src["date"] or any(out[cc]!=rates[cc] for cc in out if cc!="EUR"):
        raise ValueError("unexpected currency or source snapshot scope change")
    if any(eur[k]!=src[k] for k in ("2Y","10Y","date","quality","source","tenors")):
        raise ValueError("current official 2Y/10Y or other curve tenors were mutated")
    return out,{
        "schema":SCHEMA,
        "status":"CANDIDATE_FOR_SEPARATE_REVIEW_NOT_PUBLISHED",
        "as_of":latest.isoformat(),
        "source_authority":"European Central Bank",
        "start_date":START,
        "last_date":latest.isoformat(),
        "per_tenor_official_parity":reports,
        "weekly_reference_same_day":ref.isoformat(),
        "candidate_chg2_bp":delta2,"candidate_chg10_bp":delta10,
        "candidate_curve_bp":eur["curve_bp"],
        "source_history_rebase_notice_candidate_only":True,
        "official_paired_observations_sha256":baseline_history_sha256,
        "rebase_does_not_mean_market_move":True,
        "current_rate_snapshot_unchanged":True,
        "other_seven_G8_unchanged":True,
        "5Y_30Y_tenors_unchanged":True,
        "first_release_vintage_certified":False,
        "2Y_10Y_cross_country_basis_comparability_certified":False,
        "downstream_site_score_consumers_audited":False,
        "actual_production_promotion":False,
        "no_smoothing_or_date_imputation":True,
        "no_core_or_forward_mutation":True,
    }


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ecb-2y-original",type=Path,required=True)
    ap.add_argument("--ecb-10y-original",type=Path,required=True)
    ap.add_argument("--receipt",type=Path,required=True)
    ap.add_argument("--candidate",type=Path,required=True)
    args=ap.parse_args()
    if any(not p.resolve().is_relative_to(Path("/tmp")) for p in
           (args.candidate,args.receipt)):
        ap.error("read-only research candidate/receipt must be under /tmp")
    data=json.loads(CURRENT.read_text(encoding="utf-8"))
    output,receipt=build_candidate(
        data,args.ecb_2y_original.read_bytes(),args.ecb_10y_original.read_bytes())
    args.receipt.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    args.candidate.write_text(json.dumps(output,ensure_ascii=False,separators=(",",":"))+"\n")
    print(json.dumps(receipt,sort_keys=True))


if __name__=="__main__":
    main()
