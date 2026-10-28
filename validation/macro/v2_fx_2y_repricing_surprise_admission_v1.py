#!/usr/bin/env python3
"""Research FX: reproduce 2Y changes from dated observations and block false surprises.

A displayed chg2_bp may not refer to the last two stored 2Y observations.
Never overwrite it, equate it with day-on-day repricing, or align changes
between countries with different observation dates. Derive paired changes
ONLY from two exact jointly observed end/previous dates in each pair.

Secondary forecast-only calendar events are not actual surprises. Official
6M OIS levels on the same day do not establish the same weekly reference or
comparable benchmark contract. CB Want/Can requires official communications.

No live score/rank, no publisher-time PIT, no price-event causality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path

from validation.macro.v2_domestic_candidate_explicit_formula_v1 import G8
from validation.macro.v2_fx_28pair_synchronized_evidence_gate_v1 import (
    ROOT, EVALUATION_DAY, SECTION, run as source_run
)

SCHEMA="GMFQ_MACRO_V2_FX_28PAIR_2Y_DATED_REPRICING_SURPRISE_ADMISSION_V1"
CPI_DISCLOSURE="SECONDARY_PRE_RELEASE_CONSENSUS_NOT_PUBLISHED_ACTUAL"
REPORTED_CHANGE_SCOPE="UNSPECIFIED_NOT_PROVEN_LAST_ADJACENT_HISTORY_OBSERVATIONS"
MAX_REFERENCE_GAP_CALENDAR_DAYS=7
CLAIMED_LAST_DELTA_TOLERANCE_BP=0.11

def need(ok,reason):
    if not ok:raise ValueError("FX_2Y_REPRICING_SURPRISE_ADMISSION_REJECTED: "+reason)

def strict_day(text):
    need(isinstance(text,str) and re.fullmatch(r"20\d\d-\d\d-\d\d",text),
         "strict ISO observation date required")
    result=date.fromisoformat(text)
    need(result.isoformat()==text and result<=date.fromisoformat(EVALUATION_DAY),
         "invalid or forward dated data")
    return result

def numeric(x):
    need(type(x) in (float,int) and math.isfinite(x),"finite numeric source observation")
    return float(x)

def inspect_2y(rates):
    need(isinstance(rates,dict) and set(rates)==set(G8),"canonical 8 currency native 2Y source")
    out={}
    for c in G8:
        r=rates[c]
        h=r.get("history2",{})
        ds=h.get("dates")
        vs=h.get("values")
        need(isinstance(ds,list) and isinstance(vs,list) and len(ds)==len(vs)
             and len(ds)>=3,"2Y dated history is essential")
        # Older JPY source dates may have formatting/inversion issues.
        # THIS audit certifies only the last two observations, not whole history.
        need(len(set(ds[-2:]))==2,"two recent observations required")
        prev=ds[-2]
        latest=ds[-1]
        a,b=strict_day(prev),strict_day(latest)
        need(a<b and r.get("date")==latest and h.get("last_date")==latest,
             c+": last two source observations must follow chronological order")
        vprev,vlast=numeric(vs[-2]),numeric(vs[-1])
        need(math.isclose(vlast,numeric(r.get("2Y")),rel_tol=0,abs_tol=1e-8)
             and math.isclose(vlast,numeric(h.get("last_value")),rel_tol=0,abs_tol=1e-8)
             and str(r.get("quality","")).startswith("FULL_CURRENT_OFFICIAL"),
             c+": native rate day, history last and official source mismatch")
        prev_bp=(vlast-vprev)*100
        claimed=numeric(r.get("chg2_bp"))
        conflict=abs(claimed-prev_bp)>CLAIMED_LAST_DELTA_TOLERANCE_BP
        out[c]={
            "currency":c,
            "last_2Y_date":latest,"previous_2Y_date":prev,
            "last_2Y_pct":vlast,"previous_2Y_pct":vprev,
            "calculated_latest_adjacent_history_change_bp":round(prev_bp,6),
            "displayed_chg2_bp":claimed,
            "displayed_minus_adjacent_history_bp":round(claimed-prev_bp,6),
            "chg2_source_reference_clock_verified_as_adjacent_history":False,
            "chg2_vs_adjacent_history":(
                "REPORTED_SCOPE_NOT_SAME_AS_ADJACENT_HISTORY"
                if conflict else "NUMERICALLY_COMPATIBLE_REFERENCE_SCOPE_STILL_UNVERIFIED"),
            "latest_observation_stale_on_research_day":
                (date.fromisoformat(EVALUATION_DAY)-b).days>7,
            "usable_for_model_2Y_repricing":False,
        }
    return out

def recent_history_index(r,currency):
    h=r["history2"]
    dates=h["dates"]
    vals=h["values"]
    # Work with last <=45-calendar-day segment; avoid sanitizing historical
    # non-ISO JPY legacy rows or silently sorting a possibly corrupt archive.
    lookup={}
    earliest=date.fromisoformat(EVALUATION_DAY).toordinal()-45
    raw_recent=[(d,v) for d,v in zip(dates,vals)
                if isinstance(d,str) and re.fullmatch(r"20\d\d-\d\d-\d\d",d)
                and date.fromisoformat(d).toordinal()>=earliest]
    prev=None
    for d,v in raw_recent:
        stamp=strict_day(d)
        need(prev is None or prev<stamp,
             currency+": recent rate observations duplicated or out of order")
        prev=stamp
        lookup[d]=numeric(v)
    need(r["date"] in lookup and lookup[r["date"]]==numeric(r["2Y"]),
         currency+": rate last day missing in historical contemporaneous window")
    return lookup

def inspect_consensus(calendar,seed):
    need(calendar.get("schema")=="GMFQ_MACRO_CONSENSUS_SECONDARY_V1"
         and calendar.get("status")=="ACTIVE_PARTIAL"
         and calendar.get("rules",{}).get("actual_not_used_as_pre_release_consensus") is True
         and calendar.get("rules",{}).get("core_score_impact")==0
         and calendar.get("rules",{}).get("never_promote_to_official") is True
         and calendar.get("rules",{}).get("official_calendar_remains_primary") is True,
         "secondary consensus never pre-authorizes surprises")
    need(seed.get("schema")=="GMFQ_MACRO_RELEASE_OFFICIAL_SEED_V1"
         and seed.get("status")=="ACTIVE_VERIFIED_SEED"
         and seed.get("consensus")=="NOT_INCLUDED",
         "official calendar only confirms release schedule, not consensus/actual")
    registered={(e.get("ccy"),e.get("date"),e.get("event_type"),e.get("title"))
                for e in seed["events"]}
    results=[]
    for event in calendar.get("events",[]):
        need(event.get("status")=="AVAILABLE"
             and event.get("actual_ignored_for_pre_release_consensus") is True
             and event.get("official_date_overridden") is False
             and event.get("ccy") in G8
             and event.get("provider")=="FOREX_FACTORY_FAIR_ECONOMY_WEEKLY"
             and event.get("confidence_grade")=="B"
             and (event.get("ccy"),event.get("official_date"),
                  event.get("event_type"),event.get("official_title")) in registered,
             "forecast event must correspond to unmodified official calendar release")
        day=strict_day(event["official_date"])
        need(day>date.fromisoformat(EVALUATION_DAY),"frozen 28 Oct consensus must be pre-release")
        forecast=event.get("consensus")
        need(isinstance(forecast,str) and forecast.strip()
             and event.get("previous") not in (None,""),
             "need explicitly available secondary forecast and previous")
        results.append({
            "event_key":event["event_key"],"currency":event["ccy"],
            "official_release_day":event["official_date"],
            "event_type":event["event_type"],
            "pre_release_secondary_consensus":forecast,
            "previous_print":event["previous"],
            "official_actual":None,
            "actual_publisher_release_clock":None,
            "forecast_capture_predates_event":True,
            "surprise_actual_minus_forecast":None,
            "surprise_available_for_FX":False,
            "status":CPI_DISCLOSURE,
        })
    need(len(results)==2 and set(x["currency"] for x in results)=={"USD","CAD"},
         "frozen secondary pre-release forecast-only set")
    return results

def evaluate(*,rates,source,calendar,seed,as_of=EVALUATION_DAY):
    need(as_of==EVALUATION_DAY,"dated research snapshot, no live availability inferred")
    need(source.get("schema")==
         "GMFQ_MACRO_V2_28PAIR_MATCHED_DAY_ECONOMIC_RATE_PRICING_GATE_V1"
         and source.get("safe_to_publish_D_json") is False
         and source.get("safe_to_recalculate_28_pairs") is False
         and source.get("summary",{}).get("pairs_total")==28,
         "previous source-sync gate unchanged")
    country=inspect_2y(rates)
    forecasts=inspect_consensus(calendar,seed)
    recent={c:recent_history_index(rates[c],c) for c in G8}
    pairs={}
    for pair,e in sorted(source["pair_evidence"].items()):
        need(e.get("pair")==pair and
             e.get("can_construct_model_relative_FX_score") is False,
             "no FX promotion from source matrix")
        a,b=pair.split("/")
        A,B=country[a],country[b]
        synchronized=A["last_2Y_date"]==B["last_2Y_date"]
        need(synchronized is e["2Y_same_observation_day"],
             "date matching must agree across source audits")
        prev_shared=None
        end=A["last_2Y_date"] if synchronized else None
        diffbp=None
        legbp=None
        if synchronized:
            common=sorted(set(recent[a]) & set(recent[b]))
            earlier=[x for x in common if x<end]
            if earlier:
                proposed=earlier[-1]
                if (strict_day(end)-strict_day(proposed)).days<=MAX_REFERENCE_GAP_CALENDAR_DAYS:
                    prev_shared=proposed
                    da=(recent[a][end]-recent[a][prev_shared])*100
                    db=(recent[b][end]-recent[b][prev_shared])*100
                    legbp={"base_2Y_change_bp":round(da,6),
                           "quote_2Y_change_bp":round(db,6)}
                    diffbp=round(da-db,6)
        pairs[pair]={
            "pair":pair,
            "source_last_2Y_date_base":A["last_2Y_date"],
            "source_last_2Y_date_quote":B["last_2Y_date"],
            "2Y_pair_end_day_strict_match":synchronized,
            "2Y_both_observations_same_start_end_days":
                prev_shared is not None,
            "2Y_common_start":prev_shared,
            "2Y_common_end":end if prev_shared else None,
            "2Y_legs_dated_changes_bp_DESCRIPTIVE_ONLY":legbp,
            "2Y_relative_change_bp_DESCRIPTIVE_ONLY":diffbp,
            "2Y_instruments_comparable_same_risk_free_basis":False,
            "source_original_release_day_PIT_2Y_proven":False,
            "official_6m_OIS_same_day_reference_only":
                e["6m_official_same_observation_day"],
            "official_6m_OIS_same_week_start_end_proven":False,
            "official_6m_OIS_relative_repricing_bp":None,
            "macro_actual_vs_consensus_surprise_score":None,
            "CB_Want_Can_confirmed_from_issuer_statements":False,
            "FX_strength_score":None,"FX_direction":None,
            "safe_for_beta":False,"safe_for_forward":False,
            "eligible_for_model_pair_ranking":False,
        }
    need(len(pairs)==28,"exact 28 FX pairs")
    conflicts=sorted(c for c,x in country.items()
                     if x["chg2_vs_adjacent_history"]==
                     "REPORTED_SCOPE_NOT_SAME_AS_ADJACENT_HISTORY")
    synced=sorted(p for p,x in pairs.items() if x["2Y_both_observations_same_start_end_days"])
    output={
        "schema":SCHEMA,
        "status":"2Y_OBSERVATION_CLOCK_REPRICING_DESCRIPTIVE__MACRO_SURPRISE_NOT_YET_OBSERVABLE",
        "as_of":EVALUATION_DAY,
        "2Y_reported_change_reference_not_automatically_adjacent_history":True,
        "old_2Y_change_values_not_overwritten":True,
        "2Y_instrument_conventions_unharmonized":True,
        "2Y_histories_not_original_release_day_PIT":True,
        "OIS_6m_relative_weekly_repricing_reference_dates_not_verified":True,
        "CB_Want_Can_requires_official_statements_not_inferred_from_rate_levels":True,
        "secondary_pre_release_forecasts_are_not_actual_surprises":True,
        "currencies":country,"consensus_future_events":forecasts,
        "pairs":pairs,
        "summary":{
            "currencies":8,
            "2Y_displayed_change_not_adjacent_history_count":len(conflicts),
            "2Y_displayed_change_not_adjacent_history_currencies":conflicts,
            "2Y_numeric_compatible_but_reference_unverified_currencies":
                sorted(set(G8)-set(conflicts)),
            "28_pair_universe":len(pairs),
            "2Y_pairs_same_last_observation_date":
                sum(p["2Y_pair_end_day_strict_match"] for p in pairs.values()),
            "2Y_pairs_same_start_and_end_date_and_7day_gap":len(synced),
            "2Y_pairs_with_matched_window_descriptive_change":synced,
            "2Y_pairs_certified_as_same_risk_free_instrument_definition":0,
            "official_6m_OIS_pairs_weekly_repricing_time_normalized":0,
            "secondary_future_forecasts_count":len(forecasts),
            "official_actuals_with_prior_locked_consensus":0,
            "validated_macro_surprises":0,
            "CB_Want_Can_verified_from_statement":0,
            "FX_pair_directional_signals":0,
            "FX_pair_rankings_rebuilt":0,
        },
        "safe_to_publish_new_D":False,
        "safe_to_change_28_pair_states":False,
        "safe_to_promote_a_2Y_change_to_tradable_signal":False,
        "safe_to_use_for_beta":False,"safe_to_use_for_forward":False,
        "writes_live_data":False,
    }
    output["receipt_sha256"]=hashlib.sha256(json.dumps(
        output,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return output

def run(as_of=EVALUATION_DAY):
    def load(name):
        return json.loads((SECTION/(name+".json")).read_text(encoding="utf-8"))
    return evaluate(rates=load("NATIVE_RATES_DATA"),
      source=source_run(as_of=as_of),
      calendar=load("MACRO_CONSENSUS_SECONDARY_V1"),
      seed=load("MACRO_RELEASE_OFFICIAL_SEED_V1"),as_of=as_of)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--as-of",default=EVALUATION_DAY)
    parser.add_argument("--out",type=Path)
    args=parser.parse_args()
    if args.out:
        need(args.out.resolve().is_relative_to(Path("/tmp")),
             "only /tmp research receipts permitted")
    out=run(as_of=args.as_of)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":out["status"],"summary":out["summary"],
          "safe_to_publish_new_D":False},sort_keys=True))

if __name__=="__main__":
    main()
