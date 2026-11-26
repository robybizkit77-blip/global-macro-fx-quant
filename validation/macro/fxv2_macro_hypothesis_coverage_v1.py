#!/usr/bin/env python3
"""FXV2 macro hypothesis preregistration: descriptive coverage, NEVER scoring.

Reads the already-published Macro V1 candidate and measures which synchronized
features could enter a future prospective experiment. No FX predictions, PIT
claims, fitted weights, trade signals, or writes to the operational Core.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "site/fx-quant-v2/macro-baseline-candidate-v1.json"
SCHEMA = "GMFQ_FXV2_MACRO_HYPOTHESIS_COVERAGE_RESEARCH_V1"
SOURCE_SCHEMA = "GMFQ_FXV2_MACRO_CANDIDATE_8X3_DESCRIPTIVE_V1"
CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"}
AXES = ("growth_acceleration_pp", "unemployment_change_pp", "inflation_change_pp")
EXPERIMENTS = (
    ("H0_LABOUR_CHANGE", ("unemployment_change_pp",), False),
    ("H1_ACTIVITY_CHANGE", ("growth_acceleration_pp", "unemployment_change_pp"), False),
    ("H2_ACTIVITY_INFLATION_CONTEXT", AXES, False),
    ("H3_MACRO_OIS6M_INTERACTION", AXES, True),
)

def require(condition: bool, explanation: str) -> None:
    if not condition:
        raise ValueError("FXV2_MACRO_HYPOTHESES_REJECTED: " + explanation)

def finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)

def inspect(source: dict) -> dict:
    require(isinstance(source, dict), "source must be object")
    require(source.get("schema") == SOURCE_SCHEMA, "wrong source schema")
    require(source.get("eligible_for_live_fx_signals") is False
            and source.get("eligible_for_backtests") is False
            and source.get("eligible_for_automatic_core_rebase") is False
            and source.get("canonical_fx_core_untouched") is True,
            "upstream no-FX-permissions contract changed")
    require(source.get("published_source_lineage") == "MACRO_V3_OBSERVED_REVISED_NOT_PIT",
            "expected revised not-PIT research lineage")
    require(source.get("summary", {}).get("currencies") == 8
            and source["summary"].get("features") == 24
            and source["summary"].get("pairs") == 28
            and source["summary"].get("trading_signals_generated") == 0
            and source["summary"].get("estimated_macro_scores") == 0,
            "source totals or no-signal restrictions changed")
    as_of = source.get("as_of_research")
    require(type(as_of) is str and date.fromisoformat(as_of).isoformat() == as_of,
            "invalid source date")
    features = source.get("features")
    pairs = source.get("pairs")
    require(isinstance(features, dict) and set(features) == CURRENCIES,
            "8 currencies required")
    require(isinstance(pairs, dict) and len(pairs) == 28,
            "28 pairs required")
    for ccy, row in features.items():
        require(isinstance(row, dict) and
                set(row) == {"growth_qoq_pct", "inflation_change_pp",
                             "unemployment_change_pp"},
                ccy + " feature schema")
        for dimension, entry in row.items():
            require(isinstance(entry, dict) and finite(entry.get("value"))
                    and isinstance(entry.get("period"), str),
                    ccy + " non-numeric or undated " + dimension)
        accel = row["growth_qoq_pct"].get("gdp_acceleration_pp")
        require(accel is None or finite(accel), ccy + " invalid GDP acceleration")

    pair_axes = {}
    for name, entry in pairs.items():
        require(isinstance(entry, dict), name + " pair not object")
        base, quote = entry.get("base"), entry.get("quote")
        require(base in CURRENCIES and quote in CURRENCIES and base != quote
                and name == base + "/" + quote, name + " pair identity")
        require(entry.get("macro_fx_signal") is None
                and entry.get("expected_return") is None
                and entry.get("relative_strength_score") is None
                and entry.get("eligible_for_core") is False,
                name + " operational signal contamination")
        contrasts = entry.get("contrasts")
        require(isinstance(contrasts, dict) and set(contrasts) == set(AXES),
                name + " contrasts missing")
        available = {}
        for axis in AXES:
            contrast = contrasts[axis]
            value = contrast.get("delta_base_minus_quote_pp")
            if axis == "growth_acceleration_pp":
                left = features[base]["growth_qoq_pct"]
                right = features[quote]["growth_qoq_pct"]
                expected_available = (
                    left["gdp_acceleration_pp"] is not None
                    and right["gdp_acceleration_pp"] is not None
                    and left["period"] == right["period"])
                flag = contrast.get("same_quarter_and_historical_depth")
                expected = (round(left["gdp_acceleration_pp"] -
                                  right["gdp_acceleration_pp"], 6)
                            if expected_available else None)
            else:
                left = features[base][axis]
                right = features[quote][axis]
                expected_available = (left["period"] == right["period"]
                    and left["period_frequency"] == right["period_frequency"])
                flag = contrast.get("same_period")
                expected = (round(left["value"] - right["value"], 6)
                            if expected_available else None)
            require(type(flag) is bool and flag == expected_available,
                    name + " " + axis + " alignment flag mismatch")
            require((value is None and expected is None)
                    or (finite(value) and expected is not None
                        and abs(value - expected) <= 1e-6),
                    name + " " + axis + " mismatch or invented delta")
            available[axis] = expected_available
        pair_axes[name] = available

    experiments = {}
    for key, required_axes, needs_policy in EXPERIMENTS:
        admitted = []
        blocked = {}
        for name, availability in pair_axes.items():
            missing = [a for a in required_axes if not availability[a]]
            if needs_policy:
                # No historical frozen OIS repricing exists in this source:
                # a current-level estimate is NOT a policy surprise.
                missing.append("FROZEN_COMPARABLE_OIS6M_REPRICING")
            if missing:
                blocked[name] = missing
            else:
                admitted.append(name)
        experiments[key] = {
            "feature_requirements": list(required_axes),
            "requires_frozen_ois6m_policy_repricing": needs_policy,
            "descriptive_coverage_pairs": len(admitted),
            "descriptively_comparable_pairs": sorted(admitted),
            "blocked_pairs": blocked,
            "eligible_for_pit_estimation": False,
            "eligible_for_fx_forecast_test": False,
            "macro_score": None,
            "fx_forecast": None,
            "out_of_sample_skill": None,
        }
    checksum = hashlib.sha256(
        json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema": SCHEMA,
        "source_as_of": as_of,
        "source_sha256": checksum,
        "protocol": "FROZEN_RESEARCH_DESIGN_NO_TRADE_OR_FX_RANKING",
        "experiments": experiments,
        "individual_axis_coverage": {
            axis: sum(availability[axis] for availability in pair_axes.values())
            for axis in AXES
        },
        "total_pairs": 28,
        "official_PIT_training_panel_certified": False,
        "actual_frozen_policy_repricing_in_source": False,
        "released_to_fx_core": False,
        "backtest_executed": False,
        "prediction_accuracy": None,
        "intended_evaluation": {
            "primary_horizon": "1W",
            "first_test": "PROSPECTIVE_ONLY_AFTER_REGISTRATION_AND_VALID_PIT_T0",
            "comparison": "SAME_COHORT_LAGGED_MOMENTUM_AND_2Y_H1",
            "aggregation": "FIRST_WITHIN_DATE_THEN_ACROSS_DATES_BLOCK_BOOTSTRAP",
            "lookahead_or_revised_2026_snapshot_allowed_as_historical_T0": False,
            "candidate_models_not_yet_tested": True,
        },
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    result = inspect(source)
    payload = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")

if __name__ == "__main__":
    main()
