#!/usr/bin/env python3
"""Refresh an informational CHF/NZD benchmark context for FX Quant V2 only.

CHF: use the existing anchored, same-series official SNB daily 2J + 10J parser.
NZD: split official RBNZ B2 HTML research observations at the benchmark roll.
No data are promoted into NATIVE_RATES_DATA, OIS, macro scores or FX pair signals.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "validation/rates"))
from check_snb_same_basis_candidate_v1 import inspect as inspect_snb, SOURCE as SNB_SOURCE

SCHEMA = "GMFQ_FXV2_CHF_NZD_BENCHMARK_RESEARCH_V1"
TARGET = ROOT / "site/fx-quant-v2/chf-nzd-benchmark-research.json"
DATA = ROOT / "live_data/sections"


def obj(n):
    return json.loads((DATA / (n + ".json")).read_text(encoding="utf-8"))


def demand(ok, message):
    if not ok:
        raise ValueError("FXV2_SAME_BASIS_GUARD: " + message)


def date(s):
    demand(isinstance(s,str) and len(s)==10, "bad date")
    d=dt.date.fromisoformat(s)
    demand(d.isoformat()==s, "non-ISO date")
    return d


def yield_rate(v):
    demand(type(v) in (float,int) and math.isfinite(v) and -5 <= v <= 25,
           "invalid yield")
    return float(v)


def chf_context(inspection, official, canonical, today, previous=None):
    demand(inspection.get("schema")=="GMFQ_SNB_CHF_2Y_10Y_OFFICIAL_CANDIDATE_V1",
           "SNB candidate schema mismatch")
    demand(inspection.get("source_url")==SNB_SOURCE, "CHF source is not SNB spot cube")
    demand(inspection.get("filter")=="D0(CHF),D1(2J,10J)",
           "CHF spot source tenor/currency filter drift")
    demand(inspection.get("changed_native_rates") is False and
           inspection.get("auto_promotion") is False, "CHF source allowed production write")
    c=inspection.get("candidate") or {}
    demand(c.get("status") in ("REVIEWABLE_NEW_OFFICIAL_PAIR","CURRENT_CANONICAL_DATE_RECONCILED"),
           "CHF candidate not independently anchored")
    demand(c.get("eligible_for_automatic_promotion") is False,
           "CHF candidate cannot be promoted into FX Core")
    demand(c.get("last_certified_as_of")==canonical["CHF"]["date"],
           "CHF canonical anchor changed")
    asof=date(c["source_as_of"])
    demand(0 <= (today-asof).days <= 14,
           "SNB matched spot pair outside research freshness window")
    y2,y10=yield_rate(c["2Y"]),yield_rate(c["10Y"])
    demand(abs(round((y10-y2)*100,1)-c["curve_bp"])<.11,
           "SNB 10Y−2Y arithmetic mismatch")
    demand(int(c["common_date_observations"])>=1, "Missing same-day matched source rows")
    demand(official["schema"]=="GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1" and
           official["provenance"]=="SNB_PUBLIC_PAGE_DATED_EXACT_10Y" and
           official["eligible_for_curve_spreads"] is False and
           official["has_current_2y"] is False, "Official Swiss 10Y context drift")
    ten_asof=date(official["as_of"])
    demand(0 <= (today-ten_asof).days<=14, "SNB spot 10Y context not valid")
    if previous and previous.get("paired_date"):
        demand(asof>=date(previous["paired_date"]), "SNB dated pair rollback")
    return {
        "pair_status":"OFFICIAL_SNBSAMEBASIS_RESEARCH_REVIEW_REQUIRED",
        "paired_date":asof.isoformat(), "2Y":y2, "10Y":y10,
        "curve_bp":round((y10-y2)*100,1),
        "paired_observations_in_source":c["common_date_observations"],
        "source":"Swiss National Bank · CHF Confederation daily spot 2J/10J",
        "source_url":SNB_SOURCE,
        "separate_10y":{"as_of":ten_asof.isoformat(),"10Y":yield_rate(official["value_percent"]),
                         "source_url":official["source_url"],"not_joinable_with_paired_2y":ten_asof!=asof},
        "review_note":"Coppia 2Y/10Y dalla stessa serie spot SNB e stessa data, non dalla media di bond diversi. Il 10Y SNB più recente compare separatamente e NON aggiorna la curva 2Y/10Y.",
        "eligible_for_core":False,"eligible_for_pair_spreads":False,
        "eligible_for_backtests":False,"eligible_for_automatic_promotion":False,
    }


def nzd_context(before, change, current, today, previous=None):
    demand(before["schema"]=="GMFQ_NZD_B2_LATEST_GOVT_HTML_RESEARCH_V1" and
           before["status"]=="SINGLE_OFFICIAL_RBNZ_HTML_TEXT_CAPTURE__INDEPENDENT_XLSX_REVIEW_PENDING",
           "RBNZ pre-roll research evidence invalid")
    demand(change["schema"]=="GMFQ_NZD_B2_OCT30_WEB_CONTEXT_V1" and
           change.get("benchmark_roll_on_observation_date") is True and
           change.get("eligible_for_trading_signals") is False,
           "RBNZ roll boundary invalid")
    demand(current["schema"]=="GMFQ_NZD_B2_GOVT_WEB_REVIEW_CONTEXT_V1" and
           current["status"]=="TWO_WEB_READS_MATCH__UNAPPROVED_RESEARCH_ONLY",
           "RBNZ web source not independent XLSX-approved")
    latest=current.get("latest_official_web_context") or {}
    demand(latest.get("status")=="LATEST_INDICATIVE_CONTEXT_NOT_CANONICAL" and
           latest.get("quality")=="OFFICIAL_WEB_DISPLAY_RESEARCH_NOT_XLSX_RECONCILED" and
           latest.get("guards",{}).get("independent_xlsx_review_completed") is False,
           "RBNZ latest source misclassified as official approved")
    demand(before["source_url"].startswith("https://www.rbnz.govt.nz/") and
           latest["source_url"].startswith("https://www.rbnz.govt.nz/"),
           "RBNZ source domain inconsistent")
    end_old=before["latest_official_web_read_only"]
    pre=date(end_old["date"])
    roll=date(change["observed"])
    end=date(latest["as_of"])
    demand(pre < roll <= end <= today, "RBNZ benchmark order and calendar validity")
    demand(0<=(today-end).days<=14, "RBNZ research reading too old")
    benchmark=latest["benchmarks"]
    demand(date(benchmark["roll_date"])==roll and
           benchmark["two_year_before"]!=benchmark["two_year_from"] and
           benchmark["ten_year_before"]!=benchmark["ten_year_from"],
           "RBNZ 2Y/10Y roll instruments not explicitly identified")
    if previous and previous.get("latest_date"):
        demand(end>=date(previous["latest_date"]),"RBNZ context rollback")
    old2,old10=yield_rate(end_old["2Y"]),yield_rate(end_old["10Y"])
    roll2,roll10=yield_rate(change["government_bond_2y"]),yield_rate(change["government_bond_10y"])
    new2,new10=yield_rate(latest["government_bond_2y_pct"]),yield_rate(latest["government_bond_10y_pct"])
    spread=round((new10-new2)*100,1)
    demand(abs(spread-latest["quoted_curve_bp"])<.11,"RBNZ indicative curve mismatches same-day 2Y and 10Y")
    # No line connecting old/new benchmark; only calculate moves from roll-date onward.
    return {
        "status":"RBNZ_GOVT_B2_WEB_RESEARCH_UNAPPROVED",
        "source":"Reserve Bank of New Zealand B2 · secondary government bond closes",
        "source_url":latest["source_url"],
        "roll_date":roll.isoformat(),"latest_date":end.isoformat(),
        "old_benchmark":{"2Y":benchmark["two_year_before"],"10Y":benchmark["ten_year_before"]},
        "new_benchmark":{"2Y":benchmark["two_year_from"],"10Y":benchmark["ten_year_from"]},
        "before_roll":[{"date":pre.isoformat(),"2Y":old2,"10Y":old10}],
        "after_roll":[{"date":roll.isoformat(),"2Y":roll2,"10Y":roll10},
                      {"date":end.isoformat(),"2Y":new2,"10Y":new10}],
        "latest_2Y":new2,"latest_10Y":new10,"latest_curve_bp":spread,
        "same_benchmark_change_bp":{"2Y":round((new2-roll2)*100,1),
                                    "10Y":round((new10-roll10)*100,1),
                                    "start":roll.isoformat(),"end":end.isoformat()},
        "cross_roll_change_allowed":False,
        "research_only_note":"Cambio benchmark alla data indicata: due serie distinte. Le variazioni dopo il cambio si riferiscono agli stessi titoli, ma restano letture RBNZ HTML non riconciliate con XLSX.",
        "eligible_for_core":False,"eligible_for_pair_spreads":False,
        "eligible_for_backtests":False,"eligible_for_automatic_promotion":False,
        "independent_xlsx_reconciled":False
    }


def create_report(chf, nzd, inspected_as_of, old=None):
    demand(chf is not None or nzd is not None,"No validated context available")
    prior=old or {}
    return {
        "schema":SCHEMA,"generated_on":inspected_as_of,
        "quality":"RESEARCH_INFORMATIONAL_NOT_CANONICAL",
        "CHF":chf or prior.get("CHF"),"NZD":nzd or prior.get("NZD"),
        "same_benchmark_or_date_cross_roll_only":True,
        "source_dates_may_differ":True,
        "eligible_for_core":False,
        "eligible_for_fx_pair_engine":False,
        "eligible_for_backtests":False,
        "canonical_government_rates_untouched":True
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--as-of",type=dt.date.fromisoformat,
                   default=dt.datetime.now(dt.timezone.utc).date())
    p.add_argument("--output",type=Path,default=TARGET)
    p.add_argument("--no-network",action="store_true")
    args=p.parse_args()
    today=args.as_of
    old=json.loads(TARGET.read_text(encoding="utf-8"))
    demand(old["schema"]==SCHEMA,"Prior research feed schema changed")
    canonical=obj("NATIVE_RATES_DATA")
    inspection=inspect_snb(canonical,now=today) if not args.no_network else None
    official=obj("CHF_SNB_10Y_SPOT_CONTEXT")
    chf=None
    if inspection:
        try:
            chf=chf_context(inspection,official,canonical,today,old.get("CHF"))
        except (ValueError,KeyError,TypeError) as exc:
            print("CHF_SAME_BASIS_RESEARCH_NOT_ADVANCED "+str(exc))
    nzd=None
    try:
        nzd=nzd_context(obj("NZD_B2_GOVT_LATEST_WEB_RESEARCH"),
                        obj("NZD_B2_OCT30_WEB_CONTEXT_V1"),
                        obj("NZD_B2_GOVT_WEB_REVIEW_CONTEXT"),
                        today,old.get("NZD"))
    except (ValueError,KeyError,TypeError) as exc:
        print("NZD_BENCHMARK_RESEARCH_NOT_ADVANCED "+str(exc))
    report=create_report(chf,nzd,today.isoformat(),old)
    # Preserve original content when neither source observation has changed.
    old_dates=(old.get("CHF") or {}).get("paired_date"),(old.get("NZD") or {}).get("latest_date")
    new_dates=(report.get("CHF") or {}).get("paired_date"),(report.get("NZD") or {}).get("latest_date")
    if old_dates==new_dates and old.get("CHF") and old.get("NZD"):
        print("FXV2_BENCHMARK_RESEARCH_SAME_OBSERVATIONS; no synthetic clock refresh")
        return
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"RESEARCH_V2_ONLY","CHF_paired":new_dates[0],"NZD_roll_segment":new_dates[1],
                      "official_core_changed":False},ensure_ascii=False))


if __name__=="__main__":
    main()
