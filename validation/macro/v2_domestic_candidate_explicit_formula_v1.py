#!/usr/bin/env python3
"""Explicit, reproducible eight-country MACRO V2 *candidate*; never D.json.

The historical D score generator is unidentifiable. This new, unfit,
preregistered economic equation operates only on pre-existing research z
features. Source histories include revised vintages and issuer-web statements,
so output is research, NOT a valid PIT FX trading signal.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import date
from pathlib import Path
from validation.macro.v2_g8_three_axis_economic_shadow_v1 import (
    FX, SCHEMA as INPUT_SCHEMA, run as shadow_run,
)

SCHEMA = "GMFQ_MACRO_V2_EXPLICIT_DOMESTIC_CANDIDATE_V1"
FORMULA = "v2_domestic_activity_2026_10_27_FIXED_50_50"
W_GROWTH = 0.50
W_LABOUR = 0.50
W_INFLATION = 0.0  # The policy reaction, not CPI level, can affect FX.
Z_THRESHOLD = 0.50
SENSITIVITY_GROWTH_WEIGHTS = (0.25, 0.50, 0.75)
# Hypothetical coordinate shifts, not estimated historical revision errors.
REVISION_STRESS_EPSILONS_Z = (0.10, 0.25, 0.50)
G8 = tuple(FX)


def require(ok, why):
    if not ok:
        raise ValueError("MACRO_V2_DOMESTIC_CANDIDATE_REJECTED: " + why)


def numeric(v, name):
    require(type(v) in (int, float) and math.isfinite(v)
            and -3.00000001 <= v <= 3.00000001,
            name + " must be a finite pre-clipped z")
    return float(v)


def price_class(z):
    return ("PRICE_PRESSURE_ABOVE_OWN_HISTORY" if z >= Z_THRESHOLD else
            "PRICE_PRESSURE_BELOW_OWN_HISTORY" if z <= -Z_THRESHOLD else
            "PRICE_PRESSURE_NEAR_OWN_HISTORY")


def activity_class(z):
    return ("FIRM_RELATIVE_TO_OWN_HISTORY" if z >= Z_THRESHOLD else
            "SOFT_RELATIVE_TO_OWN_HISTORY" if z <= -Z_THRESHOLD else
            "MIXED_RELATIVE_TO_OWN_HISTORY")


def indicative_regime(activity, inflation):
    """A domestic heuristic, NOT the canonical D.cycle mapping."""
    a, p = activity_class(activity), price_class(inflation)
    if a.startswith("MIXED") or p.endswith("NEAR_OWN_HISTORY"):
        return "MIXED_OR_TURNING_DOMESTIC_CYCLE"
    if a.startswith("FIRM"):
        return ("FIRM_GROWTH_WITH_ELEVATED_PRICE_PRESSURE"
                if p.startswith("PRICE_PRESSURE_ABOVE") else
                "FIRM_GROWTH_WITH_SUBDUED_PRICE_PRESSURE")
    return ("SOFT_GROWTH_WITH_ELEVATED_PRICE_PRESSURE"
            if p.startswith("PRICE_PRESSURE_ABOVE") else
            "SOFT_GROWTH_WITH_SUBDUED_PRICE_PRESSURE")


def continuous_weight_interval(growth: float, labour: float) -> dict:
    """Exact interval for EVERY preregistered weight from 25% to 75%.

    The equation is affine in the growth weight. Therefore its extrema over
    the continuous interval occur at the two fixed endpoints; the middle
    50/50 classification cannot be called robust if either endpoint differs.
    This is within-economy arithmetic ONLY, not a PIT or FX validation.
    """
    require(SENSITIVITY_GROWTH_WEIGHTS == (0.25, 0.50, 0.75),
            "continuous sensitivity endpoints changed without preregistration")
    g = numeric(growth, "interval.growth")
    l = numeric(labour, "interval.labour")
    endpoint_values = (0.25*g + 0.75*l, 0.75*g + 0.25*l)
    lower, upper = min(endpoint_values), max(endpoint_values)
    midpoint = 0.50*(g+l)
    classes = (activity_class(lower), activity_class(midpoint),
               activity_class(upper))
    robust = classes[0] == classes[1] == classes[2]
    return {
        "growth_weight_interval_inclusive": [0.25, 0.75],
        "domestic_activity_z_min": round(lower, 12),
        "domestic_activity_z_max": round(upper, 12),
        "classification_unchanged_at_every_weight_in_interval": robust,
        "weight_invariant_domestic_class_RESEARCH_ONLY": (
            classes[1] if robust else None
        ),
        "class_changes_with_admissible_weights": not robust,
        "continuous_weight_math_is_NOT_PIT_or_FX_validation": True,
    }


def independent_axis_revision_envelope(growth: float, labour: float,
                                       epsilon: float) -> dict:
    """Exact worst-case envelope: every Growth weight in [0.25, 0.75].

    Each own-history z-coordinate may vary INDEPENDENTLY by +/- epsilon;
    convex weights put extrema at the two registered weight endpoints plus
    the symmetric shift. This is hypothetical sensitivity arithmetic, NOT
    an observed release-vintage revision error distribution or FX evidence.
    """
    require(type(epsilon) in (int, float) and math.isfinite(epsilon)
            and 0 <= epsilon <= 0.50,
            "revision stress must be finite and in registered 0..0.50 z range")
    base = continuous_weight_interval(growth, labour)
    lower = base["domestic_activity_z_min"] - epsilon
    upper = base["domestic_activity_z_max"] + epsilon
    stable = activity_class(lower) == activity_class(upper)
    return {
        "hypothetical_each_axis_shift_abs_z": epsilon,
        "growth_weight_interval_inclusive": [0.25, 0.75],
        "stressed_activity_z_min": round(lower, 12),
        "stressed_activity_z_max": round(upper, 12),
        "class_invariant_to_all_weights_and_independent_axis_shifts": stable,
        "robust_domestic_class_RESEARCH_ONLY": activity_class(lower) if stable else None,
        "this_is_not_an_empirical_revision_error_estimate": True,
        "not_a_PIT_or_FX_forecast_test": True,
    }


def build(shadow, legacy):
    require(isinstance(shadow, dict) and shadow.get("schema") == INPUT_SCHEMA
            and shadow.get("status") ==
            "EIGHT_SHADOW_THREE_AXIS_ECONOMIC_SCENARIOS_NOT_MACRO_SCORES",
            "expected existing audited 24-axis research shadow")
    require(shadow.get("safe_to_publish_new_D") is False
            and shadow.get("safe_to_update_pair_theses") is False
            and shadow.get("safe_for_beta") is False
            and shadow.get("safe_for_forward") is False
            and shadow.get("writes_live_data") is False
            and shadow.get("observed_data_is_not_historic_publication_vintage_replay") is True
            and shadow.get("economic_axis_math_not_validated_against_out_of_sample_events") is True,
            "historical-PIT / backtest / promotion eligibility drift")
    require(shadow.get("scope", {}).get("activity_weights") ==
            {"growth": 0.5, "labour_tightness": 0.5, "inflation_in_activity": 0.0},
            "upstream axis weights changed after registration")
    require(shadow.get("summary", {}).get("research_axes") == 24
            and shadow.get("summary", {}).get("economies") == 8
            and shadow.get("summary", {}).get("FX_scores_approved") == 0,
            "not 8 by 3 research evidence")
    rows = shadow.get("countries")
    require(isinstance(rows, dict) and set(rows) == set(G8), "G8 missing or unexpected currencies")
    require(isinstance(legacy, dict) and
            set(legacy.get("macro", {})) == set(G8), "legacy G8 mismatch")
    old_day, candidate_day = date.fromisoformat(legacy["asOf"]), date.fromisoformat(shadow["as_of"])
    require(old_day <= candidate_day, "old snapshot in future of economic as-of")
    cases = {}
    for currency in G8:
        row = rows[currency]
        require(row.get("currency") == currency
                and row.get("approved_for_live_core_D") is False
                and row.get("candidate_for_pair_ranking") is False
                and row.get("fx_currency_strength_score") is None
                and row.get("fx_directional_bias") is None
                and row.get("policy_rate_signal") is None
                and row.get("cb_pricing_signal") is None,
                currency + ": unapproved input or policy-derived FX claim")
        g = numeric(row.get("growth_relative_to_own_history_z"), currency+".growth")
        l = numeric(row.get("labour_tightness_relative_to_own_history_z"), currency+".labour")
        p = numeric(row.get("inflation_pressure_relative_to_own_history_z"), currency+".inflation")
        activity = W_GROWTH*g + W_LABOUR*l + W_INFLATION*p
        require(math.isclose(activity, row["illustrative_activity_labour_balance_z"],
                             rel_tol=0, abs_tol=1e-9),
                currency + ": conflict with upstream registered arithmetic")
        scenarios = {str(int(w*100)): round(w*g+(1-w)*l,12)
                     for w in SENSITIVITY_GROWTH_WEIGHTS}
        state = activity_class(activity)
        sensitivity = continuous_weight_interval(g, l)
        revision_stresses = {
            str(int(eps*100)): independent_axis_revision_envelope(g, l, eps)
            for eps in REVISION_STRESS_EPSILONS_Z
        }
        require(all(not item["class_invariant_to_all_weights_and_independent_axis_shifts"]
                    or sensitivity["classification_unchanged_at_every_weight_in_interval"]
                    for item in revision_stresses.values()),
                currency + ": stress robustness cannot exceed weight-only robustness")
        stable = sensitivity["classification_unchanged_at_every_weight_in_interval"]
        require(stable == all(activity_class(w*g+(1-w)*l) == state
                              for w in SENSITIVITY_GROWTH_WEIGHTS),
                currency + ": discrete vs continuous weight stability mismatch")
        quality = list(row.get("quality_flags", []))
        dims = row.get("dimensions", {})
        require(set(dims) == {"growth", "labour", "inflation"}, currency+": 3 dimensions required")
        require(all(dims[k].get("reference_period") for k in dims),
                currency+": undated economic observation")
        require(all(dims[k].get("quality") for k in dims),
                currency+": unlabeled source quality")
        prior = legacy["macro"][currency]
        require(all(type(prior.get(k)) in (int,float) and math.isfinite(prior[k])
                    for k in ("growth","labour","inflation")) and
                isinstance(prior.get("cycle"), str),
                currency+": baseline economic scalars missing")
        cases[currency] = {
            "growth_within_history_z":g,
            "unemployment_tightness_within_history_z":l,
            "inflation_pressure_within_history_z":p,
            "domestic_activity_candidate_z":round(activity,12),
            "domestic_activity_class":state,
            "domestic_inflation_pressure_class":price_class(p),
            "indicative_domestic_regime":indicative_regime(activity,p),
            "weights_growth_labour": [W_GROWTH,W_LABOUR],
            "growth_weight_sensitivity_z":scenarios,
            "continuous_weight_sensitivity_RESEARCH_ONLY":sensitivity,
            "hypothetical_axis_revision_stress_RESEARCH_ONLY":revision_stresses,
            "activity_class_stable_across_25_50_75pct_growth":stable,
            "source_quality_flags":quality,
            "source_quality_details":{
                k:{"period":dims[k]["reference_period"],
                   "method":dims[k]["method"],
                   "quality":dims[k]["quality"],
                   "is_estimate":dims[k]["is_estimate"]}
                for k in ("growth","labour","inflation")},
            "historical_D_values_for_uncomparable_reference_only":{
                k:prior[k] for k in ("growth","labour","inflation","cycle")},
            "legacy_D_numbers_are_NOT_in_new_candidate_units":True,
            "FX_strength_candidate":None,
            "official_ECB_BoE_Fed_policy_effect":None,
            "eligible_to_recalculate_28_pairs":False,
            "eligible_for_beta_forward":False,
        }
    output = {
        "schema": SCHEMA, "formula_version": FORMULA,
        "economic_as_of":shadow["as_of"], "legacy_core_as_of":legacy["asOf"],
        "status": "EXPLICIT_8_COUNTRY_MACRO_CANDIDATE_RESEARCH_NO_PIT_NO_FX",
        "equation": "domestic_activity_z = .50*GDP_prior12Q_z + .50*(-unemployment_prior24M_or12Q_z); price_pressure_z = CPI_history_z; CPI_weight_in_activity=0",
        "within_country_z_scores_not_identical_data_definitions_or_country_comparable":True,
        "economic_regime_is_hypothetical_not_legacy_cycle":True,
        "future_policy_risk_COT_price_FX_calibration_required":True,
        "historical_first_publication_PIT_not_certified":True,
        "growth_definition_caveats_and_estimates_visible":True,
        "out_of_sample_falsification_not_completed":True,
        "revision_stress_is_hypothetical_not_data_calibrated":True,
        "canonical_core_score_formula_recovered":False,
        "countries":cases,
        "summary":{
            "currencies":len(cases), "axes":len(cases)*3,
            "countries_unstable_to_weights":sum(not x["activity_class_stable_across_25_50_75pct_growth"] for x in cases.values()),
            "countries_robust_for_ALL_continuous_weights_25_75pct":sum(
                x["continuous_weight_sensitivity_RESEARCH_ONLY"][
                    "classification_unchanged_at_every_weight_in_interval"
                ] for x in cases.values()
            ),
            "countries_weight_ambiguous_no_robust_class":sum(
                x["continuous_weight_sensitivity_RESEARCH_ONLY"][
                    "weight_invariant_domestic_class_RESEARCH_ONLY"
                ] is None for x in cases.values()
            ),
            "countries_robust_hypothetical_axis_shift_0p10_z":sum(
                x["hypothetical_axis_revision_stress_RESEARCH_ONLY"]["10"][
                    "class_invariant_to_all_weights_and_independent_axis_shifts"]
                for x in cases.values()),
            "countries_robust_hypothetical_axis_shift_0p25_z":sum(
                x["hypothetical_axis_revision_stress_RESEARCH_ONLY"]["25"][
                    "class_invariant_to_all_weights_and_independent_axis_shifts"]
                for x in cases.values()),
            "countries_robust_hypothetical_axis_shift_0p50_z":sum(
                x["hypothetical_axis_revision_stress_RESEARCH_ONLY"]["50"][
                    "class_invariant_to_all_weights_and_independent_axis_shifts"]
                for x in cases.values()),
            "countries_with_estimates":sum(any(d["is_estimate"] for d in x["source_quality_details"].values()) for x in cases.values()),
            "FX_scores_produced":0,
            "28_pair_theses_recomputed":0,
            "D_json_rebuilt":False,
        },
        "safe_to_publish_D":False,
        "safe_to_update_pair_theses":False,
        "safe_to_use_for_beta":False,
        "safe_to_use_for_forward":False,
        "writes_live_data":False,
    }
    output["receipt_sha256"]=hashlib.sha256(json.dumps(output,sort_keys=True,
        separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return output


def run(as_of=None, legacy_path=None):
    root=Path(__file__).resolve().parents[2]
    legacy_path=legacy_path or root/"live_data/sections/D.json"
    return build(shadow_run(as_of=as_of), json.loads(legacy_path.read_text(encoding="utf-8")))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--as-of")
    parser.add_argument("--out",type=Path)
    a=parser.parse_args()
    if a.out:
        require(a.out.resolve().is_relative_to(Path("/tmp")),
                "research-only file must be under /tmp")
    result=run(as_of=a.as_of)
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"summary":result["summary"],
                      "safe_to_publish_D":result["safe_to_publish_D"],
                      "receipt_sha256":result["receipt_sha256"]},sort_keys=True))


if __name__=="__main__":
    main()
