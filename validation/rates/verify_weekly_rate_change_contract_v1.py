#!/usr/bin/env python3
"""Enforce rates 'chg2_bp/chg10_bp' WEEKLY (7d calendar anchor) semantics.

The published series use current rate minus latest actual observation on or
BEFORE end_date - 7 calendar days, not previous trading-day change. Never
replace the legitimate weekly number with last-two-observations arithmetic.

For each supported auto-fetched G8 2Y/10Y source, prove that weekly receipts,
underlying history and display deltas match; reject mutated candidates before
applying to live_data. CHF manual/stale rate lacks reference receipt: retain its
existing value but do not call it weekly certified. The NZD manually-reviewed
reference is inspected without claiming new freshness.

Read-only. No Core, Beta, Forward or FX score recalculation.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
LIVE=ROOT/"live_data/sections/NATIVE_RATES_DATA.json"
G8=("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")
AUTOMATIC=("USD","EUR","GBP","JPY","CAD","AUD")
WEEKLY_RECEIPT=("USD","EUR","GBP","JPY","CAD","AUD","NZD")
BPS=100.0
ROUND_DECIMALS=1
TOLERANCE_BPS=0.051
SCHEMA="GMFQ_RATES_2Y10Y_WEEKLY_REFERENCE_PREPUBLISH_CONTRACT_V1"

def ensure(ok,message):
    if not ok:raise ValueError("RATES_WEEKLY_CHANGE_CONTRACT_REJECTED: "+message)

def iso(x,why):
    ensure(isinstance(x,str) and len(x)==10,why+": ISO day required")
    try:d=date.fromisoformat(x)
    except ValueError:raise ValueError("RATES_WEEKLY_CHANGE_CONTRACT_REJECTED: "+why+": invalid day") from None
    ensure(d.isoformat()==x,why+": noncanonical day")
    return d

def finite(value,label):
    ensure(type(value) in (float,int) and math.isfinite(value),label+": finite rate required")
    return float(value)

def measure_one(currency,row,tenor):
    key="history2" if tenor=="2Y" else "history10"
    delta_name="chg2_bp" if tenor=="2Y" else "chg10_bp"
    receipt_name="weekly2_validation" if tenor=="2Y" else "weekly10_validation"
    hist=row.get(key)
    receipt=row.get(receipt_name)
    ensure(isinstance(hist,dict) and isinstance(receipt,dict),
           currency+"."+tenor+": missing historical source or weekly reference receipt")
    dates=hist.get("dates");values=hist.get("values")
    ensure(isinstance(dates,list) and isinstance(values,list)
           and len(dates)==len(values) and len(dates)>=3,
           currency+"."+tenor+": complete dated history required")
    end=row.get("date")
    end_day=iso(end,currency+"."+tenor+".end")
    start=receipt.get("start_date")
    start_day=iso(start,currency+"."+tenor+".start")
    cutoff=end_day-timedelta(days=7)
    ensure(start_day <= cutoff < end_day,
           currency+"."+tenor+": start MUST be on/before weekly seven-day cutoff")
    ensure(receipt.get("end_date")==end,
           currency+"."+tenor+": weekly receipt end date != source end")
    ensure(len(set(dates))==len(dates),
           currency+"."+tenor+": duplicate history observation days")
    # Historical JPY source contains older formatting irregularities: validate
    # actual ISO source days needed for the weekly reference, not unrelated old rows.
    index={d:i for i,d in enumerate(dates)}
    ensure(start in index and end in index,
           currency+"."+tenor+": receipt observation missing from source history")
    eligible=[]
    for d in dates:
        if not isinstance(d,str) or len(d)!=10:continue
        try:obs=iso(d,currency+"."+tenor+".recent")
        except ValueError:continue
        if obs <= cutoff:eligible.append(d)
    ensure(eligible and start==max(eligible),
           currency+"."+tenor+": not latest observed point at/before seven-day cutoff")
    p=finite(values[index[start]],currency+"."+tenor+".reference")
    now=finite(values[index[end]],currency+"."+tenor+".end")
    ensure(math.isclose(now,finite(row.get(tenor),currency+"."+tenor+".snapshot"),
                        rel_tol=0,abs_tol=1e-8)
           and hist.get("last_date")==end
           and math.isclose(now,finite(hist.get("last_value"),currency+"."+tenor+".historylast"),
                            rel_tol=0,abs_tol=1e-8),
           currency+"."+tenor+": canonical latest 2Y/10Y and history mismatch")
    ensure(math.isclose(p,finite(receipt.get("start_value"),
                                 currency+"."+tenor+".receipt start"),
                        rel_tol=0,abs_tol=1e-8)
           and math.isclose(now,finite(receipt.get("end_value"),
                                       currency+"."+tenor+".receipt end"),
                            rel_tol=0,abs_tol=1e-8),
           currency+"."+tenor+": weekly receipt values drift from actual history")
    displayed=finite(row.get(delta_name),currency+"."+tenor+".display")
    reported=finite(receipt.get("change_bp"),currency+"."+tenor+".receipt change")
    calc=round((now-p)*BPS,ROUND_DECIMALS)
    ensure(abs(calc-displayed)<=TOLERANCE_BPS
           and abs(calc-reported)<=TOLERANCE_BPS,
           currency+"."+tenor+": published weekly change disagrees with source/receipt")
    # This is NOT certified intraday, same-market-calendar or original-publisher PIT.
    return {
       "tenor":tenor,"interval_definition":"WEEKLY_REFERENCE_LAST_OBSERVATION_ON_OR_BEFORE_END_MINUS_7_CALENDAR_DAYS",
       "reference_seven_day_cutoff":cutoff.isoformat(),
       "source_reference_day":start,
       "source_end_day":end,
       "reference_value_pct":p,"end_value_pct":now,
       "calculated_change_bp":calc,
       "displayed_change_bp":displayed,
       "receipt_change_bp":reported,
       "last_two_observations_are_NOT_the_weekly_reference":True,
       "source_pit_release_day_certified":False,
       "weekly_source_receipt_matched":True,
    }

def validate(rates,reference=None):
    ensure(isinstance(rates,dict) and set(rates)==set(G8),
           "all 8 native rates rows required")
    out={}
    for c in G8:
        row=rates[c]
        ensure(isinstance(row,dict),"not a native rates row "+c)
        iso(row.get("date"),c+".date")
        if c=="CHF":
            # The Swiss source snapshot has no dated weekly2/10 receipts;
            # do not invent a seven-day history or block unrelated currencies.
            ensure(not row.get("weekly2_validation") and
                   not row.get("weekly10_validation"),
                   "CHF must stay separately reviewed until real weekly source receipts exist")
            out[c]={"status":"RETAINED_SOURCE_NO_WEEKLY_REFERENCE_RECEIPT",
                    "date":row["date"],
                    "weekly_2Y_10Y_certified":False,
                    "published_change_interpretation_unverified":True}
            continue
        ensure(c in WEEKLY_RECEIPT,c+" not an approved weekly source")
        ensure(str(row.get("quality","")).startswith("FULL_CURRENT_OFFICIAL"),
               c+": official rate source identity changed")
        r2=measure_one(c,row,"2Y")
        r10=measure_one(c,row,"10Y")
        ensure(math.isclose(round((finite(row["10Y"],c+".10Y")-
                                   finite(row["2Y"],c+".2Y"))*100,1),
                            finite(row.get("curve_bp"),c+".curve_bp"),
                            rel_tol=0,abs_tol=TOLERANCE_BPS),
               c+": yield curve arithmetic drift")
        out[c]={"status":"WEEKLY_2Y_10Y_CHANGE_SOURCE_RECEIPTS_VERIFIED",
                "date":row["date"],"quality":row["quality"],
                "2Y":r2,"10Y":r10,
                "weekly_2Y_10Y_certified":True,
                "is_current_session_proven":False,
                "source_first_publication_pit_certified":False}
    changed=[]
    if reference is not None:
        ensure(isinstance(reference,dict) and set(reference)==set(G8),
               "previous G8 candidate identity required")
        changed=[c for c in G8 if rates[c]!=reference[c]]
        ensure(not any(c=="CHF" for c in changed),
               "automatic CHF promotion forbidden without source review")
        ensure(set(changed) <= set(AUTOMATIC),
               "auto-update may change only approved six official daily rates")
        for c in changed:
            ensure(iso(rates[c]["date"],c+".candidate")>
                   iso(reference[c]["date"],c+".reference"),
                   "candidate cannot move observation date backward or rename old point")
    return {
        "schema":SCHEMA,"status":"PASS_WEEKLY_2Y10Y_REFERENCE_CONTRACT",
        "weekly_semantics_not_last_two_observations":True,
        "automatic_source_weekly_receipts_verified":6,
        "additional_manual_nzd_weekly_receipt_verified":True,
        "CHF_weekly_reference_unavailable_not_promoted":True,
        "source_actual_not_refreshed_by_this_audit":True,
        "currencies":out,
        "summary":{
            "currencies":len(out),
            "verified_with_dated_2Y_and_10Y_weekly_receipts":sum(
                x["weekly_2Y_10Y_certified"] for x in out.values()),
            "unverified_without_weekly_receipt":["CHF"],
            "changed_currencies":changed,
            "eligible_for_core_model_2Y_PIT_repricing":0,
            "FX_signals_emitted":0,
        },
        "writes_live_data":False,"safe_to_change_Core":False,
        "safe_to_change_28_pairs":False,
    }

def run(candidate_path=LIVE,reference_path=None):
    read=lambda p:json.loads(Path(p).read_text(encoding="utf-8"))
    return validate(read(candidate_path),
                    read(reference_path) if reference_path is not None else None)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",type=Path,default=LIVE)
    p.add_argument("--previous",type=Path)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    if a.out:ensure(a.out.resolve().is_relative_to(Path("/tmp")),
                    "receipt output restricted to /tmp")
    result=run(a.candidate,a.previous)
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"summary":result["summary"]},
                     sort_keys=True))
if __name__=="__main__":main()
