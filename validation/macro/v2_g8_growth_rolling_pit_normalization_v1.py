#!/usr/bin/env python3
"""Research-only frozen-as-of Growth normalization; never a Macro/FX score.

Read-only normalization on CALLER-SUPPLIED, unverified frozen feature snapshots.
Does not pull revised live historical observations, fit across countries,
recalculate earlier features with today's vintages or claim official PIT proof.
The numbers are illustrative math, not score approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import require, timestamp, period_index, period_start
from validation.macro.v2_g8_growth_transform_proposal_gate_v1 import (
    audit as prior_growth_audit,
    PINNED,
)

SCHEMA="GMFQ_MACRO_V2_G8_GROWTH_ROLLING_PIT_NORMALIZATION_GATE_V1"
SNAPSHOT_METHOD="FROZEN_AT_OWN_PUBLICATION_CUTOFF_UNVERIFIED_RESEARCH"
HORIZONS={
    "LEVEL_3M3M":"QUARTER_EQUIVALENT_3M_OVER_PREVIOUS_3M",
    "REPORTED_QOQ_RATE":"QUARTER_ON_QUARTER",
    "REPORTED_YOY_RATE":"SAME_QUARTER_PREVIOUS_YEAR",
}
FAMILIES={"INDUSTRIAL_PRODUCTION","REAL_GDP_INDUSTRY","REAL_GDP"}
MIN_TRAINING={"M":25,"Q":13}


def finite(x):
    return type(x) in (int,float) and math.isfinite(x)


def descriptor(proposal):
    """Pin each research candidate to its independently audited source concept."""
    c=proposal.get("currency")
    require(c in PINNED, "unknown FX Growth currency")
    sid,freq,unit,period,value,n,web,transform,family,relation=PINNED[c]
    checks={
        "observed_series_id":sid,
        "candidate_web_series_id":web,
        "frequency":freq,
        "proposal_transform":transform,
        "underlying_economic_family":family,
        "comparable_growth_horizon":HORIZONS[transform],
        "canonical_growth_source_selected":False,
        "training_window_certified":False,
        "one_to_one_metric_crosswalk_with_publisher_first_event_certified":False,
    }
    for field,expected in checks.items():
        require(proposal.get(field)==expected and
                (type(proposal.get(field)) is bool if type(expected) is bool else True),
                "proposed Growth contract mismatch: "+c+"."+field)
    require(family in FAMILIES, "unreviewed macro family")
    return {"currency":c,"source_series_id":sid,"frequency":freq,
            "economic_family":family,"transform":transform,"horizon":HORIZONS[transform],
            "historical_train_count":MIN_TRAINING[freq]}


def same_math_cohort(a,b):
    """Same *statistical* definition only, not permission to rank currencies."""
    p,q=descriptor(a),descriptor(b)
    return (p["frequency"],p["economic_family"],p["horizon"],p["transform"])==(
            q["frequency"],q["economic_family"],q["horizon"],q["transform"])


def _check_snapshot(x, expected, *, asof, current=False):
    require(isinstance(x,dict), "a frozen feature observation must be a dict")
    for field,value in (
        ("source_series_id",expected["source_series_id"]),
        ("currency",expected["currency"]),
        ("frequency",expected["frequency"]),
        ("economic_family",expected["economic_family"]),
        ("horizon",expected["horizon"]),
        ("feature_method",expected["transform"]),
        ("snapshot_method",SNAPSHOT_METHOD),
    ):
        require(x.get(field)==value, "frozen feature snapshot identity/method mismatch: "+field)
    require(x.get("recomputed_using_later_vintages") is False
            and x.get("source_original_day_archive_verified") is False,
            "research feature claims unverified historical source bytes or retroactive recomputation")
    p=x.get("reference_period")
    pi=period_index(p,expected["frequency"])
    t=timestamp(x.get("frozen_at_utc"))
    require(t.date()>=period_start(p,expected["frequency"]),
            "source feature freeze date cannot predate its economic reference period")
    require(t<=asof, "research future event leakage")
    require(finite(x.get("feature_percent")),
            "finite and purely descriptive growth feature % needed")
    require(x.get("certified_for_macro_scoring") is False,
            "frozen research snapshot cannot become approved Growth score")
    return pi,t,x["feature_percent"]


def rolling_research_normalization(proposal, current, history, *, as_of):
    """Population-z arithmetic using N *earlier* frozen feature publications.

    Required 25 prior monthly FEATURE values (not simply 25 raw first releases)
    or 13 prior quarterly FEATURE values. Separate full archival first-release
    certification and provenance checks are still needed in another process.
    """
    p=descriptor(proposal)
    cutoff=timestamp(as_of)
    cur_i,cur_t,cur_v=_check_snapshot(current,p,asof=cutoff,current=True)
    require(isinstance(history,list),"frozen historical feature series must be a list")
    checked=[_check_snapshot(x,p,asof=cutoff) for x in history]
    indexes=[i for i,t,v in checked]
    require(len(set(indexes))==len(indexes),"duplicate economic feature period")
    require(all(i<cur_i and t<cur_t for i,t,v in checked),
            "training must be published BEFORE current feature and belong to earlier periods")
    checked.sort(key=lambda row:row[0])
    # Never update a previously frozen training feature with a later revision.
    require(all(x[1]<y[1] for x,y in zip(checked,checked[1:])),
            "historically frozen training feature publication order inconsistent")
    required=p["historical_train_count"]
    relevant=[(i,t,v) for i,t,v in checked if cur_i-required<=i<cur_i]
    indices=[i for i,t,v in relevant]
    expected_indices=list(range(cur_i-required,cur_i))
    result={
        "schema":SCHEMA,
        "currency":p["currency"],"source_series_id":p["source_series_id"],
        "economic_family":p["economic_family"],"horizon":p["horizon"],
        "feature_method":p["transform"],
        "as_of_utc":cutoff.isoformat(),"current_reference_period":current["reference_period"],
        "current_frozen_at_utc":cur_t.isoformat(),"current_research_feature_pct":cur_v,
        "historical_train_count_required":required,
        "historical_prior_feature_snapshots_supplied":len(history),
        "historical_relevant_prior_features_visible":len(relevant),
        "research_rolling_mean_pct":None,"research_rolling_std_pct":None,
        "research_rolling_z":None,
        "status":"INSUFFICIENT_CONSECUTIVE_FROZEN_PRIOR_FEATURES",
        "source_feature_snapshots_independently_authenticated":False,
        "original_publication_bytes_certified":False,
        "full_historical_revisions_certified":False,
        "cross_country_economic_comparability_certified":False,
        "usable_for_macro_score":False,"usable_for_backtest":False,
        "safe_to_publish_new_D":False,"safe_to_update_pair_theses":False,
        "writes_live_data":False,
    }
    if indices!=expected_indices:
        return result
    values=[v for _,_,v in relevant]
    mean=math.fsum(values)/required
    variance=math.fsum((v-mean)**2 for v in values)/required
    std=math.sqrt(variance)
    if std<=1e-12:
        result["status"]="ZERO_OR_NEAR_ZERO_FROZEN_HISTORY_VARIANCE"
        return result
    z=(cur_v-mean)/std
    require(math.isfinite(z),"research normalization produced nonfinite result")
    result.update({
        "research_rolling_mean_pct":mean,
        "research_rolling_std_pct":std,
        "research_rolling_z":z,
        "historical_train_reference_periods":[
            x["reference_period"] for x in sorted(history,
                key=lambda rec:period_index(rec["reference_period"],p["frequency"]))
            if cur_i-required<=period_index(x["reference_period"],p["frequency"])<cur_i
        ],
        "status":"RESEARCH_ROLLING_Z_MATH_ONLY_UNVERIFIED_VINTAGES",
    })
    return result


def group_contract():
    """Describe statistical cohorts; not exchangeable output-score families."""
    r=prior_growth_audit()
    require(r["schema"]=="GMFQ_MACRO_V2_G8_GROWTH_SHADOW_TRANSFORM_CONTRACT_V1"
            and r["summary"]["g8_growth_candidates"]==8
            and r["summary"]["g8_growth_slots_with_model_selected"]==0
            and r["summary"]["g8_growth_scores_newly_approved"]==0,
            "previous 8-Growth study must remain unapproved")
    proposals=json.loads(
        (Path(__file__).parent/"fixtures/v2_g8_growth_transform_proposal_contract_v1.json")
        .read_text(encoding="utf-8"))["feature_proposals"]
    items=[descriptor(x) for x in proposals]
    require(len(items)==8,"all G8 Growth comparisons required")
    cohorts={}
    for item in items:
        key=f'{item["economic_family"]}|{item["horizon"]}|{item["transform"]}'
        cohorts.setdefault(key,[]).append(item["currency"])
    require(sorted(sorted(v) for v in cohorts.values())==
            sorted([sorted(["USD","EUR","GBP","JPY","CHF"]),["CAD"],["AUD"],["NZD"]]),
            "economic families and horizons unexpectedly became homogeneous")
    return {
        "schema":"GMFQ_MACRO_V2_G8_GROWTH_COMPARABILITY_COHORTS_V1",
        "as_of_review":"2026-10-24",
        "cohorts":cohorts,"mathematically_distinct_cohort_count":len(cohorts),
        "observed_growth_series_reviewed":8,
        "cross_currency_growth_rank_approved":False,
        "comparable_economic_breadth_across_cohorts":False,
        "within_cohort_country_calibration_approved":False,
        "quarter_end_rolling_3m3m_is_not_automatic_gdp_qoq_equivalence":True,
        "nzd_yoy_requires_independent_qoq_source_or_same_vintage_level_bridge":True,
        "consumption_composite_still_requires_official_series_and_pit_archives":True,
        "derived_macroeconomic_strength_scores":False,
        "source_vintage_audit_passed":False,
        "safe_to_publish_new_D":False,"writes_live_data":False,
    }


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--out",type=Path)
    args=cli.parse_args()
    result=group_contract()
    if args.out is not None:
        require(args.out.resolve().is_relative_to(Path("/tmp")),
                "research receipt must stay under /tmp")
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result))


if __name__=="__main__":
    main()
