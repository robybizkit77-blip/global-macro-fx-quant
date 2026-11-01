#!/usr/bin/env python3
"""New Macro V3 observational input: current 8 G8 economies and 28 pair contexts.

This is the FIRST live-source economic evidence layer for a future, separately
validated Core replacement, NOT a rebadged legacy D.json score. Uses complete
latest source values, dates and past observed changes even where a robust
z-score cannot be computed (zero MAD or missing historical PIT windows).
A data gap, source mismatch or future observation fails explicitly; it is
never turned into zero, a point estimate, an FX bias or a false backtest.

Economic observation periods are NOT publisher release timestamps. Current
MACRO_SERIES history is revised, and GDP first-web research is not an
immutable full PIT archive. No output here is a tradable FX strength score.
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
    run as observed_run, SCHEMA as OBSERVED_SCHEMA, ROOT
)
from validation.macro.v3_gdp_q3_official_overlay_v1 import observed_q3_updates

FX = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
SCHEMA = "GMFQ_MACRO_V3_CURRENT_G8_28PAIR_OBSERVED_ECONOMIC_CONTEXT_V1"
MODEL = "V3_DESCRIPTIVE_OBSERVED_THREE_PILLAR_CHANGES_2026_11_01"
# Predeclared descriptive noise bands in percentage points, not a fitted
# statistical test, change-point probability or FX decision threshold.
OBSERVATION_NOISE_PP = 0.05


def need(ok, why):
    if not ok:
        raise ValueError("MACRO_V3_ECONOMIC_INPUT_REJECTED: " + why)


def number(x, why):
    need(type(x) in (int, float) and math.isfinite(x), why + " must be finite")
    return float(x)


def period_month(s, why):
    need(isinstance(s, str) and len(s) in (7, 10), why + " date precision")
    try:
        m = date.fromisoformat(s[:7] + "-01")
        if len(s) == 10:
            need(date.fromisoformat(s).isoformat() == s, why + " invalid day")
    except ValueError as exc:
        raise ValueError("MACRO_V3_ECONOMIC_INPUT_REJECTED: " + why + " invalid date") from exc
    need(m.strftime("%Y-%m") == s[:7], why + " noncanonical month")
    return m


def movement(delta):
    # This is a change in the OBSERVATION value, not a shock vs consensus.
    return "UP" if delta > OBSERVATION_NOISE_PP else (
        "DOWN" if delta < -OBSERVATION_NOISE_PP else "FLAT")


def load(name):
    return json.loads((ROOT / "live_data" / "sections" / (name + ".json"))
                      .read_text(encoding="utf-8"))


def build(observed, heat, legacy, setup, *, as_of):
    cutoff = date.fromisoformat(as_of)
    need(observed.get("schema") == OBSERVED_SCHEMA and
         observed.get("checked_as_of") == as_of and
         observed.get("status") == "OBSERVED_G8_RESEARCH_FEATURES_NOT_CERTIFIED_MACRO_MODEL" and
         observed.get("writes_live_data") is False and
         observed.get("safe_to_publish_new_D") is False and
         observed.get("safe_to_update_pair_theses") is False,
         "upstream revised-history research cannot be promoted into FX signals")
    need(heat.get("schema_version") == "GMFQ_MACRO_HEATMAP_V1" and
         heat.get("status") == "ACTIVE" and
         set(heat.get("currencies", {})) == set(FX),
         "G8 thermometer source coverage changed")
    need(set(observed.get("inflation_labour", {})) ==
         {c + "." + p for c in FX for p in ("labour", "inflation")} and
         set(observed.get("growth_quarterly_gdp_web", {})) == set(FX),
         "G8 source dimensions absent")
    need(legacy.get("asOf") and
         date.fromisoformat(legacy["asOf"]) <= cutoff and
         set(legacy.get("macro", {})) == set(FX), "legacy D source scope")
    need(setup.get("schema") == "GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1" and
         setup.get("pair_count") == 28 and
         setup.get("macro_baseline_asof") == legacy["asOf"] and
         date.fromisoformat(setup["price_asof"]) <= cutoff and
         setup.get("price_audit", {}).get("status") == "PASS",
         "28 pair observational overlay must remain source-dated")

    q3_growth = observed_q3_updates(as_of)
    countries = {}
    for c in FX:
        upstream = heat["currencies"][c]
        dims = {}
        for pillar in ("labour", "inflation"):
            h = upstream[pillar]
            research = observed["inflation_labour"][c + "." + pillar]
            need(research.get("currency") == c and
                 research.get("pillar") == pillar and
                 research.get("eligible_for_macro_score") is False and
                 research.get("eligible_for_historical_backtest") is False and
                 research.get("source_observation_is_current_revised_history_not_historic_pit") is True,
                 c + "." + pillar + " invalid observed source identity")
            period = period_month(h["as_of"], c + "." + pillar)
            # Quarterly publisher periods use 2026Q3 whereas the native
            # thermometer retains the quarter-end month 2026-09.
            expected_period = (
                f"{period.year}Q{(period.month-1)//3+1}"
                if research.get("frequency") == "Q" else period.strftime("%Y-%m")
            )
            need(research.get("canonical_series_id") == h.get("series_id") and
                 research.get("observation_period") == expected_period,
                 c + "." + pillar + " observation period or series drift")
            need(period <= cutoff.replace(day=1), c + "." + pillar + " future observation")
            history = h.get("history")
            need(isinstance(history, list) and len(history) >= 4 and
                 all(type(v) in (int, float) and math.isfinite(v) for v in history[-4:]),
                 c + "." + pillar + " insufficient dated source history")
            current = number(h.get("latest_value"), c + "." + pillar)
            need(math.isclose(current, history[-1], abs_tol=1e-7, rel_tol=0) and
                 math.isclose(current, research["observation_value"], abs_tol=1e-7, rel_tol=0) and
                 all(h.get("validation", {}).get(k) is True for k in
                     ("source", "history", "latest", "transformation")),
                 c + "." + pillar + " source fingerprint or official value drift")
            diff = round(current - history[-4], 6)
            dims[pillar] = {
                "series_id": h["series_id"],
                "observation_period": research["observation_period"],
                "observation_value": current,
                "change_over_three_observation_intervals_pp": diff,
                "observation_intervals_not_fixed_calendar_months": True,
                "change_direction": movement(diff),
                "reported_unit": "PERCENT_OR_PERCENTAGE_POINTS",
                "normalization_not_required_for_observed_value": True,
                "research_z_only_when_available": research.get("research_robust_z"),
                "research_z_was_not_imputed": research.get("research_robust_z") is None,
                "observed_history_revised_not_historic_PIT": True,
                "observation_period_is_not_release_instant": True,
                "source": h.get("source"),
            }
        g = observed["growth_quarterly_gdp_web"][c]
        need(g.get("status") == "OFFICIAL_WEB_STATEMENT_RESEARCH_NOT_PIT_CERTIFIED" and
             g.get("quarter") == "2026Q2" and
             g.get("source_url", "").startswith("https://") and
             g.get("growth_score") is None and
             g.get("historical_pit_training_vintages_certified") is False,
             c + " GDP publisher web source does not authorize scoring")
        published = date.fromisoformat(g["published_on"])
        need(published <= cutoff and g["published_on"] <= as_of,
             c + " publisher event from the future")
        qoq = number(g.get("descriptive_qoq_nonannualized_pct"), c + " GDP QoQ")
        need(-50 < qoq < 50, c + " GDP normalisation failed")
        countries[c] = {
            "growth": {
                "reference_quarter": g["quarter"],
                "publisher_release_day": g["published_on"],
                "publisher_source": g["source_url"],
                "reported_value": number(g["reported_value"], c + " GDP publisher value"),
                "reported_unit": g["reported_unit"],
                "nonannualized_qoq_descriptive_pct": round(qoq, 6),
                "is_growth_strength_score": False,
                "national_definitions_are_not_fully_cross_country_equivalent": True,
                "later_revisions_not_identical_to_first_release": True,
            },
            "labour": dims["labour"],
            "inflation": dims["inflation"],
            "unemployment_falling": dims["labour"]["change_direction"] == "DOWN",
            "unemployment_rising": dims["labour"]["change_direction"] == "UP",
            "inflation_accelerating_yoy": dims["inflation"]["change_direction"] == "UP",
            "inflation_decelerating_yoy": dims["inflation"]["change_direction"] == "DOWN",
            "macro_score": None,
            "FX_strength": None,
            "country_relative_rank": None,
            "not_a_trade_or_policy_signal": True,
        }
        if c in q3_growth:
            # Preserve the Q2 issuer statement; show the later actual Q3
            # independently, never estimating GDP for the other G8 economies.
            previous = countries[c]["growth"]
            countries[c]["growth"] = {
                **q3_growth[c], "prior_documented_quarter": previous,
            }

    pairs = setup.get("pairs")
    need(isinstance(pairs, dict) and len(pairs) == 28, "exact 28 pair setup required")
    results = {}
    seen = set()
    for ticker, payload in sorted(pairs.items()):
        pair = payload.get("canonical_pair")
        need(isinstance(pair, str) and pair.replace("/", "") == ticker and
             pair.count("/") == 1, "canonical FX pair mapping drift")
        a, b = pair.split("/")
        need(a != b and a in FX and b in FX and
             frozenset((a, b)) not in seen, "duplicate/noncanonical G8 pair")
        seen.add(frozenset((a, b)))
        ld_a = countries[a]["labour"]["change_direction"]
        ld_b = countries[b]["labour"]["change_direction"]
        labour = ("BASE_UNEMPLOYMENT_FALLING_QUOTE_RISING"
                  if ld_a == "DOWN" and ld_b == "UP" else
                  "BASE_UNEMPLOYMENT_RISING_QUOTE_FALLING"
                  if ld_a == "UP" and ld_b == "DOWN" else
                  "NO_OPPOSITE_LABOUR_CHANGE")
        results[pair] = {
            "base": a, "quote": b,
            "growth": {k: countries[k]["growth"]["nonannualized_qoq_descriptive_pct"]
                       for k in (a, b)},
            "growth_periods": {k: countries[k]["growth"]["reference_quarter"]
                              for k in (a, b)},
            "labour_changes_pp": {k: countries[k]["labour"]["change_over_three_observation_intervals_pp"]
                                  for k in (a, b)},
            "labour_periods": {k: countries[k]["labour"]["observation_period"]
                              for k in (a, b)},
            "labour_change_contrast": labour,
            "inflation_yoy_changes_pp": {
                k: countries[k]["inflation"]["change_over_three_observation_intervals_pp"]
                for k in (a, b)},
            "inflation_periods": {k: countries[k]["inflation"]["observation_period"]
                                  for k in (a, b)},
            "growth_levels_not_comparable_as_relative_currency_strength": True,
            "inflation_change_does_not_imply_hawkish_policy": True,
            "labour_change_does_not_prove_FX_appreciation": True,
            "pair_trade_bias": None,
            "estimated_FX_expected_return": None,
            "recalculated_structural_thesis": False,
        }
    need(len(seen) == 28 and len(results) == 28, "28 G8 pairs not exhausted")
    result = {
        "schema": SCHEMA, "version": MODEL, "as_of": as_of,
        "economic_data_coverage": "8/8_G8_THREE_PILLARS",
        "canonical_D_macro_baseline_as_of": legacy["asOf"],
        "fx_price_as_of": setup["price_asof"],
        "country_evidence": countries, "pair_context": results,
        "summary": {
            "currencies": 8, "economic_dimensions": 24, "pairs": 28,
            "latest_observation_values_present": 24,
            "numeric_old_D_macro_scores_replaced": 0,
            "pair_trade_signals_generated": 0,
            "GDP_publishers_visible": 8,
            "GDP_later_quarter_official_releases": len(q3_growth),
        },
        "source_value_quality": "OBSERVED_REVISED_SERIES_AND_PUBLISHER_WEB_GDP",
        "point_in_time_historical_backtest_certified": False,
        "observation_day_is_not_release_day": True,
        "missing_robust_z_never_substituted_by_zero": True,
        "growth_country_definitions_not_strictly_identical": True,
        "no_extrapolation_of_future_GDP": True,
        "safe_to_republish_D": False,
        "safe_to_recompute_structural_pair_theses": False,
        "eligible_for_trading_or_forward_backtest": False,
        "writes_live_data": False,
        "status": "COMPLETE_CURRENT_ECONOMIC_OBSERVATION_8_G8_28_PAIRS_NOT_FX_SIGNAL",
    }
    result["receipt_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        .encode("utf-8")).hexdigest()
    return result


def run(*, as_of=None):
    as_of = as_of or datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
    return build(observed_run(as_of=as_of), load("MACRO_THERMOMETER_DATA"),
                 load("D"), load("PAIR_SETUP_OPERATIONAL_VIEW"), as_of=as_of)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--out", type=Path)
    a = parser.parse_args()
    if a.out:
        need(a.out.resolve().is_relative_to(Path("/tmp")),
             "research output must stay in /tmp")
    result = run(as_of=a.as_of)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(json.dumps({"status": result["status"], "summary": result["summary"],
                      "source_snapshot_sha256": result["receipt_sha256"],
                      "canonical_D_untouched": True}, sort_keys=True))


if __name__ == "__main__":
    main()
