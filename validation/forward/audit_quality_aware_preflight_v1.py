#!/usr/bin/env python3
"""Read-only next-session Quality-Aware V2 source preflight, never a freeze.

No future clock overrides or fabricated ECB T0. This checks CURRENT registered
economic/market inputs separately from availability of a *new* ECB fixing.
Real freezes remain restricted to the already-existing weekday after-19:00
capture flow and begin no earlier than 2026-11-02 Europe/Rome.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, date
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.forward.capture_v2_quality_aware_prospective_v1 import (
    ROOT, SOURCE_PATHS, SCHEMA as FREEZE_SCHEMA,
)
from validation.forward.observe_official_ecb_reference_outcomes_v1 import source_map
from validation.forward.v2_quality_market_context_v1 import (
    build as market_build, validate as market_validate,
)
from validation.macro.v2_g8_observed_feature_bridge_v1 import run as economic_run
from validation.macro.v2_us_shutdown_2025_calendar_gap_v1 import (
    audit as us_shutdown_audit, SCHEMA as US_SHUTDOWN_SCHEMA,
)
from validation.macro.v2_zero_mad_ordinal_quality_v1 import (
    build as ordinal_build, SOURCE as SERIES, REGISTRY,
    POLICY_ID, NOT_BEFORE_ROME,
)

SCHEMA = "GMFQ_V2_QUALITY_AWARE_NEXT_SESSION_SOURCE_PREFLIGHT_V1"
G8 = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")


def require(ok, msg):
    if not ok:
        raise ValueError("QUALITY_AWARE_PREFLIGHT_REJECTED: " + msg)


def inspect(*, now, observed, ordinal, market, fx, pairs, us_shutdown):
    """Verify own-source contracts; never gate a real freeze or write T0."""
    require(isinstance(now, datetime) and now.tzinfo is not None
            and now.utcoffset() is not None, "timezone-aware real instant")
    day = now.astimezone(ZoneInfo("Europe/Rome")).date().isoformat()
    require(observed.get("checked_as_of") == day
            and observed.get("status") ==
              "OBSERVED_G8_RESEARCH_FEATURES_NOT_CERTIFIED_MACRO_MODEL"
            and observed.get("safe_to_publish_new_D") is False
            and observed.get("safe_to_use_for_forward") is False
            and observed.get("writes_live_data") is False,
            "observed macro bridge promoted, stale, or mutated")
    require(ordinal.get("policy_id") == POLICY_ID
            and ordinal.get("as_of_observed_economic_bridge") == day
            and ordinal.get("strict_numeric_z_imputation_count") == 0
            and ordinal.get("can_feed_preregistered_H1") is False
            and ordinal.get("can_write_forward_v2_journal") is False,
            "zero-MAD ordinal source has been promoted to model input")
    require(market.get("as_of_rome") == day
            and market.get("summary", {}).get("eight_economies") == 8
            and market.get("summary", {}).get("28_pairs") == 28
            and market.get("summary", {}).get("FX_scores") == 0
            and market.get("eligible_for_H1_or_live_Core") is False,
            "8/28 source-graded market context not valid")
    require(pairs.get("pair_count") == 28
            and len(pairs.get("pairs", {})) == 28, "pair universe drift")
    dimensions = observed.get("inflation_labour", {})
    growth = observed.get("growth_quarterly_gdp_web", {})
    first_growth = observed.get("growth_quarterly_gdp_initial_web_research_features", {})
    require(set(dimensions) == {c + "." + p for c in G8
                               for p in ("labour", "inflation")}
            and set(growth) == set(first_growth) == set(G8),
            "24 observed dimensions not present")
    bad = sorted(k for k, r in dimensions.items()
                 if r.get("research_robust_z") is None)
    ordinal_keys = sorted(ordinal.get("zero_mad_components", {}))
    require(ordinal_keys == sorted(
            k for k, r in dimensions.items()
            if r.get("status") == "NO_Z_ZERO_ROBUST_DISPERSION"),
            "zero-MAD descriptor/source mismatch")
    for k in ordinal_keys:
        desc = ordinal["zero_mad_components"][k]
        require(dimensions[k].get("research_robust_z") is None
                and dimensions[k].get("status") == "NO_Z_ZERO_ROBUST_DISPERSION",
                k + " missing strict-z mask contradiction")
        require(desc.get("numeric_replacement_z") is None
                and desc.get("eligible_for_domestic_activity_weighting") is False
                and desc.get("eligible_for_forward_features") is False,
                k + " invalid z-score substitution")
    require(us_shutdown.get("schema") == US_SHUTDOWN_SCHEMA and
            us_shutdown.get("checked_as_of") == day and
            us_shutdown.get("no_release_imputation") is True and
            us_shutdown.get("no_historical_PIT_certification") is True and
            us_shutdown.get("safe_to_publish_D") is False and
            us_shutdown.get("writes_live_data") is False and
            set(us_shutdown.get("slots", {})) ==
              {"USD.inflation", "USD.labour"},
            "US missing BLS reference months not reconciled")
    for key in ("USD.inflation", "USD.labour"):
        detail = us_shutdown["slots"][key]
        require(detail.get("oct_2025_observation_exists") is False and
                detail.get("never_published_reference_period") == "2025-10" and
                detail.get("prior_24_missing_periods") ==
                    dimensions[key].get("missing_prior_periods") and
                detail.get("strict_current_research_z_is_null") is
                    (dimensions[key].get("research_robust_z") is None),
                key + " US calendar history/feature nonrelease contract")
    records = source_map(fx)
    latest = fx.get("last_as_of")
    same_day = any(d.isoformat() == day for d in records)
    require(latest == max(records).isoformat(), "ECB last as-of not canonical")
    after_cutoff = now.astimezone(ZoneInfo("Europe/Rome")).hour >= 19
    first_day = date.fromisoformat(day) >= NOT_BEFORE_ROME
    weekday = date.fromisoformat(day).weekday() < 5
    # A green source preflight is NEVER permission to freeze retrospectively.
    status = ("NOT_BEFORE_REGISTERED_FIRST_REAL_CAPTURE"
              if not first_day else
              "WEEKEND_NO_ECB_FREEZE" if not weekday else
              "AWAITING_TRUE_AFTER_19_ROME_CUTOFF" if not after_cutoff else
              "AWAITING_OFFICIAL_SAME_DAY_ECB_T0" if not same_day else
              "ECONOMIC_MARKET_SOURCE_SHAPES_PREVALIDATED_ONLY")
    return {
        "schema": SCHEMA, "status": status,
        "checked_at_utc": now.astimezone(timezone.utc).isoformat(),
        "local_date_rome": day, "first_capture_allowed_day": NOT_BEFORE_ROME.isoformat(),
        "economic_research_dimensions": 24,
        "source_quality_graded_market_currencies": 8,
        "market_context_pairs": 28,
        "current_strict_z_missing_slots": bad,
        "ordinal_context_only_slots": ordinal_keys,
        "current_USD_inflation_missing_Oct2025_source_PIT_not_repaired": (
            us_shutdown["slots"]["USD.inflation"]["oct_2025_observation_exists"] is False
        ),
        "current_USD_labour_missing_Oct2025_CPS_PIT_not_repaired": (
            us_shutdown["slots"]["USD.labour"]["oct_2025_observation_exists"] is False
        ),
        "US_oct2025_unpublished_source_calendar_gap": us_shutdown["summary"],
        "current_CHF_labour_first_SNB_precision_PIT_not_repaired": True,
        "current_EUR_labour_zero_MAD_never_filled_with_fake_z": (
            "EUR.labour" not in ordinal_keys or "EUR.labour" in bad
        ),
        "observed_ecb_last_reference_day": latest,
        "official_same_day_ECB_T0_observed": same_day,
        "weekday_eligible": weekday,
        "after_19_Rome_now": after_cutoff,
        "model_candidate_evaluated_or_updated": False,
        "current_D_or_28_pair_score_changed": False,
        "future_snapshot_captured_now": False,
        "historical_PIT_validated": False,
        "forecast_FX_accuracy_claimed": False,
        "safe_to_capture_without_real_time_admission": False,
    }


def run(*, now=None):
    now = datetime.now(timezone.utc) if now is None else now
    day = now.astimezone(ZoneInfo("Europe/Rome")).date().isoformat()
    load = lambda key: json.loads((ROOT / SOURCE_PATHS[key]).read_text(encoding="utf-8"))
    observed = economic_run(as_of=day)
    economic_series=json.loads(SERIES.read_text(encoding="utf-8"))
    economic_registry=json.loads(REGISTRY.read_text(encoding="utf-8"))
    ordinal = ordinal_build(
        observed,economic_series,economic_registry,
        today=date.fromisoformat(day),
    )
    shutdown = us_shutdown_audit(
        economic_series,economic_registry,observed,checked_as_of=day)
    pairs = load("pair_setup")
    market = market_build(day, load("rates"), load("ois"), load("banks"),
                          load("nzd_proxy"), pairs)
    market_validate(market)
    return inspect(now=now, observed=observed, ordinal=ordinal,
                   market=market, fx=load("ecb"), pairs=pairs, us_shutdown=shutdown)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(args.out.resolve().is_relative_to(Path("/tmp")),
            "receipt must remain under /tmp, no live data writes")
    result = run()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"status": result["status"],
                      "economic_research_dimensions": result["economic_research_dimensions"],
                      "strict_z_missing_slots": result["current_strict_z_missing_slots"],
                      "zero_MAD_context_only_slots": result["ordinal_context_only_slots"],
                      "US_2025_10_source_gaps":result["US_oct2025_unpublished_source_calendar_gap"]["strict_24_calendar_missing_slots"],
                      "ecb_T0_today": result["official_same_day_ECB_T0_observed"],
                      "snapshot_written": False}, sort_keys=True))


if __name__ == "__main__":
    main()
