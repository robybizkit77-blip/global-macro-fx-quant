#!/usr/bin/env python3
"""Officially uncollected Oct-2025 US CPI/CPS versus strict 24-calendar-month z.

A missing calendar month is NOT a missing GitHub fetch and cannot be made into
a BLS release or a point-in-time panel. This module is documentary research:
no backfill, no imputation, no macro score, no live-data or journal mutation.

BLS authorities:
https://www.bls.gov/cps/methods/2025-federal-government-shutdown-impact-cps.htm
https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm
"""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from validation.macro.v2_g8_observed_feature_bridge_v1 import (
    ROOT, normalized_source, transformed_series, index_to_period, period,
)

SCHEMA = "GMFQ_MACRO_V2_US_SHUTDOWN_CALENDAR_GAP_V1"
MONTH = "2025-10"
SLOTS = {
    "USD.inflation": {
        "registered_series": "CPIAUCSL",
        "macro_series": "US_CPIAUCSL_history_value",
        "transformation": "yoy_pct_from_index",
        "official_source": "https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm",
        "reason": "OCT_2025_ALL_ITEMS_CPI_NEVER_PUBLISHED",
    },
    "USD.labour": {
        "registered_series": "UNRATE",
        "macro_series": "US_UNRATE_history_value",
        "transformation": "level",
        "official_source": "https://www.bls.gov/cps/methods/2025-federal-government-shutdown-impact-cps.htm",
        "reason": "OCT_2025_HOUSEHOLD_SURVEY_NOT_COLLECTED_OR_RETROACTIVELY_COLLECTED",
    },
}


def require(ok, msg):
    if not ok:
        raise ValueError("MACRO_V2_US_SHUTDOWN_GAP_REJECTED: " + msg)


def audit(series, registry, observed, *, checked_as_of):
    require(isinstance(checked_as_of, str)
            and date.fromisoformat(checked_as_of).isoformat() == checked_as_of,
            "audit date must be actual canonical YYYY-MM-DD")
    require(observed.get("status") ==
            "OBSERVED_G8_RESEARCH_FEATURES_NOT_CERTIFIED_MACRO_MODEL"
            and observed.get("checked_as_of") == checked_as_of
            and observed.get("safe_to_publish_new_D") is False,
            "contemporaneous research bridge required")
    reg = registry.get("series", {})
    rows = series.get("USD", [])
    features = observed.get("inflation_labour", {})
    month_idx, _ = period(MONTH, "M")
    output = {}
    for key, contract in SLOTS.items():
        registered = reg.get(key, {})
        feature = features.get(key, {})
        require(registered.get("series_id") == contract["registered_series"]
                and registered.get("frequency") == "M"
                and registered.get("transformation") == contract["transformation"]
                and registered.get("historical_replay_evidence", {}).get("macro_series_id") ==
                contract["macro_series"],
                key + " registered source definition drift")
        matches = [r for r in rows if r.get("id") == contract["macro_series"]]
        require(len(matches) == 1, key + " missing or duplicated macro history")
        raw, aliases = normalized_source(matches[0], "M")
        # This is a documented nonrelease. A fabricated Oct-2025 CPI/CPS
        # observation must fail closed, not get treated as a recovered source.
        require(month_idx not in raw,
                key + " fabricated original observation for never-collected month")
        transformed = transformed_series(raw, contract["transformation"])
        newest = max(transformed)
        prior = range(newest-24, newest)
        missing = [index_to_period(i,"M") for i in prior if i not in transformed]
        require(feature.get("canonical_series_id") == registered["series_id"]
                and feature.get("macro_series_id") == contract["macro_series"]
                and feature.get("observation_period") == index_to_period(newest,"M")
                and feature.get("missing_prior_periods") == missing,
                key + " observed feature/calendar reconstruction disagrees")
        if missing:
            require(feature.get("research_robust_z") is None and
                    feature.get("status") == "NO_Z_MISSING_PRIOR_ECONOMIC_PERIODS",
                    key + " incomplete 24-month window incorrectly scored")
        output[key] = {
            "registered_series": contract["registered_series"],
            "input_history_id": contract["macro_series"],
            "economic_period_last_available": index_to_period(newest,"M"),
            "reported_observation_count": len(raw),
            "date_precision_aliases_removed": aliases,
            "never_published_reference_period": MONTH,
            "oct_2025_observation_exists": False,
            "official_BLS_evidence": contract["official_source"],
            "nonrelease_reason": contract["reason"],
            "prior_24_calendar_months": [index_to_period(i,"M") for i in prior],
            "prior_24_missing_periods": missing,
            "calendar_consecutive_24_observations": len(missing) == 0,
            "strict_current_research_z_is_null": feature.get("research_robust_z") is None,
            "current_research_z_not_historic_first_release_PIT": True,
            "no_BLS_shutdown_month_imputation": True,
        }
    return {
        "schema": SCHEMA,
        "checked_as_of": checked_as_of,
        "slots": output,
        "summary": {
            "officially_uncollected_US_2025_10_series": len(output),
            "strict_24_calendar_missing_slots": sorted(
                k for k,x in output.items() if not x["calendar_consecutive_24_observations"]),
            "first_web_release_count_is_not_same_as_consecutive_month_count": True,
            "model_z_scores_recovered": 0,
        },
        "source_evidence_is_official_nonrelease_not_reconstructed_original_bytes": True,
        "no_release_imputation": True,
        "no_historical_PIT_certification": True,
        "no_change_to_MacroV2_formula_or_28_pairs": True,
        "safe_to_publish_D": False,
        "writes_live_data": False,
    }


def run(*, as_of):
    from validation.macro.v2_g8_observed_feature_bridge_v1 import run as bridge_run
    source=json.loads((ROOT/"live_data/sections/MACRO_SERIES.json").read_text())
    reg=json.loads((ROOT/"validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json").read_text())
    return audit(source,reg,bridge_run(as_of=as_of),checked_as_of=as_of)


def main():
    import argparse
    from datetime import datetime
    from zoneinfo import ZoneInfo
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    require(args.out.resolve().is_relative_to(Path("/tmp")),
            "research evidence receipt must remain in /tmp")
    day=datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
    result=run(as_of=day)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"schema":SCHEMA,"summary":result["summary"],
                      "safe_to_publish_D":False},sort_keys=True))


if __name__=="__main__":
    main()
