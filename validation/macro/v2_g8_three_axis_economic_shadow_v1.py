#!/usr/bin/env python3
"""Macro V2 G8: three-axis shadow economic diagnostics, no FX score.

Pre-registered arithmetic on the 24-source research bridge: Growth relative
to 12 prior first-publisher WEB quarterly statements; unemployment tightness
relative to 24 prior dated monthly / 12 quarterly observed values (inverted);
inflation pressure relative to its own history (NOT currency desirability).

This prototype deliberately neither computes a *live* Macro Strength score
nor reconstructs legacy D.json, backtests, applies rates/CB pricing, estimates
FX direction, or reranks currency pairs. "Activity" here is a HYPOTHETICAL
50/50 sum of two within-series z values, not measured FX strength.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.v2_g8_observed_feature_bridge_v1 import (
    FX, ROOT, SCHEMA as INPUT_SCHEMA, run as observed_run
)

SCHEMA = "GMFQ_MACRO_V2_G8_THREE_AXIS_ECONOMIC_RESEARCH_V1"
VERSION = "PRE_REGISTERED_HYPOTHESIS_2026_10_27"
AXIS_THRESHOLD = 0.5
WEIGHTS = {"growth": 0.5, "labour_tightness": 0.5, "inflation_in_activity": 0.0}
EXPECTED_LABOUR = {
    "USD": "UNRATE", "EUR": "EA_UNEMP", "GBP": "MGSX",
    "JPY": "JP_UNEMP_RATE", "CHF": "CH_UNEMP_RATE",
    "CAD": "CA_UNEMP_RATE", "AUD": "AU_UNEMP_RATE", "NZD": "NZ_UNEMP_RATE"
}
EXPECTED_CAVEATS = {
    "EUR": ("EURO_AREA_POPULATION_DEFINITION_NOT_UNIFORM_OR_UNPINNED",),
    "CHF": ("SWISS_INITIAL_GDP_SPORTS_FLASH_DEFINITION_MIXED",),
}
GAP_METHOD = "GMFQ_MACRO_V2_BLS_OCT2025_STRUCTURAL_GAP_RESEARCH_V1"
GROWTH_STATUS = {
    "DESCRIPTIVE_INITIAL_WEB_GROWTH_Z_DEFINITION_CAVEAT",
    "DESCRIPTIVE_INITIAL_WEB_GROWTH_Z_NOT_MODEL_CERTIFIED",
}


def need(condition, message):
    if not condition:
        raise ValueError("MACRO_V2_THREE_AXIS_REJECTED: " + message)


def z(value, name):
    need(type(value) in (float, int) and math.isfinite(value) and
         -3.000000001 <= value <= 3.000000001,
         name + ": finite clipped within-history z required")
    return float(value)


def zone(value, positive, negative):
    if value >= AXIS_THRESHOLD:
        return positive
    if value <= -AXIS_THRESHOLD:
        return negative
    return "NEAR_OWN_HISTORY_MIDPOINT"


def _pillar(inp, gaps, currency, pillar):
    entry = inp[f"{currency}.{pillar}"]
    need(entry["currency"] == currency and entry["pillar"] == pillar,
         "research pillar identity mismatch")
    need(entry.get("eligible_for_macro_score") is False and
         entry.get("eligible_for_historical_backtest") is False and
         entry.get("source_observation_is_current_revised_history_not_historic_pit") is True,
         "unapproved pillar certification or mutation")
    need(entry.get("economic_interpretation") ==
         ("LABOUR_TIGHTNESS_NOT_FX_STRENGTH" if pillar == "labour"
          else "PRICE_PRESSURE_NOT_FX_STRENGTH"),
         "pillar polarity/FX distinction lost")
    if pillar == "labour":
        need(entry.get("canonical_series_id") == EXPECTED_LABOUR[currency] and
             entry.get("transformation") == "level",
             "only unemployment rate can use negative-is-tight labour polarity")
    else:
        need(entry.get("canonical_series_id") not in EXPECTED_LABOUR.values(),
             "inflation source swapped with unemployment")

    strict = entry.get("research_robust_z")
    key = f"{currency}.{pillar}"
    if strict is not None:
        need(entry.get("status") == "DESCRIPTIVE_REVISED_HISTORY_ROBUST_Z_NOT_PIT",
             "strict z without complete-source status")
        need(key not in gaps, "official and estimated intensity must not double-count")
        return {"raw_z": z(strict, key), "method": "OBSERVED_REVISED_HISTORY_24M_OR_12Q",
                "is_estimate": False, "reference_period": entry["observation_period"],
                "source_id": entry["canonical_series_id"],
                "quality": "RESEARCH_CURRENT_REVISED_HISTORY_NO_HISTORIC_PIT"}
    need(currency == "USD" and key in gaps and
         entry.get("status") == "NO_Z_MISSING_PRIOR_ECONOMIC_PERIODS",
         "missing strict z cannot be replaced by unapproved estimates")
    est = gaps[key]
    need(est.get("schema") == GAP_METHOD and est.get("dimension") == pillar and
         est.get("status") == "BLS_SHUTDOWN_GAP_AWARE_RESEARCH_ESTIMATE_NOT_PIT" and
         est.get("canonical_source_id") == entry["canonical_series_id"] and
         est.get("actual_current_observation_period") == entry["observation_period"] and
         est.get("missing_calendar_periods") == ["2025-10"] and
         est.get("structurally_missing_economic_month") == "2025-10" and
         est.get("training_observed_months_used") == 24 and
         est.get("original_missing_value_imputed") is False and
         est.get("source_history_modified") is False and
         est.get("allow_macro_score") is False and
         est.get("allow_pair_ranking") is False and
         est.get("allow_beta") is False and
         est.get("allow_forward") is False,
         "US October 2025 provenance or forecast restriction mismatch")
    return {"raw_z": z(est.get("estimated_research_robust_z"), key),
            "method": "ESTIMATE_BLS_SHUTDOWN_EXACT_ONE_GAP_25_CALENDAR_MONTHS",
            "is_estimate": True, "reference_period": entry["observation_period"],
            "source_id": entry["canonical_series_id"],
            "quality": "ESTIMATED_NOT_OBSERVED_24_CONSECUTIVE_MONTHS_NO_PIT",
            "reason": est["missing_cause"],
            "source_evidence_url": est["official_evidence_url"]}


def _growth(g, currency):
    need(g["currency"] == currency and g.get("status") in GROWTH_STATUS,
         "GDP initial-web status/identity not approved for even descriptive arithmetic")
    need(g.get("numeric_model_growth_score") is None and
         g.get("safe_to_promote_growth_score") is False and
         g.get("actual_PIT_backtest_eligible") is False and
         g.get("historical_original_publisher_day_bytes_certified") is False and
         g.get("current_initial_value_excluded_from_training") is True and
         g.get("training_prior_quarters_required") == 12,
         "GDP first-release research-only contract or 12Q guard changed")
    caveats = tuple(g.get("growth_definition_caveats", ()))
    need(caveats == EXPECTED_CAVEATS.get(currency, ()),
         "expected EUR/CHF GDP economic definition quality flags not preserved")
    return {"raw_z": z(g.get("research_robust_growth_z"), currency + ".growth"),
            "method": "FIRST_WEB_GDP_12_PRIOR_QUARTERS_RESEARCH_ONLY",
            "is_estimate": False, "reference_period": g["latest_initial_period"],
            "source_url": g["latest_source_url"],
            "quality": ("GDP_FIRST_WEB_DEFINITION_CAVEAT_NO_PIT" if caveats else
                        "GDP_FIRST_WEB_RESEARCH_NO_ORIGINAL_DAY_ARCHIVE"),
            "definition_caveats": list(caveats)}


def build(observed):
    """Input is today's snapshot, NEVER a historical replayable vintage ledger."""
    need(isinstance(observed, dict) and observed.get("schema") == INPUT_SCHEMA
         and observed.get("status") ==
         "OBSERVED_G8_RESEARCH_FEATURES_NOT_CERTIFIED_MACRO_MODEL"
         and observed.get("source_class") ==
         "TODAY_REVISED_OBSERVATIONS_NOT_REPLAYABLE_HISTORICAL_PIT"
         and observed.get("safe_to_publish_new_D") is False and
         observed.get("safe_to_update_pair_theses") is False and
         observed.get("safe_to_use_for_beta") is False and
         observed.get("safe_to_use_for_forward") is False and
         observed.get("writes_live_data") is False and
         observed.get("gdp_initial_web_features_not_model_growth_scores") is True and
         observed.get("optional_us_gap_estimates_not_replacements_for_strict_z") is True,
         "wrong or promoted G8 observational bridge contract")
    s = observed["summary"]
    need(s["economic_dimension_slots"] == 24 and
         s["registered_inflation_labour_slots"] == 16 and
         s["growth_scores_computed"] == 0 and
         s["fx_strength_scores_computed"] == 0 and
         s["gdp_descriptive_research_growth_features"] == 8,
         "not exactly 24 shadow pillars or unexpected model scores")
    p = observed.get("inflation_labour")
    g = observed.get("growth_quarterly_gdp_initial_web_research_features")
    gaps = observed.get("us_bls_shutdown_research_estimates")
    need(isinstance(p, dict) and set(p) ==
         {f"{c}.{d}" for c in FX for d in ("inflation", "labour")} and
         isinstance(g, dict) and set(g) == set(FX) and
         isinstance(gaps, dict) and set(gaps) <=
         {"USD.inflation", "USD.labour"}, "G8 24 input identity or gap-estimate scope")
    need(date.fromisoformat(observed["checked_as_of"]) <=
         datetime.now(ZoneInfo("Europe/Rome")).date(),
         "research clock cannot be in the future")

    rows = {}
    for currency in FX:
        growth = _growth(g[currency], currency)
        labour = _pillar(p, gaps, currency, "labour")
        inflation = _pillar(p, gaps, currency, "inflation")
        tightness = -labour["raw_z"]
        # Fixed, NOT fit to FX returns or the old D vector. Price pressure
        # must NOT act as a proxy for economic health or currency strength.
        activity = WEIGHTS["growth"] * growth["raw_z"] + (
            WEIGHTS["labour_tightness"] * tightness)
        price = inflation["raw_z"]
        flags = []
        if labour["is_estimate"] or inflation["is_estimate"]:
            flags.append("US_BLS_ESTIMATED_INFLATION_LABOUR_Z")
        flags.extend(growth["definition_caveats"])
        rows[currency] = {
            "currency": currency,
            "growth_relative_to_own_history_z": growth["raw_z"],
            "labour_tightness_relative_to_own_history_z": tightness,
            "inflation_pressure_relative_to_own_history_z": price,
            "illustrative_activity_labour_balance_z": round(activity, 12),
            "axis_classification_relative_to_own_history": {
                "activity": zone(activity, "RELATIVELY_FIRM", "RELATIVELY_SOFT"),
                "price_pressure": zone(price, "RELATIVELY_ELEVATED", "RELATIVELY_SUBDUED"),
            },
            "dimensions": {"growth": growth, "labour": labour, "inflation": inflation},
            "quality_flags": flags,
            "qualitative_quality": (
                "ESTIMATED_WITH_DEFINITION_CAVEAT" if (
                    (labour["is_estimate"] or inflation["is_estimate"]) and
                    bool(growth["definition_caveats"])) else
                "ESTIMATED_RESEARCH_ONLY" if (
                    labour["is_estimate"] or inflation["is_estimate"]) else
                "GDP_DEFINITION_CAVEAT_RESEARCH_ONLY" if
                    growth["definition_caveats"] else
                "REVISED_OR_WEB_RESEARCH_NOT_PIT"),
            "economic_cycle_certified": None,
            "policy_rate_signal": None,
            "cb_pricing_signal": None,
            "fx_currency_strength_score": None,
            "fx_directional_bias": None,
            "candidate_for_pair_ranking": False,
            "approved_for_live_core_D": False,
        }

    out = {
        "schema": SCHEMA,
        "version": VERSION,
        "as_of": observed["checked_as_of"],
        "status": "EIGHT_SHADOW_THREE_AXIS_ECONOMIC_SCENARIOS_NOT_MACRO_SCORES",
        "scope": {
            "currencies": list(FX), "economic_axes": 24,
            "horizon_note": "Quarterly first publisher GDP and monthly/quarterly revised inflation/labour are NOT synchronized publication-vintage inputs.",
            "activity_weights": WEIGHTS,
            "zone_threshold_z": AXIS_THRESHOLD,
            "activity_is_hypothetical_within_country_not_rank_comparable": True,
            "inflation_is_pressure_not_good_or_bad_for_currency": True,
        },
        "countries": rows,
        "summary": {
            "economies": len(rows), "research_axes": 3 * len(rows),
            "research_activity_balances_calculated": len(rows),
            "countries_with_estimated_source_axes": sum(
                "US_BLS_ESTIMATED_INFLATION_LABOUR_Z" in x["quality_flags"]
                for x in rows.values()),
            "countries_with_GDP_measurement_caveats": sum(
                bool(x["dimensions"]["growth"]["definition_caveats"])
                for x in rows.values()),
            "macro_model_scores_approved": 0,
            "FX_scores_approved": 0,
            "pair_rankings_recalculated": 0,
        },
        "observed_bridge_fingerprint": observed["input_fingerprint_sha256"],
        "observed_data_is_not_historic_publication_vintage_replay": True,
        "economic_axis_math_not_validated_against_out_of_sample_events": True,
        "rates_CB_pricing_positioning_not_included": True,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "safe_for_beta": False,
        "safe_for_forward": False,
        "writes_live_data": False,
    }
    out["receipt_sha256"] = hashlib.sha256(json.dumps(
        {"version": VERSION, "as_of": out["as_of"], "countries": rows,
         "input": out["observed_bridge_fingerprint"]},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return out


def run(*, as_of=None):
    return build(observed_run(as_of=as_of))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is not None:
        need(args.output.resolve().is_relative_to(Path("/tmp")),
             "research receipt must stay in /tmp")
    result = run(as_of=args.as_of)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({"schema": SCHEMA, "status": result["status"],
                      **result["summary"], "safe_to_publish_new_D": False},
                     sort_keys=True))


if __name__ == "__main__":
    main()
