#!/usr/bin/env python3
"""US October 2025 structural-release gap: explicit research-only normalization.

BLS never collected October 2025 CPI all-items index or CPS unemployment,
so an invented/forward-filled observation would not be official. Compute
an OPTIONAL explicitly estimated cross-gap feature using 24 PRIOR OBSERVED
months in a fixed 25-calendar-month window (one missing month), retaining
the original strict 24-consecutive-month z as null. No backward look-ahead
training claim, no PIT validation, no Core / Beta / FX-pair promotion.

The gap attestation is pinned to BLS government pages, not inferred from the
shape of a vendor time series. Any other absent period fails closed.
"""
from __future__ import annotations

import math
import statistics
from datetime import date

from validation.macro.v2_g8_observed_feature_bridge_v1 import (
    finite, index_to_period, normalized_source, period, require, transformed_series
)

SCHEMA = "GMFQ_MACRO_V2_BLS_OCT2025_STRUCTURAL_GAP_RESEARCH_V1"
BLS_EVIDENCE = {
    "inflation": {
        "canonical_id": "CPIAUCSL",
        "source_id": "US_CPIAUCSL_history_value",
        "missing_period": "2025-10",
        "reason": "NO_OCT2025_ALL_ITEMS_CPI_ESTIMATE_BLS_SHUTDOWN",
        "primary_reference": "https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm",
        "secondary_reference": "https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm",
    },
    "labour": {
        "canonical_id": "UNRATE",
        "source_id": "US_UNRATE_history_value",
        "missing_period": "2025-10",
        "reason": "NO_OCT2025_CPS_HOUSEHOLD_SURVEY_BLS_SHUTDOWN",
        "primary_reference": "https://www.bls.gov/cps/methods/2025-federal-government-shutdown-impact-cps.htm",
        "secondary_reference": "https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm",
    },
}
TRAIN_PRIOR_ACTUAL_N = 24
MAX_PRIOR_CALENDAR_MONTHS = 25
CLIP_Z = 3.0


def shadow_gap_estimate(dimension, registered, source_row, heat, strict, as_of):
    """Return optional *estimated research z*; never patch missing source."""
    require(dimension in BLS_EVIDENCE, "only attested US CPI/UNRATE structural gap")
    cfg = BLS_EVIDENCE[dimension]
    require(registered.get("series_id") == cfg["canonical_id"]
            and registered.get("frequency") == "M"
            and source_row.get("id") == cfg["source_id"]
            and (heat.get("series_id"), heat.get("frequency")) ==
            (cfg["canonical_id"], "M"), "exact registered US source identity required")
    require(strict.get("currency") == "USD" and strict.get("pillar") == dimension
            and strict.get("canonical_series_id") == cfg["canonical_id"]
            and strict.get("status") == "NO_Z_MISSING_PRIOR_ECONOMIC_PERIODS"
            and strict.get("research_robust_z") is None,
            "strict-source result must remain blocked for absent calendar month")
    require(isinstance(as_of, date), "explicit audit as-of required")
    samples, alias_count = normalized_source(source_row, "M")
    observed = transformed_series(samples, registered["transformation"])
    newest = max(observed)
    newest_period = index_to_period(newest, "M")
    require(newest_period == strict["observation_period"], "latest source/strict mismatch")
    require(index_to_period(newest, "M") <= f"{as_of.year:04d}-{as_of.month:02d}",
            "future economic observation")
    missing_raw = cfg["missing_period"]
    gap_idx, _ = period(missing_raw, "M")
    # Shutdown absence MUST be real in raw series too, not synthetic zero or fill.
    require(gap_idx not in samples, "BLS shutdown month was fabricated in raw history")
    training_months = list(range(newest - MAX_PRIOR_CALENDAR_MONTHS, newest))
    missing = [i for i in training_months if i not in observed]
    # Narrow one-gap policy. Unknown absent months/YoY transforms are not covered
    # by the shutdown attestation and never become estimates.
    candidate = {
        "schema": SCHEMA,
        "status": "NO_GAP_ESTIMATE_UNLESS_EXACT_BLS_MISSING_MONTH",
        "dimension": dimension, "canonical_source_id": cfg["canonical_id"],
        "actual_current_observation_period": newest_period,
        "strict_consecutive_research_z": None,
        "estimated_research_robust_z": None,
        "estimated_research_robust_z_unclipped": None,
        "training_observed_months_required": TRAIN_PRIOR_ACTUAL_N,
        "training_calendar_months": MAX_PRIOR_CALENDAR_MONTHS,
        "missing_calendar_periods": [index_to_period(i, "M") for i in missing],
        "structurally_missing_economic_month": missing_raw,
        "missing_cause": cfg["reason"],
        "official_evidence_url": cfg["primary_reference"],
        "second_official_evidence_url": cfg["secondary_reference"],
        "original_missing_value_imputed": False,
        "source_history_modified": False,
        "quality": "RESEARCH_ESTIMATE_REVISED_VALUES_NO_HISTORICAL_PIT",
        "allow_macro_score": False, "allow_pair_ranking": False,
        "allow_beta": False, "allow_forward": False,
    }
    if missing != [gap_idx] or newest - 1 not in observed or newest - 2 not in observed:
        return candidate
    train = [observed[i][1] for i in training_months if i in observed]
    require(len(train) == TRAIN_PRIOR_ACTUAL_N, "one-gap training cardinality")
    median = statistics.median(train)
    mad = statistics.median(abs(x - median) for x in train)
    if mad <= 1e-9:
        candidate["status"] = "NO_GAP_ESTIMATE_ZERO_ROBUST_DISPERSION"
        return candidate
    val = observed[newest][1]
    require(finite(val) and math.isclose(val, strict["observation_value"],
                                        rel_tol=0, abs_tol=1e-7),
            "strict and gap-estimation current values differ")
    z = (val - median) / (1.4826 * mad)
    require(math.isfinite(z), "nonfinite robust research z")
    candidate.update({
        "status": "BLS_SHUTDOWN_GAP_AWARE_RESEARCH_ESTIMATE_NOT_PIT",
        "estimated_research_robust_z": max(-CLIP_Z, min(CLIP_Z, z)),
        "estimated_research_robust_z_unclipped": z,
        "training_first_observed_period": index_to_period(training_months[0], "M"),
        "training_last_observed_period": index_to_period(training_months[-1], "M"),
        "training_observed_months_used": TRAIN_PRIOR_ACTUAL_N,
        "training_median": median, "training_mad": mad,
        "current_value": val, "source_alias_count": alias_count,
        "observed_only_no_interpolation": True,
        "no_future_or_current_training_observations": True,
        "not_equivalent_to_strict_24_consecutive_month_normalization": True,
    })
    return candidate
