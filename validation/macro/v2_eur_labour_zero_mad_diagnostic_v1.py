#!/usr/bin/env python3
"""Read-only EUR unemployment zero-MAD diagnostic: no V2 model change.

A published rounded level can be above every prior observation even when
the registered 24-month MAD scale is zero. This explains the blocked feature;
the alternative scales below are DESCRIPTIVE SENSITIVITY, not imputation,
an authorized research z, PIT backtest or an FX signal.
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
    ROOT, normalized_source, transformed_series, period
)

SCHEMA = "GMFQ_EUR_LABOUR_ZERO_MAD_DIAGNOSTIC_V1"
SOURCE = ROOT / "live_data/sections/MACRO_SERIES.json"
REGISTRY = ROOT / "validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json"
SLOT = "EUR.labour"
EXPECTED_ID = "EA_UNEMP"
PRIOR = 24


def need(condition, description):
    if not condition:
        raise ValueError("EUR_ZERO_MAD_DIAGNOSTIC_REJECTED: " + description)


def percentile_type7(sorted_values, p):
    x = (len(sorted_values) - 1) * p
    a = math.floor(x)
    w = x - a
    return sorted_values[a] * (1 - w) + sorted_values[min(a + 1, len(sorted_values)-1)] * w


def assess(row, registered, *, as_of):
    """Measure available revised series; require fixed 24 economic months."""
    need(isinstance(as_of, date), "explicit observation cutoff required")
    need(registered["series_id"] == EXPECTED_ID
         and registered["transformation"] == "level"
         and registered["frequency"] == "M",
         "wrong series definition; do not compare alternative labour measures")
    rid = (registered.get("historical_replay_evidence") or {}).get(
        "macro_series_id", "EA_UNEMP_history_value")
    need(row.get("id") == rid, "registered source identity mismatch")
    grouped, aliases = normalized_source(row, "M")
    data = transformed_series(grouped, "level")
    newest = max(data)
    last_period = data[newest][0]
    cutoff_idx, _ = period(as_of.strftime("%Y-%m"), "M")
    need(newest <= cutoff_idx, "future economic observation")
    prior_idx = range(newest - PRIOR, newest)
    missing = [i for i in prior_idx if i not in data]
    need(not missing, "missing prior economic periods; no partial training window")
    history = [data[i][1] for i in prior_idx]
    current = data[newest][1]
    need(all(math.isfinite(x) for x in history + [current]), "nonfinite observation")
    order = sorted(history)
    median = statistics.median(order)
    mad = statistics.median([abs(v - median) for v in order])
    std = statistics.stdev(history)
    q25 = percentile_type7(order, .25)
    q75 = percentile_type7(order, .75)
    iqr = q75 - q25
    unique = sorted(set(history))
    distribution = [{"value": n, "count": history.count(n)} for n in unique]
    if mad == 0:
        status = "ROBUST_Z_UNDEFINED_ZERO_MAD"
    else:
        status = "ROBUST_Z_DEFINED_NO_SPECIAL_HANDLING"
    return {
        "schema": SCHEMA,
        "status": status,
        "registered_slot": SLOT,
        "series_id": EXPECTED_ID,
        "current_economic_period": last_period,
        "current_value_pct": current,
        "prior_economic_periods": PRIOR,
        "prior_first_period": data[newest - PRIOR][0],
        "prior_last_period": data[newest - 1][0],
        "source_date_precision_aliases_collapsed": aliases,
        "prior_distribution": distribution,
        "prior_median_pct": median,
        "prior_mad_pct": mad,
        "prior_sample_std_pct": std,
        "prior_iqr_pct": iqr,
        "current_vs_prior_max": (
            "ABOVE_ALL_PRIOR_OBSERVATIONS" if current > max(history) else
            "BELOW_ALL_PRIOR_OBSERVATIONS" if current < min(history) else
            "WITHIN_OR_EQUAL_PRIOR_RANGE"
        ),
        "current_percentile_midrank_prior": (
            sum(v < current for v in history)
            + 0.5 * sum(v == current for v in history)
        ) / PRIOR,
        # Algebraic stress tests only: neither substitutes for the
        # preregistered median/MAD research z.
        "not_approved_std_scale_z_sensitivity": (
            (current - median) / std if std > 0 else None
        ),
        "not_approved_iqr_scale_z_sensitivity": (
            (current - median) / (iqr / 1.349) if iqr > 0 else None
        ),
        "strict_macro_v2_normalizer_remains_unmodified": True,
        "authorized_fallback_method": None,
        "no_economic_missing_value_filled": True,
        "not_PIT_or_FX_predictive_validation": True,
        "no_trade_signal_or_position": True,
        "safe_to_use_as_forward_v2_numeric_feature": False,
        "writes_live_data": False,
        "writes_frozen_forward_journals": False,
    }


def run(*, as_of=None):
    today = datetime.now(ZoneInfo("Europe/Rome")).date()
    day = date.fromisoformat(as_of) if as_of else today
    need(day <= today, "future requested research as-of")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    matches = [x for x in source["EUR"] if x.get("id") == "EA_UNEMP_history_value"]
    need(len(matches) == 1, "missing/duplicated official historical source")
    result = assess(matches[0], registry["series"][SLOT], as_of=day)
    result["input_sha256"] = hashlib.sha256(json.dumps(
        {"row": matches[0], "registry": registry["series"][SLOT]},
        sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    need(args.receipt.resolve().is_relative_to(Path("/tmp")),
         "read-only research receipt must remain under /tmp")
    report = run()
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
