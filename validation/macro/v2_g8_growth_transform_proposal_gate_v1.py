#!/usr/bin/env python3
"""Eight-currency Growth feature transform CONTRACT, not a Macro score.

Rejects source metric substitution, vintage leakage and cross-horizon ranking.
Describes transformations of current observed series but NEVER applies the
current revised 82/33/42-value arrays as if first-publication PIT histories.
A separate pure calculator accepts caller-supplied dated events for unit and
no-lookahead tests; its values are explicitly research math, never model input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import (
    ROOT, require, timestamp, period_index, period_start,
)
from validation.macro.v2_growth_inflation_g8_desk_inventory_v1 import (
    parse_reference_period,
)
from validation.macro.v2_pit_g8_control_plane_v1 import (
    CURRENCIES, run as g8_control_plane,
)

SCHEMA = "GMFQ_MACRO_V2_G8_GROWTH_TRANSFORM_PROPOSAL_GATE_V1"
RECEIPT = "GMFQ_MACRO_V2_G8_GROWTH_SHADOW_TRANSFORM_CONTRACT_V1"
FILE = ROOT / "validation/macro/fixtures/v2_g8_growth_transform_proposal_contract_v1.json"
OBSERVED = ROOT / "live_data/sections/MACRO_SERIES.json"
MONTHLY_TRANSFORM = "LEVEL_3M3M"
QUARTERLY_TRANSFORMS = {"REPORTED_QOQ_RATE", "REPORTED_YOY_RATE"}
TRANSFORM_COUNTS = {"LEVEL_3M3M": 6,
                    "REPORTED_QOQ_RATE": 1, "REPORTED_YOY_RATE": 1}
# Independently frozen source identity, frequency and UNIT: not a model score.
PINNED = {
    "USD": ("US_INDPRO_history_value","M","Index 2017=100",
            "2026-08",103.0682,82,"US_G17_IP_2017_BASE_PUBLISHED_ONE_DECIMAL",
            "LEVEL_3M3M","INDUSTRIAL_PRODUCTION",
            "PUBLISHED_ROUNDED_VS_OBSERVED_EXACT"),
    "EUR": ("EA_IP_history_value","M","Index 2021=100",
            "2026-07",98.3,82,"EA_IP_MOM_CHANGE_OFFICIAL_RELEASE_PCT",
            "LEVEL_3M3M","INDUSTRIAL_PRODUCTION",
            "MOM_RATE_VS_INDEX_LEVEL"),
    "GBP": ("UK_PRODUCTION_history_value","M","Index",
            "2026-07",98.5,82,"UK_IOP_3M3M_GROWTH_RATE_OFFICIAL",
            "LEVEL_3M3M","INDUSTRIAL_PRODUCTION",
            "PUBLISHED_3M3M_RATE_VS_INDEX_LEVEL"),
    "JPY": ("JP_IIP_history_value","M","Index 2020=100",
            "2026-07",104.4,82,"JP_METI_IIP_MAY_2026_SA_2020_INDEX",
            "LEVEL_3M3M","INDUSTRIAL_PRODUCTION",
            "SOURCE_PERIOD_MAY_VS_CURRENT_JULY"),
    "CHF": ("CH_PRODUCTION_history_value","M","Index 2021=100",
            "2026-06",122.0,82,"CH_SECO_SPORTS_ADJUSTED_GDP_QOQ",
            "LEVEL_3M3M","INDUSTRIAL_PRODUCTION",
            "DIFFERENT_INDICATOR_GDP_QUARTERLY_VS_INDUSTRIAL_MONTHLY"),
    "CAD": ("CA_REAL_GDP_M_history_value","M",
            "million chained 2017 CAD SAAR",
            "2026-06",2369309,82,"STATCAN_GDP_INDUSTRY_36_10_0434_01_LEVEL",
            "LEVEL_3M3M","REAL_GDP_INDUSTRY",
            "SAME_OBSERVED_LEVEL_BUT_SOURCE_MAPPING_NOT_CERTIFIED"),
    "AUD": ("AU_REAL_GDP_QOQ_ABS_history_value","Q",
            "% QoQ, seasonally adjusted chain volume",
            "2026Q2",0.4,33,"AU_REAL_GDP_QOQ_ABS_history_value",
            "REPORTED_QOQ_RATE","REAL_GDP","QUARTERLY_QOQ"),
    "NZD": ("NZ_REAL_GDP_Q_history_value","Q","percent y/y",
            "2026Q2",2.6,42,"NZ_REAL_GDP_Q_history_value",
            "REPORTED_YOY_RATE","REAL_GDP",
            "QUARTERLY_SAME_QUARTER_YOY_NOT_QOQ"),
}
RULES = {
    "LEVEL_3M3M":
    "100*((x_t+x_t_1+x_t_2)/(x_t_3+x_t_4+x_t_5)-1), six consecutive MONTHLY levels from allowed as-of source vintages, strictly positive denominators",
    "REPORTED_QOQ_RATE":
    "Pass through one official published QUARTERLY QoQ rate only for descriptive study, no reinterpretation as GDP annual average",
    "REPORTED_YOY_RATE":
    "Pass through one official published QUARTERLY same-quarter YoY rate only for descriptive study; CANNOT directly compare to QoQ",
    "normalization":
    "No common percentile/zscore or cross-FX ranking is fitted until each selected source has >=25 monthly or >=13 quarterly independent first releases, full revised-vintage continuity, common economic horizon and explicit approval",
    "as_of":
    "At each historical timestamp select only first-released and then-revised observations already publicly available; current 82/33/42 history points never stand in for release histories",
}


def numeric(value):
    return type(value) in (int,float) and math.isfinite(value)


def _normalize_stored_period(raw, freq):
    parsed = parse_reference_period(raw,freq)
    require(parsed is not None and parsed[1] ==
            ("month" if freq=="M" else "quarter"),
            "invalid or incompatible stored Growth observation period")
    end,_=parsed
    if freq=="M":
        return end.strftime("%Y-%m")
    return f"{end.year}Q{(end.month-1)//3+1}"


def validate_contract(manifest):
    require(manifest.get("schema")==SCHEMA
            and manifest.get("research_review_as_of")=="2026-10-24"
            and manifest.get("growth_pillar_economic_intent")==
            "REAL_ACTIVITY_MOMENTUM_NOT_AGGREGATE_REAL_GDP_CONTRIBUTION"
            and manifest.get("selection_status")==
            "EIGHT_CANDIDATE_OBSERVED_SERIES_NO_CANONICAL_GROWTH_SCORE_SELECTION"
            and manifest.get("transformation_execution_scope")==
            "SYNTHETIC_OR_SUPPLIED_FIRST_RELEASE_EVENTS_ONLY_NOT_REVISED_LIVE_HISTORY",
            "cannot silently select canonical Growth factor or score")
    for key in (
        "official_publisher_original_day_bytes_certified",
        "full_historical_pit_revision_chain_certified",
        "cross_currency_growth_zscore_comparable",
        "macro_weight_or_direction_approved",
        "save_to_live_data","write_macro_scores","eligible_for_backtest",
        "eligible_for_pair_ranking",
    ):
        require(manifest.get(key) is False,
                "unreviewed Growth research cannot promote PIT eligibility: "+key)
    require(manifest.get("policy")==RULES,
            "transformation/first-release/normalisation policy modified")
    rows=manifest.get("feature_proposals")
    require(isinstance(rows,list) and len(rows)==8 and
            [x.get("currency") for x in rows]==list(CURRENCIES),
            "all eight exact G8 currency growth candidates required")
    for row in rows:
        c=row["currency"]
        (id,freq,unit,period,value,n,web,transform,family,relation)=PINNED[c]
        pins={
            "observed_series_id":id,"frequency":freq,"raw_unit":unit,
            "latest_reference_period":period,"latest_observed_value":value,
            "observed_revised_history_length":n,
            "candidate_web_series_id":web,"proposal_transform":transform,
            "economic_family":family,"evidence_relation":relation,
            "economic_reference_status":"CURRENT_OBSERVED_HISTORY_NOT_ASOF_FIRST_RELEASE_VINTAGE",
            "canonical_growth_source_selected":False,
            "training_window_certified":False,
            "minimum_independent_first_release_periods":25 if freq=="M" else 13,
            "needed_for_math":TRANSFORM_COUNTS[transform],
            "comparable_growth_horizon":(
                "QUARTER_EQUIVALENT_3M_OVER_PREVIOUS_3M" if transform=="LEVEL_3M3M"
                else "QUARTER_ON_QUARTER" if transform=="REPORTED_QOQ_RATE"
                else "SAME_QUARTER_PREVIOUS_YEAR"),
            "one_to_one_metric_crosswalk_with_publisher_first_event_certified":False,
        }
        for field,expected in pins.items():
            require((numeric(row.get(field)) and row.get(field)==expected) if numeric(expected) else (row.get(field)==expected and type(row.get(field))==type(expected)),
                    "Growth original units/period/source or model gate changed: "+c+" "+field)
    return rows


def audit(manifest=None, observed=None, common=None):
    if manifest is None:
        manifest=json.loads(FILE.read_text(encoding="utf-8"))
    if observed is None:
        observed=json.loads(OBSERVED.read_text(encoding="utf-8"))
    if common is None:
        common=g8_control_plane(as_of="2026-10-24T00:00:00Z")
    proposals=validate_contract(manifest)
    require(set(observed)==set(CURRENCIES),"eight observed G8 series inventories required")
    require(common.get("schema")=="GMFQ_MACRO_V2_G8_SHARED_PIT_CONTROL_PLANE_V1"
            and common.get("as_of_utc")=="2026-10-24T00:00:00+00:00"
            and common["summary"]["candidate_source_streams_loaded"]==24
            and common["summary"]["slots_with_full_canonical_first_release_pit_training_certified"]==0
            and common.get("safe_to_publish_new_D") is False,
            "previous 24-slot G8 source evidence control plane not intact")
    lookup={(x["currency"],x["pillar"]):x for x in common["rows"]}
    require(len(lookup)==24,"shared currency/pillar source scope changed")
    out=[]
    for proposal in proposals:
        cc=proposal["currency"]
        found=[s for s in observed[cc] if s.get("id")==proposal["observed_series_id"]
               and s.get("category")=="Crescita"]
        require(len(found)==1,"exact observed Growth series identifier ambiguous: "+cc)
        entry=found[0]
        freq=proposal["frequency"]
        require(entry.get("frequency")==freq
                and entry.get("unit")==proposal["raw_unit"]
                and _normalize_stored_period(entry.get("last_date"),freq)==
                proposal["latest_reference_period"]
                and numeric(entry.get("last_value"))
                and entry["last_value"]==proposal["latest_observed_value"],
                "revised observed Growth series value/unit/period drift: "+cc)
        periods=entry.get("dates")
        values=entry.get("values")
        require(isinstance(periods,list) and isinstance(values,list)
                and len(periods)==len(values)==proposal["observed_revised_history_length"],
                "revised observed history length changed or incomplete: "+cc)
        normalized=[_normalize_stored_period(p,freq) for p in periods]
        indexes=[period_index(p,freq) for p in normalized]
        require(indexes==list(range(indexes[0],indexes[0]+len(indexes)))
                and normalized[-1]==proposal["latest_reference_period"]
                and all(numeric(v) for v in values)
                and values[-1]==entry["last_value"],
                "revised observed series has gap/duplicate/nonfinite values: "+cc)
        if proposal["proposal_transform"]==MONTHLY_TRANSFORM:
            require(all(v>0 for v in values),
                    "historical revised levels must be positive for hypothetical 3m3m formula")
        candidate=lookup[(cc,"growth")]
        require(candidate["canonical_series_id"] is None
                and candidate["candidate_evidence_source_id"]==
                proposal["candidate_web_series_id"]
                and candidate["candidate_documented_first_periods_visible"]==1
                and candidate["candidate_metric_unit"]
                and candidate["canonical_first_release_chain_certified"] is False
                and candidate["eligible_for_macro_score"] is False,
                "Growth first web event cannot become canonical simply from 82 revised rows")
        out.append({
            "currency":cc,
            "proposed_observed_series_id":proposal["observed_series_id"],
            "observed_raw_unit":proposal["raw_unit"],
            "frequency":freq,
            "latest_observed_reference_period":proposal["latest_reference_period"],
            "latest_observed_revised_value":proposal["latest_observed_value"],
            "observed_revised_history_periods_not_first_release":len(periods),
            "proposed_transform":proposal["proposal_transform"],
            "underlying_economic_family":proposal["economic_family"],
            "growth_horizon":proposal["comparable_growth_horizon"],
            "first_releases_minimum_per_single_series":proposal["minimum_independent_first_release_periods"],
            "minimum_same_vintage_observations_for_math":proposal["needed_for_math"],
            "candidate_official_web_source_id":candidate["candidate_evidence_source_id"],
            "publisher_first_release_periods_in_common_gateway":
                candidate["candidate_documented_first_periods_visible"],
            "candidate_reported_value":candidate["latest_candidate_value_at_cutoff"],
            "candidate_reported_period":candidate["latest_candidate_period_visible"],
            "candidate_source_relation":proposal["evidence_relation"],
            "conflating_raw_observed_and_publisher_measurement_forbidden":True,
            "current_observed_82_or_33_or_42_revised_rows_can_train_pit_model":False,
            "feature_computable_from_documented_first_web_source_events":False,
            "common_cross_currency_growth_horizon_certified":False,
            "normalization_permitted":False,
            "new_macro_score_permitted":False,
        })
    families={r["underlying_economic_family"] for r in out}
    horizons={r["growth_horizon"] for r in out}
    require(families=={"INDUSTRIAL_PRODUCTION","REAL_GDP_INDUSTRY","REAL_GDP"}
            and horizons=={"QUARTER_EQUIVALENT_3M_OVER_PREVIOUS_3M",
                           "QUARTER_ON_QUARTER","SAME_QUARTER_PREVIOUS_YEAR"},
            "G8 raw real-activity indicator families must remain explicitly non-homogeneous")
    return {
        "schema":RECEIPT,"reviewed_on":"2026-10-24",
        "status":"PROPOSED_TRANSFORM_MATH_VALIDATION_ONLY_NOT_GROWTH_MODEL_APPROVAL",
        "rows":out,
        "summary":{
            "g8_growth_candidates":8,
            "monthly_level_transform_proposals":6,
            "quarterly_reported_qoq_proposals":1,
            "quarterly_reported_yoy_proposals":1,
            "observed_current_revised_history_rows_not_first_release":
                sum(r["observed_revised_history_periods_not_first_release"] for r in out),
            "g8_growth_slots_with_model_selected":0,
            "g8_growth_slots_with_complete_first_release_vintage":0,
            "g8_growth_slots_with_common_comparable_horizon":0,
            "g8_growth_scores_newly_approved":0,
        },
        "recommended_next_gate_order":[
            "Approve common economic activity concept: industry proxy versus real GDP",
            "Approve uniform quarterly-equivalent horizon; NZD same-quarter YoY is not directly QoQ",
            "Identify exact official publisher series to canonical observed history mapping, including rounded and revised cases",
            "Acquire original day vintages, all revisions, and archived bytes for 25 months or 13 quarters",
            "Validate each as-of 3m3m event chain and country-specific historic normalization",
            "Only after independent review consider new macro factors and FX pair scores",
        ],
        "manifest_sha256":hashlib.sha256(
            json.dumps(manifest,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
        "historical_revised_series_consumed_for_macro_factor":False,
        "derived_growth_values_from_live_series_computed":False,
        "cross_fx_zscore_fitted":False,
        "scores_computed":False,"model_parameters_fitted":False,
        "ready_for_backtest":False,"safe_to_publish_new_D":False,
        "safe_to_update_pair_theses":False,"writes_live_data":False,
    }


def _valid_source_events(events, freq, as_of):
    require(isinstance(events,list),"vintage events must be explicitly supplied")
    cutoff=timestamp(as_of)
    groups=defaultdict(list)
    used=set()
    for e in events:
        require(isinstance(e,dict),"source vintage event requires object")
        p=e.get("reference_period")
        i=period_index(p,freq)
        kind=e.get("kind")
        require(kind in ("FIRST_WEB","REVISION_WEB"),
                "unknown initial/revised publication event")
        t=timestamp(e.get("published_at_utc"))
        require(t.date()>=period_start(p,freq),
                "publication cannot predate economic period")
        v=e.get("value")
        require(numeric(v),"finite source number required")
        if freq=="M":
            require(v>0,"monthly level must be positive")
        marker=(p,t)
        require(marker not in used,"same observation may not be revised twice at identical timestamp")
        used.add(marker)
        groups[i].append((t,kind,v,p))
    for index, rows in groups.items():
        rows.sort()
        require(rows[0][1]=="FIRST_WEB" and
                sum(kind=="FIRST_WEB" for _,kind,_,_ in rows)==1
                and all(a[0]<b[0] for a,b in zip(rows,rows[1:])),
                "revision must follow exactly one first release for that economic period")
    visible={}
    for index,rows in groups.items():
        versions=[v for v in rows if v[0]<=cutoff]
        if versions:
            visible[index]=versions[-1]
    return visible


def shadow_math(proposal, source_events, *, as_of):
    """Synthetic or supplied source-vintage math ONLY, not a verified report.

    This API does NOT authenticate caller-provided publisher events. It refuses
    to treat computed numerics as PIT certified; caller must independently
    prove byte provenance, release time and canonical mapping for real studies.
    """
    freq=proposal.get("frequency")
    transform=proposal.get("proposal_transform")
    require(transform in TRANSFORM_COUNTS and
            freq==("M" if transform==MONTHLY_TRANSFORM else "Q"),
            "transform and observation frequency incompatible")
    visible=_valid_source_events(source_events,freq,as_of)
    recent=max(visible) if visible else None
    result={
        "as_of_utc":timestamp(as_of).isoformat(),
        "transform":transform,"latest_period_known":visible[recent][3] if recent is not None else None,
        "visible_distinct_reference_periods":len(visible),
        "visible_latest_value":visible[recent][2] if recent is not None else None,
        "research_feature_percent":None,
        "status":"NO_VISIBLE_OBSERVATIONS" if recent is None else "MATH_PREREQUISITES_MISSING",
        "vintage_authentication_not_performed":True,
        "eligible_for_backtest":False,"eligible_for_macro_score":False,
        "safe_to_publish_new_D":False,"writes_live_data":False,
    }
    if recent is None:
        return result
    if transform in QUARTERLY_TRANSFORMS:
        result["research_feature_percent"]=visible[recent][2]
        result["status"]="DESCRIPTIVE_QUARTERLY_RATE_NO_CROSS_COUNTRY_SCORE"
        return result
    indices=list(range(recent-5,recent+1))
    if any(i not in visible for i in indices):
        result["status"]="MISSING_SIX_CONSECUTIVE_FIRST_VINTAGE_PERIODS"
        return result
    values=[visible[i][2] for i in indices]
    prev=sum(values[:3])
    current=sum(values[3:])
    require(prev>0,"invalid 3m3m denominator")
    result["research_feature_percent"]=100.0*(current/prev-1.0)
    result["status"]="SIX_MONTH_DESCRIPTIVE_RESEARCH_MATH_ONLY"
    result["underlying_periods_in_formula"]=[visible[i][3] for i in indices]
    return result


def markdown(receipt):
    lines=[
        "# Macro V2 · G8 Growth research transform proposal",
        "**Not scoring-approved.** Eight research source candidates; first-release histories and uniform horizons incomplete.",
        "",
        "| FX | Observed series | Type | Proposed calculation | Live revised rows | PIT source periods | Score |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for x in receipt["rows"]:
        lines.append("| "+ " | ".join([
            x["currency"],x["proposed_observed_series_id"],x["underlying_economic_family"],
            x["proposed_transform"],
            str(x["observed_revised_history_periods_not_first_release"]),
            str(x["publisher_first_release_periods_in_common_gateway"]),"BLOCKED",
        ])+" |")
    lines.extend([
        "",
        "Six 3m3m proposals require six consecutive **first-release as-of level** vintages; "
        "quarterly AUD GDP QoQ and NZD GDP YoY have **different horizons**.",
        "",
        "**Never use 567 current/revised history rows as 567 point-in-time release events.**",
        "No FX score or backtest, no live_data, no pair ranking or Control Room update.",
    ])
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--json-out",type=Path)
    p.add_argument("--markdown-out",type=Path)
    args=p.parse_args()
    result=audit()
    for dest,body in (
        (args.json_out,json.dumps(result,indent=2,ensure_ascii=False)+"\n"),
        (args.markdown_out,markdown(result)),
    ):
        if dest:
            require(dest.resolve().is_relative_to(Path("/tmp")),
                    "Growth research receipts only under /tmp")
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(body,encoding="utf-8")
    print(json.dumps({"status":result["status"],**result["summary"],
                      "safe_to_publish_new_D":False}))

if __name__=="__main__":
    main()
