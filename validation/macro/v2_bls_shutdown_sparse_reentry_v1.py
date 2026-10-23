#!/usr/bin/env python3
"""US BLS 2025 shutdown: missing observation != delayed publication.

This module is NOT the original monthly PIT/scoring pipeline. It produces
research-only sparse-event descriptive level snapshots while leaving original
contiguity, monthly acceleration and live-score fail-closed rules unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from validation.macro.v2_shadow_features_v1 import ROOT, period_index, require, timestamp
from validation.macro.v2_bls_us_unrate_25_release_pilot_v1 import (
    read_fixture, validate_manifest,
)
from validation.macro.v2_shadow_intensity_v1 import CLIP

SCHEMA = "GMFQ_BLS_U3_SHUTDOWN_GAP_RESEARCH_V1"
RECEIPT = "GMFQ_MACRO_V2_BLS_U3_SPARSE_RELEASE_REENTRY_V1"
PATH = ROOT / "validation/macro/fixtures/v2_bls_us_unemployment_shutdown_2025_gap_resumption.json"
MISSING = "2025-10"
PUBLISHER = "U.S. Bureau of Labor Statistics"
VALID_EVIDENCE = {
    "2025-11": ("2025-12-16T08:30:00-05:00", 4.6,
                "https://www.bls.gov/news.release/archives/empsit_12162025.htm"),
    "2025-12": ("2026-01-09T08:30:00-05:00", 4.4,
                "https://www.bls.gov/news.release/archives/empsit_01092026.htm"),
}
HISTORICAL_LIMIT = timestamp("2026-01-10T00:00:00Z")
WINDOW = 24
EPS = 1e-9


def load_evidence() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def validate_evidence(evidence: dict, pre_gap: dict) -> None:
    """Read-only, fail-closed contract for one precisely sourced observation gap."""
    require(isinstance(evidence, dict) and evidence.get("schema") == SCHEMA,
            "unknown BLS 2025 gap contract")
    validate_manifest(pre_gap)
    require((evidence.get("currency"), evidence.get("pillar"),
             evidence.get("series_id"), evidence.get("canonical_alias"))
            == ("USD", "labour", "LNS14000000", "UNRATE"),
            "official series and alias identity")
    require(evidence.get("source_publisher") == PUBLISHER and
            evidence.get("source_methodology_url") ==
            "https://www.bls.gov/cps/methods/2025-federal-government-shutdown-impact-cps.htm" and
            evidence.get("source_release_calendar_url") ==
            "https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm" and
            evidence.get("source_archive_url") ==
            "https://www.bls.gov/bls/news-release/empsit.htm",
            "official reference links cannot change")
    require(evidence.get("pre_gap_manifest") ==
            "validation/macro/fixtures/v2_bls_us_unrate_25_first_releases_2023_09_2025_09.json",
            "pre-gap manifest identity")
    require(evidence.get("status") ==
            "OFFICIAL_WEB_FIRST_RELEASE_VALUE_DATE__UNHASHED_SOURCE_BYTES" and
            evidence.get("source_evidence_independently_hashed") is False and
            evidence.get("complete_revision_vintage_history_certified") is False,
            "web evidence must not be certified as complete historical revision data")
    gaps = evidence.get("missing_observations")
    require(isinstance(gaps, list) and len(gaps) == 1 and
            isinstance(gaps[0], dict), "exactly one documented absent CPS month")
    gap = gaps[0]
    require(gap.get("reference_period") == MISSING and
            gap.get("status") == "NOT_COLLECTED_NOT_PUBLISHED_NO_CPS_UNEMPLOYMENT_RATE" and
            gap.get("survey") == "CURRENT_POPULATION_SURVEY_HOUSEHOLD" and
            gap.get("reported_first_release") is None and
            gap.get("published_value") is None and
            gap.get("evidence_ref") ==
            evidence["source_methodology_url"] and
            gap.get("permitted_imputation") is False and
            gap.get("permitted_backfill") is False and
            gap.get("continue_monthly_derivative_across_gap") is False,
            "missing October CPS was never collected or released; no imputation")
    policy = evidence.get("methodological_policy")
    require(isinstance(policy, dict) and
            policy.get("strict_monthly_model_remains_fail_closed") is True and
            policy.get("sparse_observation_window_is_event_based_only") is True and
            policy.get("latest_observation_excluded_from_robust_training") is True and
            type(policy.get("rolling_previous_releases")) is int and
            policy["rolling_previous_releases"] == WINDOW and
            policy.get("monthly_velocity") is None and
            policy.get("monthly_acceleration") is None and
            policy.get("monthly_turning_point") is None and
            policy.get("gap_backfill_allowed") is False and
            policy.get("source_release_time_enforced") == "08:30 America/New_York" and
            policy.get("cutoff_time_semantics") ==
            "release information enters only at UTC instant released_at" and
            policy.get("normalized_index_is_descriptive_not_predictive") is True and
            policy.get("safe_to_publish_new_D") is False and
            policy.get("safe_to_update_pair_theses") is False and
            policy.get("permitted_live_macro_score") is False and
            policy.get("permitted_backtest") is False and
            policy.get("writes_live_data") is False,
            "no sparse-event model may rewrite monthly Macro or FX controls")
    releases = evidence.get("resumed_first_releases")
    require(isinstance(releases, list) and len(releases) == 2,
            "exactly the two checked resumed BLS first releases")
    ny = ZoneInfo("America/New_York")
    for i, ((period, pinned), record) in enumerate(zip(VALID_EVIDENCE.items(), releases)):
        require(isinstance(record, dict) and
                record.get("observation_period") == period and
                record.get("kind") == "FIRST" and
                type(record.get("value")) in (int, float) and
                math.isfinite(record["value"]) and
                (record["released_at"], record["value"], record["evidence_ref"]) == pinned,
                "BLS resumed FIRST publication value/date/evidence source drift")
        local = timestamp(record["released_at"]).astimezone(ny)
        raw_clock = datetime.fromisoformat(record["released_at"])
        require(raw_clock.utcoffset() == local.utcoffset() and
                (local.hour, local.minute, local.second) == (8, 30, 0),
                "BLS resumed first releases must use 08:30 real NY/DST clock")
        require(urlparse(record["evidence_ref"]).hostname == "www.bls.gov" and
                local.strftime("%m%d%Y") in record["evidence_ref"],
                "BLS official archived release URL/date")
        require(period_index(record["observation_period"], "M") >
                period_index(pre_gap["vintages"][-1]["observation_period"], "M"),
                "resumed first release must follow September 2025")
    require(period_index(releases[0]["observation_period"], "M") -
            period_index(pre_gap["vintages"][-1]["observation_period"], "M") == 2,
            "October 2025 observation must remain a one-month structural hole")
    require(period_index(releases[1]["observation_period"], "M") -
            period_index(releases[0]["observation_period"], "M") == 1,
            "Nov/Dec published observation periods drifted")


def _snapshot(first: list[dict], row: dict, cutoff: datetime) -> dict:
    """Comparable within this single series only, with an explicit gap flag.

    Do not calculate per-calendar-month velocity, acceleration or turning point
    using the nonadjacent Sept->Nov reference periods.
    """
    earlier = sorted((v for v in first if v["period_index"] <
                      row["period_index"] and v["release_clock"] <= cutoff),
                     key=lambda v: v["period_index"])
    require(len(earlier) >= WINDOW,
            "sparse-event scenario needs 24 previous published FIRST observations")
    training = earlier[-WINDOW:]
    require(len({v["period_index"] for v in training}) == WINDOW and
            all(v["release_clock"] <= cutoff for v in training),
            "duplicate/future FIRST releases in sparse training")
    values = [v["value"] for v in training]
    median = statistics.median(values)
    mad = statistics.median(abs(x - median) for x in values)
    require(mad > EPS, "no variation to normalize in historical first-release window")
    z = (row["value"] - median) / (1.4826 * mad)
    require(math.isfinite(z), "nonfinite historical descriptive z-score")
    past = training[-1]
    skipped = row["period_index"] - past["period_index"] - 1
    require(skipped >= 0, "time-reversed resumed BLS observation")
    return {
        "reference_period": row["period"],
        "first_published_at_utc": row["release_clock"].isoformat(),
        "u3_first_release_percent": row["value"],
        "training_first_releases": WINDOW,
        "training_last_period": past["period"],
        "calendar_observation_holes_since_previous_first_release": skipped,
        "gap_reference_period": MISSING if skipped else None,
        "training_median": median,
        "training_mad": mad,
        "sparse_event_robust_z_unclipped": z,
        "sparse_event_robust_z_clipped": max(-CLIP, min(CLIP, z)),
        "labour_tightness_descriptive_only": -max(-CLIP, min(CLIP, z)),
        "velocity_per_month": None,
        "acceleration_per_month_squared": None,
        "turning_point_per_month": None,
        "successive_reference_month_change_comparable": skipped == 0,
        "not_a_momentum_signal": True,
        "not_a_current_macro_score": True,
        "eligible_for_live_scoring": False,
        "eligible_for_backtest": False,
    }


def replay(*, at: str, evidence: dict | None = None,
           base: dict | None = None) -> dict:
    """Evaluate information strictly at one historical cutoff; no live extrapolation."""
    proof = evidence if evidence is not None else load_evidence()
    historical = base if base is not None else read_fixture()
    validate_evidence(proof, historical)
    cutoff = timestamp(at)
    require(timestamp(historical["as_of"]) <= cutoff <= HISTORICAL_LIMIT,
            "historical shadow cutoff must stay Nov-2025 through Jan-2026 only")
    rows = historical["vintages"] + proof["resumed_first_releases"]
    seen = set()
    first = []
    for r in rows:
        period = r["observation_period"]
        idx = period_index(period, "M")
        require(period not in seen and period != MISSING,
                "duplicate or invented October 2025 unemployment release")
        seen.add(period)
        clock = timestamp(r["released_at"])
        require(r["kind"] == "FIRST" and type(r["value"]) in (int, float) and
                math.isfinite(r["value"]), "all archived US U-3 rows must be FIRST")
        first.append({
            "period": period, "period_index": idx, "value": r["value"],
            "release_clock": clock,
        })
    released = [r for r in first if r["release_clock"] <= cutoff]
    scenarios = [
        _snapshot(released, r, cutoff)
        for r in released if r["period"] in VALID_EVIDENCE
    ]
    # Preserve informational discontinuity across all later snapshots, even if
    # the immediate November-to-December period difference happens to be 1.
    digest = hashlib.sha256(json.dumps({
        "schema": RECEIPT, "at": cutoff.isoformat(),
        "missing": proof["missing_observations"],
        "release_clock_and_first_values":
            [(r["period"], r["release_clock"].isoformat(), r["value"]) for r in released],
        "scenarios": scenarios,
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema": RECEIPT,
        "status": "SPARSE_OBSERVATION_GAP_EVENT_RESEARCH_ONLY",
        "historical_cutoff": cutoff.isoformat(),
        "first_release_periods_available": len(released),
        "missing_2025_10_CPS_reference_period": True,
        "missing_2025_10_observation_imputed": False,
        "missing_2025_10_first_release_invented": False,
        "official_web_source_bytes_hashed": False,
        "full_historical_pit_independently_certified": False,
        "reentered_first_releases": len(scenarios),
        "historical_reentry_snapshots": scenarios,
        "calendar_month_momentum_after_gap_is_withheld": True,
        "model": "RESEARCH_SPARSE_EVENT_DESCRIPTIVE_LEVEL_ONLY",
        "method_fingerprint_sha256": digest,
        "2026_macro_strength": None,
        "2026_forex_signal": None,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "eligible_for_live_scoring": False,
        "eligible_for_backtest": False,
        "writes_live_data": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asof", default="2026-01-09T13:30:00Z")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = replay(at=args.asof)
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")),
                "research receipt may only be written to /tmp")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "historical_cutoff": result["historical_cutoff"],
        "missing_october": result["missing_2025_10_CPS_reference_period"],
        "resumed_releases": result["reentered_first_releases"],
        "safe_to_publish_new_D": result["safe_to_publish_new_D"],
    }))


if __name__ == "__main__":
    main()
