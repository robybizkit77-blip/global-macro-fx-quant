#!/usr/bin/env python3
"""Read-only G8 Macro thermometer -> Core D bridge readiness receipt.

Inflation/labour values and historical GDP web research are NOT a certified
replacement for the model's growth, policy or risk calibrations. Never mutate
D.json or upgrade pair thesis based on calendar age alone.
"""
from __future__ import annotations
import argparse
import json
from datetime import date, datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
G8=("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")
SECTIONS=ROOT/"live_data"/"sections"

def _day(value):
    if not isinstance(value,str) or len(value)!=10:
        raise ValueError("canonical core/price/reference day must be YYYY-MM-DD")
    result=date.fromisoformat(value)
    if result.isoformat()!=value:
        raise ValueError("non-canonical date")
    return result

def _observation(value):
    """Keep the publisher's precision; monthly does NOT mean publication day."""
    if not isinstance(value,str):
        raise ValueError("missing as_of observation")
    if len(value)==7:
        dt=date.fromisoformat(value+"-01")
        if dt.strftime("%Y-%m")!=value: raise ValueError("bad monthly date")
        return dt
    return _day(value)

def audit(core,heat,series,setup,as_of):
    today=_day(as_of)
    core_day=_day(core.get("asOf"))
    price_day=_day(setup.get("price_asof"))
    baseline=_day(setup.get("macro_baseline_asof"))
    if any(x>today for x in (core_day,price_day,baseline)):
        raise ValueError("future-dated macro snapshot or FX overlay")
    if setup.get("schema")!="GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1" or setup.get("pair_count")!=28:
        raise ValueError("unexpected 28 pair model contract")
    if setup.get("price_audit",{}).get("status")!="PASS" or setup["price_audit"].get("as_of")!=setup["price_asof"]:
        raise ValueError("FX official price overlay source audit missing")
    if heat.get("schema_version")!="GMFQ_MACRO_HEATMAP_V1":
        raise ValueError("macro heatmap not certified structure")
    if core.get("macro") is None or not all(k in core["macro"] for k in G8):
        raise ValueError("incomplete canonical core G8")
    if set(G8)-set(heat.get("currencies",{})) or set(G8)-set(series):
        raise ValueError("incomplete inflation/labour source G8")
    rows={}
    observed_dates=[]
    for ccy in G8:
        dims={}
        for dim in ("inflation","labour"):
            h=heat["currencies"][ccy].get(dim)
            if not isinstance(h,dict):
                raise ValueError(f"missing thermometer {ccy}.{dim}")
            leaf=h
            observed=leaf.get("as_of")
            date_value=_observation(observed)
            if date_value>today:
                raise ValueError(f"future-dated economic observation {ccy}.{dim}")
            if leaf.get("series_id") in (None,"") or not isinstance(leaf.get("latest_value"),(int,float)):
                raise ValueError(f"missing economic observation ID/value {ccy}.{dim}")
            observed_dates.append(date_value)
            dims[dim]={
                "series_id":leaf["series_id"],
                "observation_as_of":observed,
                "source_label":leaf.get("source"),
                "observation_frequency":leaf.get("frequency"),
                "days_from_observation_month_start":(today-date_value).days,
                "approved_as_core_weight":False,
            }
        rows[ccy]=dims
    baseline_matches=baseline==core_day
    # On-purpose separation: observing latest inflation/labour does NOT prove
    # model strength factors, policy spread mapping or scoring PIT are updated.
    return {
        "schema":"GMFQ_G8_MACRO_CORE_DAILY_BRIDGE_READINESS_V1",
        "status":"BLOCKED_UNCERTIFIED_CORE_RECALIBRATION" if baseline_matches
                 else "BROKEN_PAIR_MACRO_BASELINE_CONTRACT",
        "checked_as_of":today.isoformat(),
        "core_as_of":core_day.isoformat(),
        "core_age_calendar_days":(today-core_day).days,
        "pair_price_as_of":price_day.isoformat(),
        "pair_price_age_calendar_days":(today-price_day).days,
        "pair_macro_baseline_as_of":baseline.isoformat(),
        "pair_macro_baseline_matches_core":baseline_matches,
        "core_same_day_as_check":core_day==today,
        "core_matches_pair_price_day":core_day==price_day,
        "inflation_labour_dimensions_in_daily_refresh":2,
        "core_growth_dimension_rebuilt_by_daily_macro_pipeline":False,
        "core_policy_risk_and_positioning_rebuilt_by_daily_macro_pipeline":False,
        "historical_gdp_research_is_eligible_for_live_model":False,
        "source_observation_as_of_is_not_release_timestamp":True,
        "all_observation_dates_not_future":True,
        "daily_core_scoring_and_rank_rebuild_certified":False,
        "eligible_to_promote_new_macro_scores":False,
        "eligible_to_republish_28_pair_thesis":False,
        "audit_only_no_data_written":True,
        "first_action":"Implement independently certified Core D scoring/PIT bridge; test all G8 growth/inflation/labour, policy/rates and baseline revision rules before re-dating D.json",
        "currency_source_coverage":rows,
    }

def run(root=ROOT,as_of=None):
    p=root/"live_data"/"sections"
    read=lambda n:json.loads((p/(n+".json")).read_text(encoding="utf-8"))
    as_of=as_of or datetime.now().date().isoformat()
    return audit(read("D"),read("MACRO_THERMOMETER_DATA"),read("MACRO_SERIES"),
                 read("PAIR_SETUP_OPERATIONAL_VIEW"),as_of)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--as-of",default=None)
    parser.add_argument("--output",default=None)
    args=parser.parse_args()
    result=run(as_of=args.as_of)
    payload=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if args.output: Path(args.output).write_text(payload,encoding="utf-8")
    print(payload,end="")
    # Not a broken inflation/labour update. Explicitly RED for core readiness,
    # but a read-only status check must not stop independently valid source writes.
    return 0

if __name__=="__main__":
    raise SystemExit(main())
