#!/usr/bin/env python3
"""Historical US labour 25-FIRST-release research replay, not a 2026 live score.

Values and release clocks transcribed from individual official BLS archived
Employment Situation headlines. No independent archive-byte hashes / exhaustive
revision vintages; do not certify production PIT or FX strategies.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from validation.macro.v2_shadow_features_v1 import (
    ROOT, period_index, require, timestamp,
)
from validation.macro.v2_shadow_intensity_v1 import build_shadow_intensity

PATH = ROOT / "validation/macro/fixtures/v2_bls_us_unrate_25_first_releases_2023_09_2025_09.json"
RECEIPT = "GMFQ_MACRO_V2_US_BLS_25_FIRST_RELEASE_HISTORICAL_PILOT_V1"
FIRST = "2023-09"
LAST = "2025-09"
EXACT_ASOF = "2025-11-20T13:30:00+00:00"


def read_fixture() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def validate_manifest(m: dict) -> None:
    """Stop before scoring for any chronology, identity or provenance drift."""
    require(isinstance(m, dict), "US 25-release manifest is not an object")
    require(m.get("schema") == "GMFQ_MACRO_V2_PIT_FEATURE_INPUT_V1"
            and m.get("currency") == "USD"
            and m.get("pillar") == "labour"
            and m.get("series_id") == "LNS14000000"
            and m.get("canonical_alias") == "UNRATE"
            and m.get("variable_type") == "unemployment_rate"
            and m.get("frequency") == "M" and m.get("unit") == "percent"
            and m.get("max_lag_periods") == 2, "BLS U-3 identity/cadence/lag contract")
    require(m.get("source") == {
        "authority": "U.S. Bureau of Labor Statistics",
        "source_id": "LNS14000000", "transport": "OFFICIAL_DIRECT",
    }, "original BLS source identity")
    require(m.get("archive_index") ==
            "https://www.bls.gov/bls/news-release/empsit.htm"
            and m.get("alias_reference") ==
            "https://fred.stlouisfed.org/series/UNRATE",
            "BLS archive or source mapping reference changed")
    require(m.get("evidence_provenance") ==
            "PRIMARY_BLS_ARCHIVED_WEB_RELEASE_HEADLINE_ATTESTED__NO_IMMUTABLE_ARCHIVE_BYTES"
            and m.get("source_evidence_is_independently_certified") is False
            and m.get("archive_bytes_sha256") is None
            and m.get("complete_revision_vintage_history_certified") is False
            and m.get("eligible_for_current_2026_macro_scoring") is False
            and m.get("writes_live_data") is False,
            "a headline attestation cannot promote an archived PIT certification")
    require(m.get("source_break_after_pilot") ==
            "2025-10_EMPLOYMENT_SITUATION_NEVER_PUBLISHED_SHUTDOWN"
            and m.get("training_window_from") == FIRST
            and m.get("training_window_to") == "2025-08"
            and m.get("latest_first_release_period") == LAST
            and m.get("latest_first_release_date") == "2025-11-20",
            "source discontinuity and training end cannot be silently changed")
    require(timestamp(m.get("as_of")).isoformat() == EXACT_ASOF,
            "historical 20 November first-publication cutoff must be preserved")
    releases = m.get("vintages")
    require(isinstance(releases, list) and len(releases) == 25,
            "exactly 25 dated FIRST releases required")
    require(len({x.get("evidence_ref") for x in releases}) == 25,
            "archived release URLs must be unique")
    ny = ZoneInfo("America/New_York")
    prev_utc = None
    for i, row in enumerate(releases):
        period = row.get("observation_period")
        require(period_index(period, "M") == period_index(FIRST, "M") + i,
                "missing or reordered published U-3 reference month")
        require(row.get("kind") == "FIRST"
                and type(row.get("value")) in (float, int)
                and math.isfinite(row["value"])
                and 2.0 <= row["value"] <= 10.0,
                "historical unemployment headline value/first-release contract")
        clock = timestamp(row.get("released_at"))
        local = clock.astimezone(ny)
        require((local.hour, local.minute, local.second) == (8, 30, 0),
                "BLS archived employment release must be 08:30 New York")
        require(datetime.fromisoformat(row["released_at"]).utcoffset()
                == local.utcoffset(),
                "offset not consistent with America/New_York DST")
        require(clock.date() >= datetime.fromisoformat(period + "-01").date()
                and clock <= timestamp(m["as_of"]),
                "BLS release chronology / cutoff")
        d = local.strftime("%m%d%Y")
        url = row.get("evidence_ref")
        require(isinstance(url, str) and
                url == "https://www.bls.gov/news.release/archives/empsit_" + d + ".htm"
                and urlsplit(url).hostname == "www.bls.gov",
                "archived HTML evidence must match exact release date and source")
        require(prev_utc is None or clock > prev_utc,
                "first releases must have strictly increasing publication clocks")
        prev_utc = clock
    require(releases[-1]["observation_period"] == LAST
            and releases[-1]["value"] == 4.4
            and releases[-1]["released_at"] == "2025-11-20T08:30:00-05:00",
            "delayed September 2025 FIRST release source changed")
    require(releases[-2]["observation_period"] == "2025-08"
            and releases[-2]["value"] == 4.3
            and releases[-2]["released_at"] == "2025-09-05T08:30:00-04:00",
            "pre-shutdown observation and cutoff changed")
    # Protect already reviewed December 2023-April 2024 pilot observations.
    earlier = json.loads((ROOT /
        "validation/macro/fixtures/v2_bls_us_unrate_first_release_2023_12_2024_04.json"
        ).read_text(encoding="utf-8"))["vintages"]
    for row in earlier:
        matching = [r for r in releases if
                    r["observation_period"] == row["observation_period"]]
        require(len(matching) == 1
                and matching[0]["value"] == row["value"]
                and matching[0]["released_at"] == row["released_at"]
                and matching[0]["evidence_ref"] == row["evidence_ref"],
                "first-five independently reviewed BLS pilot anchors have drifted")


def run(manifest: dict | None = None) -> dict:
    m = read_fixture() if manifest is None else manifest
    validate_manifest(m)
    feature = build_shadow_intensity(m)
    require(feature["training_first_releases"] == 24
            and feature["training_end_period"] == "2025-08"
            and feature["latest_period"] == "2025-09"
            and feature["latest_first_release_value"] == 4.4
            and feature["economic_polarity"] == -1,
            "trained PIT shadow fixture unexpectedly changed")
    return {
        "schema": RECEIPT,
        "status": "HISTORICAL_25_FIRST_RELEASE_WEB_ATTESTATIONS_NOT_CERTIFIED",
        "historical_cutoff": m["as_of"],
        "source_id": "LNS14000000", "fred_alias": "UNRATE",
        "training_releases": feature["training_first_releases"],
        "current_first_release": feature["latest_first_release_value"],
        "last_reference_period": feature["latest_period"],
        "first_release_dates_officially_attested_in_archived_web_pages": 25,
        "archive_release_bytes_hashed": False,
        "independent_full_pit_certified": False,
        "october_2025_release_gap": True,
        "training_median": feature["training_median"],
        "training_mad": feature["training_mad"],
        "unemployment_robust_z_clipped": feature["robust_z_clipped"],
        "labour_tightness_intensity_not_currency_strength": feature["dimension_intensity"],
        "latest_observation_excluded_from_training": True,
        "method_fingerprint_sha256": feature["method_fingerprint_sha256"],
        "not_a_current_2026_macro_score": True,
        "not_an_fx_signal": True,
        "currency_strength_score": None,
        "eligible_for_live_macro": False,
        "eligible_for_backtest": False,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "writes_live_data": False,
        "notes": [
            "Earliest official BLS headlines for each period were read manually; "+
            "their immutable bytes and all subsequent revisions were not independently audited.",
            "The last FIRST release was delayed until 2025-11-20. Missing October "+
            "2025 Employment Situation cannot be imputed.",
            "Only a historical dimension pilot; no trade return or predictive validation.",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    receipt = run()
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")),
                "no output outside /tmp allowed")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in (
        "status", "historical_cutoff", "training_releases",
        "labour_tightness_intensity_not_currency_strength",
        "safe_to_publish_new_D", "writes_live_data",
    )}))


if __name__ == "__main__":
    main()
