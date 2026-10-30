#!/usr/bin/env python3
"""Preregistered descriptive handling for zero-MAD research economic sources.

NO numeric fallback z, FX score, or live Core change. This is a *separate*
quality descriptor, never a replacement for existing strict Macro V2. It uses
the same prior-only economic periods and registered transformation as the
existing observed bridge, with no interpolation or revised-history PIT claim.

Version: V2-ZERO-MAD-ORDINAL-QUALITY-V1 (registered 2026-10-30; the first
future observation cannot be earlier than 2026-11-02 Europe/Rome).
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import statistics
from zoneinfo import ZoneInfo

from validation.macro.v2_g8_observed_feature_bridge_v1 import (
    ROOT, FX, PILLARS, WINDOW, normalized_source, transformed_series,
    index_to_period, run as observed_run,
)

SCHEMA = "GMFQ_V2_ZERO_MAD_ORDINAL_QUALITY_RESEARCH_V1"
POLICY_ID = "V2-ZERO-MAD-ORDINAL-QUALITY-V1"
NOT_BEFORE_ROME = date(2026, 11, 2)
METHODOLOGY = "STRICT_PRIOR_24M_OR_12Q_ZERO_MAD_NO_NUMERIC_FALLBACK"
SOURCE = ROOT / "live_data/sections/MACRO_SERIES.json"
REGISTRY = ROOT / "validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json"


def require(condition, why):
    if not condition:
        raise ValueError("V2_ZERO_MAD_ORDINAL_REJECTED: " + why)


def source_quality(row, registered, feature):
    """Return one optional zero-MAD descriptor; fail if evidence is ambiguous."""
    require(feature.get("canonical_series_id") == registered.get("series_id")
            and feature.get("transformation") == registered.get("transformation")
            and feature.get("frequency") == registered.get("frequency"),
            "source/feature registry mismatch")
    if feature.get("status") != "NO_Z_ZERO_ROBUST_DISPERSION":
        return None
    require(feature.get("research_robust_z") is None and
            feature.get("eligible_for_macro_score") is False and
            feature.get("eligible_for_historical_backtest") is False,
            "zero MAD must not have a model score")
    frequency = registered.get("frequency")
    require(frequency in WINDOW, "unsupported frequency")
    expected_id = ((registered.get("historical_replay_evidence") or {})
                   .get("macro_series_id") or registered["series_id"] + "_history_value")
    require(row.get("id") == expected_id, "registered historical source mismatch")
    grouped, aliases = normalized_source(row, frequency)
    economic = transformed_series(grouped, registered["transformation"])
    newest = max(economic)
    n = WINDOW[frequency]
    require(feature.get("observation_period") == economic[newest][0],
            "source and registered latest economic period differ")
    required = list(range(newest-n, newest))
    require(all(idx in economic for idx in required),
            "incomplete prior economic history: ordinal count withheld")
    prior = [economic[idx][1] for idx in required]
    current = economic[newest][1]
    require(type(current) in (int, float) and math.isfinite(current)
            and all(type(x) in (int,float) and math.isfinite(x) for x in prior),
            "nonfinite observed economic value")
    med = statistics.median(prior)
    mad = statistics.median(abs(x-med) for x in prior)
    require(mad <= 1e-9, "source MAD is not zero under strict bridge tolerance")
    less = sum(v < current for v in prior)
    equal = sum(v == current for v in prior)
    above = current > max(prior)
    below = current < min(prior)
    direction = ("ABOVE_ALL_PRIOR" if above else
                 "BELOW_ALL_PRIOR" if below else
                 "WITHIN_OR_TIED_PRIOR_RANGE")
    return {
        "status": "UNDEFINED_STRICT_Z_ZERO_MAD_ORDINAL_CONTEXT_ONLY",
        "latest_observation_period": feature["observation_period"],
        "prior_first_economic_period": index_to_period(required[0], frequency),
        "prior_last_economic_period": index_to_period(required[-1], frequency),
        "number_of_prior_economic_periods": n,
        "current_observation": current,
        "prior_median": med,
        "strict_prior_MAD": mad,
        "current_minus_prior_median_original_units": round(current-med, 10),
        "ordinal_relation": direction,
        "less_than_current_prior_count": less,
        "equal_to_current_prior_count": equal,
        "midrank_percentile_of_prior": (less + 0.5*equal)/n,
        "prior_unique_observed_values": len(set(prior)),
        "date_precision_aliases_collapsed": aliases,
        "is_numeric_z_score": False,
        "numeric_replacement_z": None,
        "FX_or_policy_direction_derived": None,
        "estimator_sensitivity_is_not_approval": True,
        "not_a_historical_point_in_time_measurement": True,
        "eligible_for_domestic_activity_weighting": False,
        "eligible_for_forward_features": False,
    }


def build(observed, series, registry, *, today):
    require(isinstance(today, date), "need economic-day audit cutoff")
    require(observed.get("status") ==
            "OBSERVED_G8_RESEARCH_FEATURES_NOT_CERTIFIED_MACRO_MODEL",
            "observed input is not research-only")
    require(observed.get("safe_to_use_for_forward") is False and
            observed.get("safe_to_publish_new_D") is False,
            "unexpected promotion in observed source")
    features = observed.get("inflation_labour", {})
    expected = {f"{c}.{p}" for c in FX for p in PILLARS}
    require(set(features) == expected and
            set(registry.get("series", {})) == expected and
            set(series) >= set(FX), "G8 economic/registry keys incomplete")
    require(date.fromisoformat(observed["checked_as_of"]) <= today,
            "cannot inspect future economic research")
    output = {}
    for key in sorted(expected):
        ccy, pillar = key.split(".")
        feat = features[key]
        reg = registry["series"][key]
        rid = ((reg.get("historical_replay_evidence") or {})
               .get("macro_series_id") or reg["series_id"] + "_history_value")
        rows = [r for r in series[ccy]
                if isinstance(r, dict) and r.get("id") == rid]
        require(len(rows) == 1, "missing/duplicate historical source " + key)
        if feat.get("status") != "NO_Z_ZERO_ROBUST_DISPERSION":
            continue
        item = source_quality(rows[0], reg, feat)
        require(item is not None, "unexplained missing source quality descriptor")
        output[key] = item
    result = {
        "schema": SCHEMA,
        "policy_id": POLICY_ID,
        "methodology": METHODOLOGY,
        "registration_day_rome": "2026-10-30",
        "earliest_possible_future_capture_day_rome": NOT_BEFORE_ROME.isoformat(),
        "as_of_observed_economic_bridge": observed["checked_as_of"],
        "status": "RESEARCH_QUALITY_ONLY_NO_MODEL_OR_FX_SCORE",
        "zero_mad_components": output,
        "zero_mad_component_count": len(output),
        "strict_numeric_z_imputation_count": 0,
        "existing_macro_v2_strict_z_unchanged": True,
        "changes_prior_frozen_snapshots": False,
        "can_generate_legacy_D": False,
        "can_write_forward_v2_journal": False,
        "can_feed_preregistered_H1": False,
        "allowed_to_create_trading_signal": False,
        "historical_PIT_validated": False,
        "writes_live_data": False,
    }
    result["evidence_fingerprint_sha256"] = hashlib.sha256(json.dumps(
        {"policy":POLICY_ID,"as_of":result["as_of_observed_economic_bridge"],
         "components": output}, sort_keys=True,
        separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return result


def run(*, as_of=None):
    today = datetime.now(ZoneInfo("Europe/Rome")).date()
    day = date.fromisoformat(as_of) if as_of else today
    require(day <= today, "future audit day")
    observed = observed_run(as_of=day.isoformat())
    series = json.loads(SOURCE.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return build(observed,series,registry,today=today)


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--receipt",type=Path,required=True)
    a=arg.parse_args()
    require(a.receipt.resolve().is_relative_to(Path("/tmp")),
            "receipts only in /tmp")
    r=run()
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.receipt.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n",
                         encoding="utf-8")
    print(json.dumps({"status":r["status"],"policy_id":r["policy_id"],
                      "zero_mad_components":list(r["zero_mad_components"]),
                      "future_capture_allowed_now":False,
                      "forward_v2_numeric_fallback_authorized":False},
                     sort_keys=True))


if __name__=="__main__":
    main()
