#!/usr/bin/env python3
"""Adversarial sensitivity + GDP release-clock research for Macro V2 G8.

1. Re-evaluate a pre-registered *illustrative* Growth/Labour activity mix for
   25/50/75% Growth weights, plus one-axis-at-a-time +/-0.25-z measurement
   shocks. This is NOT calibrated, confidence interval, model score or FX rank.
2. Replay 8 GDP first-web releases per currency for 2024Q3..2026Q2, always
   from the next UTC date after the publisher's date-only first statement.
   Late revisions must never be used for the first-web training. This tests
   cutoff consistency ONLY: historic first-day immutable source archives and
   inflation/labour same-clock PIT inputs remain missing. NO backtest claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from validation.macro.v2_g8_gdp_first_web_growth_features_v1 import (
    FX, asof_visible, qidx, qlabel, receipt as gdp_receipt
)
from validation.macro.v2_g8_gdp_unified_web_research_v1 import unified_research_rows
from validation.macro.v2_g8_three_axis_economic_shadow_v1 import (
    ROOT, SCHEMA as THREE_AXIS_SCHEMA, build as build_three_axis,
    run as run_three_axis, zone
)

SCHEMA = "GMFQ_MACRO_V2_G8_SENSITIVITY_RELEASE_CLOCK_AUDIT_V1"
WEIGHT_GROWTH = (0.25, 0.50, 0.75)
STRESS_Z = 0.25
FIRST_REPLAY_QUARTER = "2024Q3"
LAST_REPLAY_QUARTER = "2026Q2"
REPLAY_QUARTERS = tuple(qlabel(i) for i in range(
    qidx(FIRST_REPLAY_QUARTER), qidx(LAST_REPLAY_QUARTER) + 1))


def must(ok, msg):
    if not ok:
        raise ValueError("MACRO_V2_SENSITIVITY_REJECTED: " + msg)


def activity(growth, labour, weight):
    must(all(type(x) in (int, float) and math.isfinite(x)
             for x in (growth, labour, weight)) and 0 <= weight <= 1,
         "finite research-only inputs and bounded Growth weight needed")
    # Never clip a proxy across countries, fit to D.json or include inflation.
    return weight * growth + (1.0 - weight) * labour


def activity_bucket(value):
    return zone(value, "RELATIVELY_FIRM", "RELATIVELY_SOFT")


def sensitivity(three_axis):
    must(three_axis.get("schema") == THREE_AXIS_SCHEMA and
         three_axis.get("status") ==
         "EIGHT_SHADOW_THREE_AXIS_ECONOMIC_SCENARIOS_NOT_MACRO_SCORES" and
         three_axis.get("safe_to_publish_new_D") is False and
         three_axis.get("safe_to_update_pair_theses") is False and
         three_axis.get("safe_for_beta") is False and
         three_axis.get("safe_for_forward") is False and
         three_axis.get("writes_live_data") is False and
         three_axis.get("summary", {}).get("macro_model_scores_approved") == 0 and
         three_axis.get("summary", {}).get("FX_scores_approved") == 0,
         "three-axis upstream report must remain research-only")
    countries = three_axis.get("countries")
    must(isinstance(countries, dict) and set(countries) == set(FX),
         "all eight independent within-country cases required")
    must(three_axis["scope"]["activity_weights"] ==
         {"growth": 0.5, "labour_tightness": 0.5, "inflation_in_activity": 0.0},
         "preregistered baseline weights changed")
    details = {}
    for c in FX:
        row = countries[c]
        must(row.get("currency") == c and row.get("fx_currency_strength_score") is None
             and row.get("fx_directional_bias") is None and
             row.get("candidate_for_pair_ranking") is False and
             row.get("approved_for_live_core_D") is False and
             row.get("economic_cycle_certified") is None,
             "unknown or promoted country macro status")
        g, l, p = (row.get("growth_relative_to_own_history_z"),
                   row.get("labour_tightness_relative_to_own_history_z"),
                   row.get("inflation_pressure_relative_to_own_history_z"))
        must(all(type(x) in (int, float) and math.isfinite(x) and
                 -3.00000001 <= x <= 3.00000001 for x in (g, l, p)),
             "missing or nonfinite economic axis")
        baseline = activity(g, l, 0.5)
        must(abs(baseline - row["illustrative_activity_labour_balance_z"]) < 1e-9,
             "shadow reported value disagrees with preregistered baseline")
        weights = {f"growth_{int(round(w*100))}pct": round(activity(g, l, w), 12)
                   for w in WEIGHT_GROWTH}
        buckets = {k: activity_bucket(v) for k, v in weights.items()}
        shocks = {}
        for axis, base in (("growth", g), ("labour_tightness", l)):
            for delta in (-STRESS_Z, STRESS_Z):
                perturbed = max(-3.0, min(3.0, base + delta))
                new_g, new_l = ((perturbed, l) if axis == "growth"
                                else (g, perturbed))
                label = f"{axis}_{'minus' if delta < 0 else 'plus'}_{int(STRESS_Z*100)}bp_z"
                shocks[label] = {
                    "input_delta_z": round(perturbed - base, 12),
                    "activity_balance_z": round(activity(new_g, new_l, 0.5), 12),
                    "activity_bucket": activity_bucket(activity(new_g, new_l, 0.5)),
                }
        responses = [v["activity_balance_z"] for v in shocks.values()]
        details[c] = {
            "currency": c,
            "baseline_activity_balance_z": round(baseline, 12),
            "baseline_bucket": activity_bucket(baseline),
            "alternative_weights_growth_25_50_75": weights,
            "weight_variant_activity_buckets": buckets,
            "weight_variation_min_z": min(weights.values()),
            "weight_variation_max_z": max(weights.values()),
            "weight_variation_range_z": round(max(weights.values()) - min(weights.values()), 12),
            "weight_category_changes": len(set(buckets.values())) > 1,
            "one_axis_plus_minus_0_25z_shocks": shocks,
            "input_shock_min_activity_z": min(responses),
            "input_shock_max_activity_z": max(responses),
            "input_shock_changes_baseline_category":
                any(v["activity_bucket"] != activity_bucket(baseline)
                    for v in shocks.values()),
            "inflation_pressure_z_stays_separate": float(p),
            "source_quality_flags": row["quality_flags"],
            "source_quality_label": row["qualitative_quality"],
            "one_country_only_not_cross_currency_comparable": True,
            "estimated_uncertainty_interval": False,
            "live_currency_score": None,
            "pair_ranking_eligible": False,
        }
    return {
        "schema": SCHEMA,
        "section": "WITHIN_COUNTRY_WEIGHT_AND_INPUT_SENSITIVITY_RESEARCH_ONLY",
        "weights_tested_growth": list(WEIGHT_GROWTH),
        "baseline_growth_weight": 0.5, "other_weight_is_labour_tightness": True,
        "inflation_used_for_activity_weight": False,
        "shock_axis_change_z": STRESS_Z,
        "shock_size_is_scenario_not_estimated_measurement_error": True,
        "countries": details,
        "summary": {
            "currencies": len(details),
            "within_country_weights_per_currency": len(WEIGHT_GROWTH),
            "countries_where_bucket_changes_with_weights": sum(
                x["weight_category_changes"] for x in details.values()),
            "countries_where_bucket_changes_with_input_shock": sum(
                x["input_shock_changes_baseline_category"] for x in details.values()),
            "FX_rankings_computed": 0, "macro_scores_approved": 0,
        },
        "no_cross_currency_ranking_authorized": True,
        "source_report_fingerprint_sha256": three_axis["receipt_sha256"],
        "safe_to_publish_new_D": False, "safe_to_update_pair_theses": False,
        "safe_to_use_for_beta": False, "safe_to_use_for_forward": False,
    }


def gdp_publication_clock_replay(rows):
    """Historical proof about first-web availability gates, NOT an FX OOS test."""
    # Parse and validate the FULL evidence dossier on each cutoff. This ensures
    # malformed, future or revised sources cannot silently overwrite first.
    first = {(x["currency"], x["reference_quarter"]): x
             for x in rows if x.get("stage_order") == 0}
    must(all((c, q) in first for c in FX for q in REPLAY_QUARTERS),
         "complete eight-country eight-quarter initial web releases required")
    observations = {c: [] for c in FX}
    for c in FX:
        for q in REPLAY_QUARTERS:
            current_first = first[c, q]
            release_gate = asof_visible(current_first)
            cutoff = release_gate.isoformat()
            report = gdp_receipt(rows, as_of=cutoff)
            item = report["features"][c]
            must(item["latest_initial_period"] == q and
                 item["latest_first_web_release_day"] ==
                 current_first["publisher_release_day"] and
                 item["latest_visible_revision"] is None and
                 item["research_robust_growth_z"] is not None and
                 item["training_window_end"] == qlabel(qidx(q) - 1) and
                 item["current_initial_value_excluded_from_training"] is True and
                 item["actual_PIT_backtest_eligible"] is False and
                 report["can_publish_D_json"] is False,
                 "GDP current first-statement feature changed at publisher gate")
            before = (release_gate - __import__("datetime").timedelta(microseconds=1))
            earlier = gdp_receipt(rows, as_of=before.isoformat())["features"][c]
            must(earlier["latest_initial_period"] == qlabel(qidx(q) - 1),
                 "GDP future first release was visible before publisher gate")
            observations[c].append({
                "reference_quarter": q,
                "first_web_publisher_date": current_first["publisher_release_day"],
                "conservative_visible_from_utc": cutoff,
                "source_url": current_first["source_url"],
                "first_web_descriptive_growth_z": item["research_robust_growth_z"],
                "first_web_qoq_nonannualized_pct":
                    item["latest_nonannualized_qoq_pct"],
                "first_web_release_clock_cutoff_obeyed": True,
                "first_web_training_excludes_same_quarter": True,
                "not_a_historical_backtest_PIT_certification": True,
                "country_metric_definition_caveats":
                    item.get("growth_definition_caveats", []),
            })
    result = {}
    for c in FX:
        vals = [x["first_web_descriptive_growth_z"] for x in observations[c]]
        consecutive_moves = [abs(b - a) for a, b in zip(vals, vals[1:])]
        result[c] = {
            "quarterly_first_web_research_replays": observations[c],
            "quarters_checked": len(observations[c]),
            "descriptive_growth_z_rolling_changes": consecutive_moves,
            "max_absolute_next_quarter_z_change": max(consecutive_moves),
            "proven_first_release_intraday_knowledge": False,
            "archived_original_day_publication_bytes_verified": False,
            "valid_joint_macro_asof_replay": False,
            "valid_FX_backtest": False,
        }
    return {
        "schema": "GMFQ_MACRO_V2_G8_GDP_RELEASE_CLOCK_REPLAY_V1",
        "scope": f"{FIRST_REPLAY_QUARTER}_THROUGH_{LAST_REPLAY_QUARTER}",
        "selection": "PUBLISHER_FIRST_WEB_STATEMENT_AVAILABLE_FROM_NEXT_UTC_DAY_ONLY",
        "countries": result,
        "summary": {
            "g8_currencies": len(result),
            "quarters_each": len(REPLAY_QUARTERS),
            "first_web_currency_quarter_cases": sum(
                d["quarters_checked"] for d in result.values()),
            "cutoff_guard_failures": 0,
            "historic_first_release_bytes_certified": 0,
            "whole_macro_joint_PIT_test_cases": 0,
            "FX_out_of_sample_trading_tests": 0,
        },
        "not_proof_of_historical_asof_macro_training": True,
        "not_an_out_of_sample_FX_study": True,
        "safe_to_publish_new_D": False, "safe_to_update_pair_theses": False,
        "safe_to_use_for_beta": False, "safe_to_use_for_forward": False,
    }


def audit(*, as_of=None, gdp_rows=None, three_axis=None):
    root = three_axis if three_axis is not None else run_three_axis(as_of=as_of)
    weights = sensitivity(root)
    chronology = gdp_publication_clock_replay(
        gdp_rows if gdp_rows is not None else unified_research_rows())
    must(weights["summary"]["currencies"] == 8 and
         chronology["summary"]["first_web_currency_quarter_cases"] == 64 and
         chronology["summary"]["cutoff_guard_failures"] == 0,
         "eight-country scenario or release-clock coverage lost")
    result = {
        "schema": SCHEMA,
        "version": "SHADOW_STRESS_NOT_VALIDATION_2026_10_27",
        "as_of": root["as_of"],
        "status": "MATH_SENSITIVITY_AND_GDP_CLOCK_CHECKS_NOT_OUT_OF_SAMPLE_VALIDATION",
        "weights_and_input_stress": weights,
        "GDP_web_release_clock": chronology,
        "summary": {
            **weights["summary"],
            "GDP_release_clock_cases": 64,
            "FX_out_of_sample_trials": 0,
            "certified_macro_scores": 0,
        },
        "computation_not_independent_source_pit_certification": True,
        "macro_labour_inflation_historic_pit_replay_still_missing": True,
        "no_trading_edge_or_predictive_performance_demonstrated": True,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "safe_to_use_for_beta": False,
        "safe_to_use_for_forward": False,
        "writes_live_data": False,
    }
    result["audit_sha256"] = hashlib.sha256(json.dumps(
        {"version": result["version"], "as_of": result["as_of"],
         "sensitivity": weights, "clock": chronology},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return result


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--as-of", default=None)
    cli.add_argument("--output", type=Path)
    options = cli.parse_args()
    if options.output is not None:
        must(options.output.resolve().is_relative_to(Path("/tmp")),
             "research output must remain in /tmp")
    out = audit(as_of=options.as_of)
    if options.output is not None:
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                                  encoding="utf-8")
    print(json.dumps({"schema": out["schema"], "status": out["status"],
                      **out["summary"], "safe_to_publish_new_D": False},
                     sort_keys=True))
    # Case-by-case diagnostics: user-facing trace, not a relative FX ranking.
    for currency in FX:
        item = out["weights_and_input_stress"]["countries"][currency]
        print(json.dumps({
            "currency": currency,
            "baseline_activity_balance_z": item["baseline_activity_balance_z"],
            "baseline_bucket": item["baseline_bucket"],
            "weight_25_50_75_buckets": item["weight_variant_activity_buckets"],
            "weight_changes_category": item["weight_category_changes"],
            "shock_changes_category": item["input_shock_changes_baseline_category"],
            "quality_flags": item["source_quality_flags"],
            "fx_strength_score": None,
        }, sort_keys=True))


if __name__ == "__main__":
    main()
