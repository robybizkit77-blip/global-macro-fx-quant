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
ARCHIVED_NZD_POSTROLL = ROOT / "site/fx-quant-v2/nzd-b2-postroll-web-research.json"
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
    # The matched 2J/10J spot data arrive on the SNB statistical publication
    # cadence, whereas the separately published 10Y can advance each trading
    # day. A 14-day guard wrongly blocks refreshing the daily 10Y during
    # the middle/end of the monthly statistical publication interval.
    # Keep the original observation date and cap the dated anchor at 45 days.
    demand(0 <= (today-asof).days <= 45,
           "SNB matched spot pair outside 45-day statistical anchor window")
    y2,y10=yield_rate(c["2Y"]),yield_rate(c["10Y"])
    demand(abs(round((y10-y2)*100,1)-c["curve_bp"])<.11,
           "SNB 10Y−2Y arithmetic mismatch")
    demand(int(c["common_date_observations"])>=1, "Missing same-day matched source rows")
    demand(official["schema"]=="GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1" and
           official["provenance"]=="SNB_PUBLIC_PAGE_DATED_EXACT_10Y" and
           official["eligible_for_curve_spreads"] is False and
           official["has_current_2y"] is False, "Official Swiss 10Y context drift")
    ten_asof=date(official["as_of"])
    # The separately published 10Y is CONTEXT, not the source of the
    # independently matched SNB daily spot 2Y/10Y pair. A new verified pair
    # must not be blocked by a delayed/stale publication of isolated 10Y.
    demand(ten_asof<=today, "SNB isolated 10Y context dated in the future")
    ten_value=yield_rate(official["value_percent"])
    if ten_asof==asof:
        demand(abs(ten_value-y10)<=0.001,
               "Same-day official SNB 10Y contexts contradict each other")
    if previous and previous.get("paired_date"):
        demand(asof>=date(previous["paired_date"]), "SNB dated pair rollback")
    return {
        "pair_status":"OFFICIAL_SNBSAMEBASIS_RESEARCH_REVIEW_REQUIRED",
        "paired_date":asof.isoformat(), "2Y":y2, "10Y":y10,
        "curve_bp":round((y10-y2)*100,1),
        "paired_observations_in_source":c["common_date_observations"],
        "source":"Swiss National Bank · CHF Confederation daily spot 2J/10J",
        "source_url":SNB_SOURCE,
        "separate_10y":{"as_of":ten_asof.isoformat(),"10Y":ten_value,
                         "source_url":official["source_url"],"not_joinable_with_paired_2y":ten_asof!=asof},
        "official_pair_independently_dated":True,
        "matched_source_cadence":"SNB_STATISTICAL_MONTH_END_ANCHOR",
        "review_note":"Coppia 2Y/10Y dalla stessa serie spot SNB e stessa data, non dalla media di bond diversi. Il 10Y SNB pubblicato separatamente ha data propria e non può impedire l'uso della coppia ufficiale più recente; non si mescolano mai due date per una curva osservata.",
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



def extend_nzd_with_live_public_table(base: dict, live: dict, today: dt.date) -> dict:
    """Upgrade a dated *research-only* post-roll context from newly read RBNZ HTML.

    The official web page is a genuine primary publication, but it is not an
    independent XLSX reconciliation or a verified pre/post intraday market move.
    """
    demand(isinstance(base,dict) and base.get("status")=="RBNZ_GOVT_B2_WEB_RESEARCH_UNAPPROVED" and
           base.get("cross_roll_change_allowed") is False and
           base.get("eligible_for_core") is False and
           base.get("independent_xlsx_reconciled") is False,
           "prior NZD research benchmark invariants invalid")
    demand(isinstance(live,dict) and
           live.get("independent_xlsx_reconciled") is False and
           live.get("eligible_for_core") is False and
           live.get("eligible_for_fx_pair_engine") is False and
           live.get("eligible_for_backtests") is False,
           "not a research-only RBNZ B2 record")
    official=(live.get("schema")=="GMFQ_FXV2_NZD_RBNZ_B2_PUBLIC_HTML_RESEARCH_V1" and
              live.get("status")=="OFFICIAL_PUBLIC_HTML_TABLE_CAPTURED_RESEARCH_ONLY" and
              live.get("official_html_observed") is True and
              live.get("source_url")==
              "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates")
    vendor=(live.get("schema")=="GMFQ_FXV2_NZD_RBNZ_B2_REPUBLISHED_API_RESEARCH_V1" and
            live.get("status")=="THIRD_PARTY_API_RBNZ_B2_REPUBLISHED_RESEARCH_ONLY" and
            live.get("official_html_observed") is False and
            live.get("third_party_redistribution") is True and
            live.get("provider")=="eolas" and
            live.get("release_date_quality")=="UNVERIFIED_PROVIDER_AS_OF_ONLY" and
            live.get("source_url")==
            "https://eolas.fyi/datasets/rbnz_b2_wholesale_rates_daily" and
            live.get("provider_api_url")==
            "https://api.eolas.nz/v1/datasets/rbnz_b2_wholesale_rates_daily/data")
    demand(official or vendor,"unsupported B2 feed provenance, source, or entitlement")
    demand(live.get("benchmark_roll_date")==base["roll_date"]=="2026-10-30" and
           live.get("benchmark_2Y")==base["new_benchmark"]["2Y"]=="April 2029" and
           live.get("benchmark_10Y")==base["new_benchmark"]["10Y"]=="April 2037" and
           live.get("benchmark_note_date")=="2026-11-02",
           "RBNZ benchmark roll changed or needs review")
    last=date(live["as_of"])
    release=date(live["release_date"])
    demand(base["roll_date"]<=last.isoformat()<=today.isoformat() and
           last<=release and 0<=(today-last).days<=9 and
           release<=today,"NZD web daily source date invalid or old")
    if last.isoformat()<=base["latest_date"]:
        return base
    y2,y10=yield_rate(live["2Y"]),yield_rate(live["10Y"])
    demand(abs(round((y10-y2)*100,2)-live["curve_bp"])<.02,
           "NZD B2 official HTML daily curve arithmetic mismatch")
    start=base["after_roll"][0]
    demand(start["date"]==base["roll_date"] and
           start["date"]<last.isoformat() and
           yield_rate(start["2Y"])==3.96 and yield_rate(start["10Y"])==4.9,
           "NZD post-roll anchor has changed unexpectedly")
    # Need the official table row for the most recent observation, not a
    # synthetic extrapolation; no 29Oct->30Oct cross-roll movement is computed.
    rows=live.get("post_roll_table_rows",[])
    demand(isinstance(rows,list) and any(
        isinstance(row,dict) and row.get("date")==live["as_of"] and
        row.get("2Y")==y2 and row.get("10Y")==y10 for row in rows),
        "latest daily B2 observation not present in same-row public table")
    new=dict(base)
    new["latest_date"]=last.isoformat()
    new["latest_2Y"]=y2
    new["latest_10Y"]=y10
    new["latest_curve_bp"]=round((y10-y2)*100,1)
    new["after_roll"]=[start,{"date":last.isoformat(),"2Y":y2,"10Y":y10}]
    new["same_benchmark_change_bp"]={
        "2Y":round((y2-start["2Y"])*100,1),
        "10Y":round((y10-start["10Y"])*100,1),
        "start":start["date"],"end":last.isoformat()
    }
    new["source"]=("Reserve Bank of New Zealand · B2 government benchmarks (public HTML research)"
                   if official else "eolas API · RBNZ B2 redistributed research, not direct RBNZ fetch")
    new["source_url"]=live["source_url"]
    if official:
        new["source_release_date"]=live["release_date"]
        new["source_release_date_quality"]="OFFICIAL_RBNZ_PUBLIC_PAGE_DATE"
        new["source_capture_method"]="OFFICIAL_HTML_PUBLIC_TABLE_NOT_INDEPENDENT_XLSX"
        new["research_only_note"]="RBNZ government benchmark closing yields, public HTML; not XLSX-reconciled. Roll 30 Oct preserved; no Core or backtests."
    else:
        # Do NOT equate provider row date with RBNZ publication timestamp.
        new["source_release_date"]=None
        new["source_release_date_quality"]="NOT_VERIFIED_PROVIDER_AS_OF_ONLY"
        new["source_capture_method"]="EO_API_LICENSED_RBNZ_B2_REPUBLISHED_RESEARCH"
        new["research_only_note"]="Licensed eolas API redistributed RBNZ B2; new 2Y April 2029 and 10Y April 2037 instruments explicitly reconciled within each row. RBNZ publication timestamp and source XLSX not independently checked. Research only; no Core, FX pair signals, OIS or backtests."
    new["independent_xlsx_reconciled"]=False
    new["eligible_for_automatic_promotion"]=False
    return new



def extend_nzd_with_archived_manual_postroll(base: dict, archive: dict, today: dt.date) -> dict:
    """Reconcile *already stored* publisher-viewed B2 research; no new RBNZ HTTP.

    A previously checked dated research table should not be stranded in one
    site feed while the benchmark dossier still shows an older observation.
    This is **not** automatic primary-source collection or permission for FX
    scoring, and it is not an independent XLSX approval.
    """
    demand(isinstance(base,dict) and base.get("status")=="RBNZ_GOVT_B2_WEB_RESEARCH_UNAPPROVED"
           and base.get("cross_roll_change_allowed") is False
           and base.get("eligible_for_core") is False
           and base.get("independent_xlsx_reconciled") is False,
           "base research provenance not certified")
    demand(isinstance(archive,dict) and
           archive.get("schema")=="GMFQ_NZD_RBNZ_B2_POSTROLL_WEB_RESEARCH_V1"
           and archive.get("status")=="PUBLIC_OFFICIAL_WEB_RESEARCH_NOT_XLSX_RECONCILED"
           and archive.get("currency")=="NZD"
           and archive.get("source_url")==
             "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates"
           and archive.get("source_capture_method")==
             "PUBLIC_OFFICIAL_PAGE_MANUAL_RESEARCH_NOT_AUTOMATED_FETCH"
           and archive.get("official_web_display_observed") is True
           and archive.get("automated_access_authorized") is False
           and archive.get("independent_xlsx_reconciled") is False
           and archive.get("historical_benchmark_roll_continuity") is False
           and archive.get("no_interpolation") is True
           and archive.get("research_only") is True
           and archive.get("eligible_for_core") is False
           and archive.get("eligible_for_fx_pair_engine") is False
           and archive.get("eligible_for_backtests") is False
           and archive.get("eligible_for_automatic_promotion") is False
           and archive.get("canonical_government_rates_untouched") is True,
           "not a verified no-promotion manual source archive")
    demand(archive.get("benchmark_roll_date")==base["roll_date"]=="2026-10-30"
           and archive.get("benchmark_2Y")==base["new_benchmark"]["2Y"]=="April 2029"
           and archive.get("benchmark_10Y")==base["new_benchmark"]["10Y"]=="April 2037"
           and archive.get("before_roll_2Y")==base["old_benchmark"]["2Y"]=="May 2028"
           and archive.get("before_roll_10Y")==base["old_benchmark"]["10Y"]=="May 2036",
           "manual B2 benchmark roll identifiers differ")
    released=date(archive["source_release_date"])
    captured=date(archive["source_capture_date"])
    demand(released<=captured<=today,"archive claimed future publisher/capture date")
    rows=archive.get("daily_observations")
    demand(isinstance(rows,list) and 2<=len(rows)<=25,
           "manual research daily observation count invalid")
    parsed=[]
    for row in rows:
        demand(isinstance(row,dict) and set(row)=={"date","2Y","10Y"},
               "unrecognized research columns")
        day=date(row["date"])
        demand(base["roll_date"]<=day.isoformat()<=released.isoformat()
               and day.weekday()<5
               and (not parsed or day>date(parsed[-1]["date"])),
               "out-of-order, synthetic, pre-roll or future research market date")
        y2,y10=yield_rate(row["2Y"]),yield_rate(row["10Y"])
        parsed.append({"date":day.isoformat(),"2Y":y2,"10Y":y10})
    anchor=base["after_roll"][0]
    demand(parsed[0]==anchor and parsed[0]["date"]==base["roll_date"],
           "RBNZ new benchmark anchor disagrees with verified 30 Oct source")
    previously={p["date"]:p for p in base["after_roll"]}
    archived={p["date"]:p for p in parsed}
    for day,known in previously.items():
        if day in archived:
            demand(archived[day]==known,
                   "manual archive contradicts previously certified same-benchmark observation")
    last=parsed[-1]
    age=(today-date(last["date"])).days
    if age>14 or last["date"]<=base["latest_date"]:
        # A stored record is not continuously refreshed by running a job.
        return base
    out=dict(base)
    out["latest_date"]=last["date"]
    out["latest_2Y"]=last["2Y"]
    out["latest_10Y"]=last["10Y"]
    out["latest_curve_bp"]=round((last["10Y"]-last["2Y"])*100,1)
    out["after_roll"]=parsed
    out["same_benchmark_change_bp"]={
        "2Y":round((last["2Y"]-anchor["2Y"])*100,1),
        "10Y":round((last["10Y"]-anchor["10Y"])*100,1),
        "start":anchor["date"],"end":last["date"]
    }
    out["source"]="Reserve Bank of New Zealand B2 · archived manual public-page research"
    out["source_url"]=archive["source_url"]
    out["source_release_date"]=released.isoformat()
    out["source_release_date_quality"]="PUBLISHER_RELEASE_DATE_RECORDED_IN_MANUAL_ARCHIVE"
    out["source_capture_method"]="ALREADY_STORED_MANUAL_WEB_RESEARCH_NOT_RUNNER_FETCH"
    out["research_only_note"]=(
        "RBNZ B2 daily NZFMA government benchmarks, previously captured by human page review; "
        "now reconciled with the independent dated V2 research file. "
        "NOT an automated fresh RBNZ read; no XLSX reconciliation, official OIS, Core, FX pair "
        "signals or backtests; do not join yields across the 30 Oct benchmark roll.")
    out["cross_roll_change_allowed"]=False
    out["independent_xlsx_reconciled"]=False
    out["eligible_for_core"]=False
    out["eligible_for_pair_spreads"]=False
    out["eligible_for_backtests"]=False
    out["eligible_for_automatic_promotion"]=False
    return out


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
    p.add_argument("--nzd-daily-candidate",type=Path,
                   help="Already fetched official public RBNZ B2 HTML research receipt, or absent on source failure")
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
    nzd=old.get("NZD")
    try:
        base=nzd_context(obj("NZD_B2_GOVT_LATEST_WEB_RESEARCH"),
                         obj("NZD_B2_OCT30_WEB_CONTEXT_V1"),
                         obj("NZD_B2_GOVT_WEB_REVIEW_CONTEXT"),today)
        if not nzd or base["latest_date"]>nzd["latest_date"]:
            nzd=base
    except (ValueError,KeyError,TypeError) as exc:
        print("NZD_ARCHIVED_WEB_RESEARCH_NOT_ADVANCED "+str(exc))
    if nzd and ARCHIVED_NZD_POSTROLL.is_file():
        try:
            local=json.loads(ARCHIVED_NZD_POSTROLL.read_text(encoding="utf-8"))
            candidate=extend_nzd_with_archived_manual_postroll(nzd,local,today)
            if candidate.get("latest_date")!=nzd.get("latest_date"):
                print("NZD_ARCHIVED_MANUAL_B2_RESEARCH_RECONCILED",
                      nzd["latest_date"],candidate["latest_date"],
                      "NOT_NEW_AUTOMATED_SOURCE")
            nzd=candidate
        except (ValueError,KeyError,TypeError) as exc:
            print("NZD_ARCHIVED_B2_RESEARCH_NOT_ADVANCED "+str(exc))
    if args.nzd_daily_candidate and args.nzd_daily_candidate.is_file() and nzd:
        try:
            daily=json.loads(args.nzd_daily_candidate.read_text(encoding="utf-8"))
            nzd=extend_nzd_with_live_public_table(nzd,daily,today)
        except (ValueError,KeyError,TypeError, OSError) as exc:
            print("NZD_PUBLIC_B2_DAILY_RESEARCH_REJECTED "+str(exc))
    else:
        print("NZD_PUBLIC_B2_DAILY_SOURCE_UNAVAILABLE_PREVIOUS_RETAINED")
    report=create_report(chf,nzd,today.isoformat(),old)
    # Neither a fresh pipeline run nor an unchanged source date can create
    # a new market observation. Also detect genuine same-day revisions.
    old_chf=old.get("CHF") or {}
    old_nzd=old.get("NZD") or {}
    new_chf=report.get("CHF") or {}
    new_nzd=report.get("NZD") or {}
    watched_chf=("paired_date","2Y","10Y","separate_10y")
    watched_nzd=("latest_date","latest_2Y","latest_10Y","source_release_date","source_capture_method")
    if old_chf and old_nzd and all(old_chf.get(k)==new_chf.get(k) for k in watched_chf) and all(
       old_nzd.get(k)==new_nzd.get(k) for k in watched_nzd):
        print("FXV2_BENCHMARK_RESEARCH_SAME_OBSERVATIONS; no synthetic clock refresh")
        return
    new_dates=new_chf.get("paired_date"),new_nzd.get("latest_date")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"RESEARCH_V2_ONLY","CHF_paired":new_dates[0],"NZD_roll_segment":new_dates[1],
                      "official_core_changed":False},ensure_ascii=False))


if __name__=="__main__":
    main()
