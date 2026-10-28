#!/usr/bin/env python3
"""Macro V2: 28-pair matched-date source quality, not an FX ranking.

The first explicit domestic candidate is within each country's history,
NOT a cross-currency score. Official 2Y and OIS/futures snapshots often
refer to different dates. Never synthesize a "same-day" policy signal
from lagged sources, proxy futures, two different 2Y benchmarks or CB
Want/Can inferred from a single interest-rate level.

Read-only, one dated audit, writes only /tmp if explicitly requested.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
from datetime import date
from pathlib import Path

from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    FORMULA, G8, run as domestic_run
)
from validation.macro.v2_core_quant_falsification_readiness_v1 import (
    ROOT, EVALUATION_DAY, prior_pair_universe, run as quantitative_run
)

SCHEMA="GMFQ_MACRO_V2_28PAIR_MATCHED_DAY_ECONOMIC_RATE_PRICING_GATE_V1"
SECTION=ROOT/"live_data/sections"
OFFICIAL_OIS={"GBP","JPY","CAD","AUD"}
PROXY_ONLY_OIS={"USD","EUR","CHF","NZD"}

def need(ok, reason):
    if not ok:
        raise ValueError("MACRO_28PAIR_MATCHED_DAY_REJECTED: "+reason)

def number(x,kind):
    need(type(x) in (int,float) and math.isfinite(x),kind+": finite numeric value required")
    return float(x)

def day(x):
    need(isinstance(x,str) and re.fullmatch(r"20\d\d-\d\d-\d\d",x),
         "source day YYYY-MM-DD required")
    d=date.fromisoformat(x)
    need(d.isoformat()==x and d <= date.fromisoformat(EVALUATION_DAY),
         "invalid or post-audit observation day")
    return d

def currencies_snapshot(domestic,rates,ois,readiness,cb):
    need(set(rates)==set(ois.get("currencies",{}))==set(cb)==set(G8),
         "eight canonical independent rates/OIS/CB country records required")
    need(readiness.get("schema")=="GMFQ_OIS_SOURCE_READINESS_VIEW_V1"
         and readiness.get("no_automatic_promotions") is True
         and readiness.get("no_core_score_effect") is True
         and readiness.get("no_backtest_effect") is True
         and readiness.get("prices_omitted") is True,
         "readiness index is not pricing evidence")
    source_status=readiness.get("currencies")
    need(isinstance(source_status,dict) and set(source_status)==PROXY_ONLY_OIS,
         "source readiness retains four blocked/indicative OIS currencies")
    need(domestic.get("formula_version")==FORMULA
         and domestic.get("historical_first_publication_PIT_not_certified") is True
         and domestic.get("safe_to_publish_D") is False
         and domestic.get("summary",{}).get("FX_scores_produced")==0,
         "new domestic candidate is not a relative FX strength score")
    d=domestic.get("countries")
    need(isinstance(d,dict) and set(d)==set(G8),"eight country research axes")
    country={}
    for c in G8:
        r,o,b=rates[c],ois["currencies"][c],cb[c]
        rate_day=day(r.get("date"))
        need(r.get("history2",{}).get("last_date")==r["date"]
             and number(r.get("history2",{}).get("last_value"),c+".2Y-last")==
                 number(r.get("2Y"),c+".2Y")
             and str(r.get("quality","")).startswith("FULL_CURRENT_OFFICIAL"),
             c+": official 2Y term structure source and actual history day required")
        ois_day=day(o.get("as_of"))
        cb_day=day(b.get("last_date"))
        policy=number(b.get("rate"),c+".policy_rate")
        is_official=c in OFFICIAL_OIS
        need(o.get("backtest_eligible_as_official") is is_official
             and o.get("quality")==("OFFICIAL_CERTIFIED" if is_official
                                    else "ESTIMATED_INFORMATIONAL")
             and o.get("official_status")==("ACTIVE" if is_official else "WITHHELD")
             and (source_status[c]["usable_for_policy_pricing"] is False
                  if not is_official else True),
             c+": never convert indicative OIS proxy to official")
        h=o.get("horizons",{}).get("6m")
        need(isinstance(h,dict),"mandatory 6m evidence or explicit no-value")
        level=h.get("rate")
        if is_official:
            level=number(level,c+".OIS6M")
            need(o.get("change_1w_available") is True and
                 number(h.get("change_1w_bp"),c+".OIS6M-weekly")<5000,
                 c+": official OIS weekly repricing source absent")
        else:
            need(o.get("change_1w_available") is False
                 and h.get("change_1w_bp") is None,
                 c+": secondary OIS cannot make a fake weekly repricing")
            if level is not None: level=number(level,c+".indicative_6m")
        dom=d[c]
        need(dom.get("FX_strength_candidate") is None
             and dom.get("eligible_to_recalculate_28_pairs") is False
             and dom.get("legacy_D_numbers_are_NOT_in_new_candidate_units") is True,
             c+": domestic z is not relative FX score")
        country[c]={
            "currency":c,
            "domestic_activity_candidate_z_WITHIN_COUNTRY_ONLY":
                number(dom["domestic_activity_candidate_z"],c+".domestic"),
            "domestic_source_quality_flags":dom.get("source_quality_flags",[]),
            "2Y_level_pct":number(r["2Y"],c+".2Y"),"2Y_observation_day":str(rate_day),
            "2Y_quality":r["quality"],"2Y_yield_convention_comparable_cross_G8":False,
            "CB_policy_rate_pct":policy,"CB_last_observed_decision_day":str(cb_day),
            "CB_Want_Can_publisher_statement_qualitatively_attested":False,
            "OIS_6m_level_pct":level,
            "OIS_6m_source_observation_day":str(ois_day),
            "OIS_6m_source_quality":o["quality"],
            "OIS_6m_is_official":is_official,
            "OIS_6m_1w_change_bp_official":h.get("change_1w_bp") if is_official else None,
            "OIS_6m_change_1w_pit_release_chain_certified":False,
            "2Y_and_official_OIS_same_day_own_currency":bool(is_official and rate_day==ois_day),
            "safe_to_use_for_FX_score":False,
        }
    return country

def evaluate(*,domestic,rates,ois,readiness,cb,setup,core,quant,as_of=EVALUATION_DAY):
    need(as_of==EVALUATION_DAY,"audit snapshot is not real-time FX market query")
    universe=prior_pair_universe(core,setup)
    need(quant.get("status")==
         "RESEARCH_QUANT_MATH_CHECKED__PIT_OOS_AND_OPERATIONAL_PROMOTION_BLOCKED"
         and quant.get("safe_to_publish_new_D") is False
         and quant.get("safe_to_recalculate_28_pairs") is False
         and quant.get("forward_truth",{}).get("three_date_archived_forward_observations_reconciled") is True
         and quant.get("summary",{}).get("new_core_scores_published")==0,
         "earlier quantitative prelaunch gate must remain blocked and auditable")
    need(ois.get("schema") is not None
         and ois.get("official_runtime_untouched") is True,
         "read-only official OIS view expected")
    sources=currencies_snapshot(domestic,rates,ois,readiness,cb)
    pairs=setup["pairs"]
    need(len(pairs)==28,"all 28 named G8 pairs must be present")
    evidence={}
    for key in sorted(pairs):
        p=pairs[key]
        name=p.get("canonical_pair")
        need(isinstance(name,str) and len(name)==7 and
             name[3]=="/" and key==name.replace("/",""),"pair orientation not canonical")
        a,b=name.split("/")
        need(a in G8 and b in G8 and a!=b,"invalid G8 currency pair")
        A,B=sources[a],sources[b]
        date2=A["2Y_observation_day"]==B["2Y_observation_day"]
        dateois=A["OIS_6m_source_observation_day"]==B["OIS_6m_source_observation_day"]
        bothofficial=A["OIS_6m_is_official"] and B["OIS_6m_is_official"]
        matched_official_ois=bool(dateois and bothofficial)
        matched_both=bool(date2 and matched_official_ois and
                          A["2Y_and_official_OIS_same_day_own_currency"] and
                          B["2Y_and_official_OIS_same_day_own_currency"])
        # Different country nominal government-bond YTM conventions;
        # a raw difference is a descriptive measurement, NOT a
        # standardized pure-policy 2Y spread or CB surprise.
        raw2y=round((A["2Y_level_pct"]-B["2Y_level_pct"])*100,6) if date2 else None
        rawois=round((A["OIS_6m_level_pct"]-B["OIS_6m_level_pct"])*100,6) \
            if matched_official_ois else None
        evidence[name]={
            "pair":name,
            "macro_comparison":"WITHIN_COUNTRY_ACTIVITY_SCORES_UNITS_NOT_CALIBRATED_CROSS_FX",
            "macro_strength_diff_z":None,
            "CB_Want_Can_pair_comparison_validated":False,
            "2Y_same_observation_day":date2,
            "2Y_date_base":A["2Y_observation_day"],
            "2Y_date_quote":B["2Y_observation_day"],
            "2Y_raw_yield_difference_bp_DESCRIPTION_ONLY":raw2y,
            "2Y_basis_instrument_homogeneity_certified":False,
            "6m_official_both_legs":bool(bothofficial),
            "6m_official_same_observation_day":matched_official_ois,
            "6m_OIS_date_base":A["OIS_6m_source_observation_day"],
            "6m_OIS_date_quote":B["OIS_6m_source_observation_day"],
            "6m_official_curve_difference_bp_DESCRIPTION_ONLY":rawois,
            "6m_weekly_relative_repricing_verified_same_expiry_methods":False,
            "2Y_and_official_6m_matched_same_day_both_legs":matched_both,
            "can_construct_model_relative_FX_score":False,
            "quality":"MATCHED_DESCRIPTIVE_REFERENCE_NO_FX_SIGNAL" if matched_both
                    else "PARTIAL_OR_ASYNC_INFO_NO_FX_SIGNAL",
            "original_D_pair_rebuilt":False,
        }
    need(set(frozenset(x.split("/")) for x in evidence)==
         {frozenset((a,b)) for a,b in itertools.combinations(G8,2)},
         "exact full 28 pair universe after orientation")
    same2=sum(x["2Y_same_observation_day"] for x in evidence.values())
    sameois=sum(x["6m_official_same_observation_day"] for x in evidence.values())
    full=sum(x["2Y_and_official_6m_matched_same_day_both_legs"] for x in evidence.values())
    potential=sum(x["6m_official_both_legs"] for x in evidence.values())
    eligible={c for c,x in sources.items() if x["2Y_and_official_OIS_same_day_own_currency"]}
    need(all(x["can_construct_model_relative_FX_score"] is False for x in evidence.values()),
         "must not infer FX rankings from snapshot level differences")
    result={
        "schema":SCHEMA,"research_as_of":EVALUATION_DAY,
        "source_2y_OIS_levels_as_loaded_not_fresh_intraday":True,
        "status":"28_PAIR_SAME_DAY_SOURCE_MATRIX_RESEARCH_ONLY_NO_FX_STRENGTH",
        "macro_candidate_formula":FORMULA,
        "macro_z_different_country_histories_not_directly_cross_comparable":True,
        "interest_differentials_not_pure_policy_surprise_and_instruments_different":True,
        "official_OIS_current_levels_not_equivalent_to_first_release_PIT_history":True,
        "CB_Want_Can_still_requires_qualitative_source_attestation":True,
        "source_quality_estimates_retained_in_context_not_promoted":True,
        "no_2026_10_28_market_availability_inferred":True,
        "source_currencies":sources,
        "pair_evidence":evidence,
        "summary":{
            "currencies":8,"pairs_total":28,
            "country_official_OIS_6m_count":sum(x["OIS_6m_is_official"] for x in sources.values()),
            "country_only_indicative_or_unavailable_OIS_6m_count":
                sum(not x["OIS_6m_is_official"] for x in sources.values()),
            "country_2Y_and_official_OIS_same_date_count":len(eligible),
            "countries_same_date_2Y_official_OIS":sorted(eligible),
            "pair_same_day_2Y_raw_description_only":same2,
            "pair_both_official_OIS_6m_any_dates":potential,
            "pair_both_official_OIS_6m_same_date":sameois,
            "pair_full_bundle_2Y_and_official_OIS_exact_date":full,
            "relative_macro_scores_authorized":0,
            "relative_cb_Want_Can_scores_authorized":0,
            "relative_FX_pair_scores_authorized":0,
            "pair_rankings_changed":0,
            "Beta_forward_signals_generated":0,
        },
        "no_automatic_OIS_proxy_promotion":True,
        "no_pit_oos_claim":True,
        "safe_to_publish_D_json":False,
        "safe_to_recalculate_28_pairs":False,
        "safe_for_beta":False,"safe_for_forward":False,
        "writes_live_data":False,
    }
    result["receipt_sha256"]=hashlib.sha256(json.dumps(
        result,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return result

def run(as_of=EVALUATION_DAY):
    def load(name):
        return json.loads((SECTION/(name+".json")).read_text(encoding="utf-8"))
    return evaluate(domestic=domestic_run(as_of="2026-10-27"),
      rates=load("NATIVE_RATES_DATA"),ois=load("OIS_OPERATIONAL_VIEW"),
      readiness=load("OIS_SOURCE_READINESS_VIEW"),
      cb=load("NATIVE_CB_DATA"),setup=load("PAIR_SETUP_OPERATIONAL_VIEW"),
      core=load("D"),quant=quantitative_run(as_of=EVALUATION_DAY),
      as_of=as_of)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--as-of",default=EVALUATION_DAY)
    ap.add_argument("--out",type=Path)
    args=ap.parse_args()
    if args.out: need(args.out.resolve().is_relative_to(Path("/tmp")),
                      "research-only output receipts under /tmp")
    result=run(args.as_of)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"summary":result["summary"],
          "safe_to_publish_D_json":False},sort_keys=True))

if __name__=="__main__":
    main()
