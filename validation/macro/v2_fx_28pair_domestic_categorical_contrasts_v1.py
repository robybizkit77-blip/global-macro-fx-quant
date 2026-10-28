#!/usr/bin/env python3
"""Macro V2 categorical 28-pair *domestic contrast*, NOT an FX score/ranking.

An activity z normalized within one country's OWN history is not comparable
as a numeric FX-strength level to another country's z. The strictly
descriptive experiment asks only whether one country's activity is FIRM and
the other's SOFT at three UNFITTED macro weights 25/50/75%.

Contrasts are *within-country categorical context*, not evidence that the
currency should appreciate, that 2Y/OIS is repricing, or of validated alpha.
A mixed activity bucket cannot break a tie. CPI pressure is not an automatic
FX-positive vote. All policy/2Y quality observations remain separate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    FORMULA, G8, Z_THRESHOLD, activity_class, run as domestic_run,
)
from validation.macro.v2_fx_28pair_synchronized_evidence_gate_v1 import (
    ROOT, EVALUATION_DAY, SCHEMA as SOURCE_SCHEMA, run as source_run
)

SCHEMA="GMFQ_MACRO_V2_FX_28_PAIR_DOMESTIC_CATEGORICAL_WEIGHT_STRESS_RESEARCH_V1"
WEIGHT_SCENARIOS=("25","50","75")
FIRM="FIRM_RELATIVE_TO_OWN_HISTORY"
SOFT="SOFT_RELATIVE_TO_OWN_HISTORY"
MIXED="MIXED_RELATIVE_TO_OWN_HISTORY"
NO_CONTRAST="NO_OPPOSITE_ACTIVITY_CLASSES"


def need(condition, reason):
    if not condition:
        raise ValueError("FX_28PAIR_CATEGORICAL_CONTRAST_REJECTED: "+reason)


def contrast_classes(base,quote):
    """Only OPPOSED within-country activity classes get a *description*."""
    need(base in (FIRM,SOFT,MIXED) and quote in (FIRM,SOFT,MIXED),
         "unrecognized within-country activity category")
    if base==FIRM and quote==SOFT:
        return "BASE_FIRM_QUOTE_SOFT"
    if base==SOFT and quote==FIRM:
        return "BASE_SOFT_QUOTE_FIRM"
    return NO_CONTRAST


def contrast_values(base,quote):
    need(type(base) in (int,float) and type(quote) in (int,float)
         and math.isfinite(base) and math.isfinite(quote)
         and -3.000001<=base<=3.000001 and -3.000001<=quote<=3.000001,
         "bounded finite domestic activity z values")
    return contrast_classes(activity_class(base),activity_class(quote))


def compute(*,candidate,source,as_of=EVALUATION_DAY):
    need(as_of==EVALUATION_DAY,"dated research snapshot; no same-day market inference")
    need(candidate.get("schema")=="GMFQ_MACRO_V2_EXPLICIT_DOMESTIC_CANDIDATE_V1"
         and candidate.get("formula_version")==FORMULA
         and candidate.get("economic_as_of")=="2026-10-27"
         and candidate.get("safe_to_publish_D") is False
         and candidate.get("safe_to_update_pair_theses") is False
         and candidate.get("safe_to_use_for_beta") is False
         and candidate.get("safe_to_use_for_forward") is False
         and candidate.get("writes_live_data") is False
         and candidate.get("historical_first_publication_PIT_not_certified") is True
         and candidate.get("out_of_sample_falsification_not_completed") is True
         and candidate.get("summary",{}).get("FX_scores_produced")==0
         and candidate.get("summary",{}).get("axes")==24,
         "only accepted unpromoted first domestic research candidate")
    need(source.get("schema")==SOURCE_SCHEMA
         and source.get("research_as_of")==as_of
         and source.get("safe_to_publish_D_json") is False
         and source.get("safe_to_recalculate_28_pairs") is False
         and source.get("safe_for_beta") is False
         and source.get("safe_for_forward") is False
         and source.get("writes_live_data") is False
         and source.get("no_automatic_OIS_proxy_promotion") is True
         and source.get("summary",{}).get("pairs_total")==28
         and source.get("summary",{}).get("relative_FX_pair_scores_authorized")==0,
         "relative 2Y/OIS evidence must not be promoted")
    countries=candidate.get("countries",{})
    need(set(countries)==set(G8)
         and set(source.get("source_currencies",{}))==set(G8),
         "both independent G8 input layers complete")
    pairs=source.get("pair_evidence",{})
    need(isinstance(pairs,dict) and len(pairs)==28,"all 28 canonical pairs")
    results={}
    for pair,e in sorted(pairs.items()):
        need(e.get("pair")==pair and pair.count("/")==1
             and e.get("can_construct_model_relative_FX_score") is False
             and e.get("macro_strength_diff_z") is None
             and e.get("original_D_pair_rebuilt") is False
             and e.get("6m_weekly_relative_repricing_verified_same_expiry_methods") is False
             and e.get("CB_Want_Can_pair_comparison_validated") is False,
             "no preexisting or forged relative score/rates cause")
        a,b=pair.split("/")
        need(a!=b and a in G8 and b in G8, "canonical FX G8 pair only")
        A,B=countries[a],countries[b]
        for c,x in ((a,A),(b,B)):
            need(x.get("FX_strength_candidate") is None
                 and x.get("eligible_to_recalculate_28_pairs") is False
                 and x.get("eligible_for_beta_forward") is False
                 and x.get("legacy_D_numbers_are_NOT_in_new_candidate_units") is True
                 and x.get("weights_growth_labour")==[0.5,0.5],
                 c+": domestic candidate cannot be market FX signal")
            g=x.get("growth_within_history_z")
            l=x.get("unemployment_tightness_within_history_z")
            p=x.get("inflation_pressure_within_history_z")
            need(all(type(v) in (int,float) and math.isfinite(v)
                     and abs(v)<=3.000001 for v in (g,l,p)),
                 c+": three within-country z axes must be finite")
            need(abs(x["domestic_activity_candidate_z"]-(g+l)*0.5)<1e-10,
                 c+": 50/50 equation only growth and labour")
            ss=x.get("growth_weight_sensitivity_z")
            need(isinstance(ss,dict) and set(ss)==set(WEIGHT_SCENARIOS),
                 c+": fixed 3 weight scenarios required")
            for w in WEIGHT_SCENARIOS:
                wfloat=int(w)/100
                need(abs(ss[w]-(wfloat*g+(1-wfloat)*l))<1e-10,
                     c+": scenario arithmetic not independent or post-fit")
        scenario={}
        for w in WEIGHT_SCENARIOS:
            va=A["growth_weight_sensitivity_z"][w]
            vb=B["growth_weight_sensitivity_z"][w]
            scenario[w]={
                "base_domestic_class":activity_class(va),
                "quote_domestic_class":activity_class(vb),
                "categorical_economic_contrast_ONLY":contrast_values(va,vb),
                "not_an_FX_direction_or_probability":True,
            }
        contrasts=[scenario[w]["categorical_economic_contrast_ONLY"]
                   for w in WEIGHT_SCENARIOS]
        distinct=set(contrasts)
        recurring=(len(distinct)==1 and NO_CONTRAST not in distinct)
        some=any(x!=NO_CONTRAST for x in contrasts)
        if recurring:
            typ="PERSISTENT_OPPOSED_DOMESTIC_ACTIVITY_CATEGORIES_NOT_FX"
        elif some:
            typ="WEIGHT_SENSITIVE_DOMESTIC_CATEGORY_CONTRAST_NOT_FX"
        else:
            typ="NO_OPPOSED_DOMESTIC_ACTIVITY_CATEGORIES"
        labels={
            "base_estimated_inputs":any(x.get("is_estimate") is True
                                       for x in A["source_quality_details"].values()),
            "quote_estimated_inputs":any(x.get("is_estimate") is True
                                       for x in B["source_quality_details"].values()),
            "base_source_definition_caveat":bool(A["source_quality_flags"]),
            "quote_source_definition_caveat":bool(B["source_quality_flags"]),
        }
        results[pair]={
            "pair":pair,
            "study":"CATEGORICAL_OPPOSED_DOMESTIC_ACTIVITY_NOT_CROSS_COUNTRY_Z_DIFFERENCE",
            "scenario_weights_growth_pct":[25,50,75],
            "scenario_outcomes":scenario,
            "original_50pct_domestic_contrast":scenario["50"]["categorical_economic_contrast_ONLY"],
            "classification":typ,
            "persistent_opposed_category_all_weights":recurring,
            "some_opposite_category_but_not_all_scenarios":some and not recurring,
            "has_at_least_one_nonopposed_scenario":NO_CONTRAST in distinct,
            "source_quality_annotations":labels,
            "has_any_estimate_or_definition_caveat":any(labels.values()),
            "official_2Y_both_same_date":e["2Y_same_observation_day"],
            "official_6m_both_same_date":e["6m_official_same_observation_day"],
            "2Y_6m_full_same_day_both_legs":e["2Y_and_official_6m_matched_same_day_both_legs"],
            "official_OIS_6m_weekly_relative_repricing_FX":None,
            "macro_relative_FX_score":None,
            "macro_relative_FX_rank":None,
            "can_emit_bias_or_trade":False,
            "eligible_for_historical_PIT_backtest":False,
            "eligible_for_forward_or_beta":False,
        }
    need(len(results)==28,"no omitted pair result")
    group=Counter(x["classification"] for x in results.values())
    total=sum(group.values())
    need(total==28,"category partitions must exhaust 28 pairs exactly")
    unstable=sorted(k for k,v in countries.items()
                    if not v["activity_class_stable_across_25_50_75pct_growth"])
    output={
        "schema":SCHEMA,
        "status":"28_PAIR_3_WEIGHTS_DOMESTIC_CATEGORICAL_FALSIFICATION_RESEARCH_ONLY",
        "research_as_of":as_of,
        "model_formula":FORMULA,
        "category_threshold_z":Z_THRESHOLD,
        "growth_weights_preregistered":[0.25,0.5,0.75],
        "country_specific_history_z_magnitudes_not_subtracted":True,
        "only_opposed_firm_soft_categories_count_as_descriptive_contrast":True,
        "CPI_separate_not_positive_FX_vote":True,
        "central_bank_want_can_requires_publisher_context":True,
        "no_tuning_to_future_FX_returns":True,
        "no_cross_country_rank_or_pair_signal":True,
        "source_2Y_and_OIS_dates_not_synchronized_for_all_pairs":True,
        "scenario_pair_rows":results,
        "summary":{
            "countries":8,"pairs":total,
            "scenarios_per_pair":3,
            "country_weight_unstable":unstable,
            "country_weight_unstable_count":len(unstable),
            "pairs_persistent_opposed_categories":group["PERSISTENT_OPPOSED_DOMESTIC_ACTIVITY_CATEGORIES_NOT_FX"],
            "pairs_weight_sensitive_opposed_categories":group["WEIGHT_SENSITIVE_DOMESTIC_CATEGORY_CONTRAST_NOT_FX"],
            "pairs_no_opposed_categories":group["NO_OPPOSED_DOMESTIC_ACTIVITY_CATEGORIES"],
            "pairs_with_any_estimate_or_definition_caveat":
                sum(r["has_any_estimate_or_definition_caveat"] for r in results.values()),
            "pairs_all_2Y_6m_OIS_exact_same_day":
                sum(r["2Y_6m_full_same_day_both_legs"] for r in results.values()),
            "FX_directional_signals":0,
            "relative_strength_rankings":0,
            "out_of_sample_predictions_evaluated":0,
        },
        "safe_to_publish_new_D":False,
        "safe_to_change_28_pair_states":False,
        "safe_to_use_for_beta":False,
        "safe_to_use_for_forward":False,
        "writes_live_data":False,
    }
    output["receipt_sha256"]=hashlib.sha256(json.dumps(
        output,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return output


def run(as_of=EVALUATION_DAY):
    return compute(candidate=domestic_run(as_of="2026-10-27"),
                   source=source_run(as_of=as_of),as_of=as_of)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--as-of",default=EVALUATION_DAY)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    if a.out:need(a.out.resolve().is_relative_to(Path("/tmp")),
                  "only /tmp permitted for research receipt")
    r=run(as_of=a.as_of)
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":r["status"],"summary":r["summary"],
          "safe_to_publish_new_D":False},sort_keys=True))


if __name__=="__main__":
    main()
