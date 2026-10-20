#!/usr/bin/env python3
"""BLS first-release historical pilot, strictly research-only, without FX scoring.

Manual official website value/date attestations are not immutable source bytes.
Do not confuse first-release-only history with complete revised PIT vintages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from validation.macro.v2_shadow_features_v1 import (
    ROOT, SCHEMA, build_features, require, timestamp,
)

MANIFEST = ROOT / "validation/macro/fixtures/v2_bls_us_unrate_first_release_2023_12_2024_04.json"
PILOT_SCHEMA = "GMFQ_MACRO_V2_BLS_FIRST_RELEASE_PILOT_V1"
# Facts checked against the five period-specific archived BLS news releases.
# Intentionally independent of the JSON fixture: a mutated finite value or
# shifted release time must fail before being interpreted as genuine history.
PINNED_RELEASES = (
    ("2023-12", 3.7, "2024-01-05", "USDL-24-0006", "empsit_01052024.htm"),
    ("2024-01", 3.7, "2024-02-02", "USDL-24-0148", "empsit_02022024.htm"),
    ("2024-02", 3.9, "2024-03-08", "USDL-24-0451", "empsit_03082024.htm"),
    ("2024-03", 3.8, "2024-04-05", "USDL-24-0629", "empsit_04052024.htm"),
    ("2024-04", 3.9, "2024-05-03", "USDL-24-0796", "empsit_05032024.htm"),
)


def validate_official_attestations(manifest: dict) -> None:
    require(isinstance(manifest, dict) and manifest.get("schema") == SCHEMA,
            "BLS manifest schema invalid")
    require((manifest.get("currency"), manifest.get("pillar"),
             manifest.get("series_id"), manifest.get("frequency")) ==
            ("USD", "labour", "LNS14000000", "M"), "BLS identity mismatch")
    require(manifest.get("unit") == "percent, seasonally adjusted unemployment rate",
            "BLS unemployment rate unit mismatch")
    require(manifest.get("max_lag_periods") == 2,
            "BLS pre/post-release freshness guard drift")
    require(manifest.get("first_release_only") is True, "first-release-only contract missing")
    require(manifest.get("evidence_provenance") ==
            "MANUALLY_CROSSCHECKED_BLS_ARCHIVED_RELEASE_HTML_NO_IMMUTABLE_BYTES",
            "BLS evidence limitations must be explicit")
    require(manifest.get("source") == {
        "authority": "U.S. Bureau of Labor Statistics",
        "source_id": "LNS14000000",
        "transport": "OFFICIAL_DIRECT",
    }, "BLS declared authority changed")
    records = manifest.get("vintages")
    require(isinstance(records, list) and len(records) == len(PINNED_RELEASES),
            "five unique official first releases are mandatory")
    zone = ZoneInfo("America/New_York")
    for record, expected in zip(records, PINNED_RELEASES):
        require(isinstance(record, dict), "invalid BLS period record")
        period, value, date, release_id, archive = expected
        require(record.get("observation_period") == period,
                "BLS observation period mismatch")
        require(type(record.get("value")) in (float, int) and
                math.isfinite(record["value"]) and
                record["value"] == value, "BLS first-release value mismatch")
        require(record.get("kind") == "FIRST" and
                record.get("news_release_id") == release_id,
                "BLS first-release identity mismatch")
        url = urlsplit(str(record.get("evidence_ref") or ""))
        require(url.scheme == "https" and url.netloc == "www.bls.gov" and
                url.path == "/news.release/archives/" + archive and
                not url.query and not url.fragment,
                "BLS archival source URL mismatch")
        stamp = timestamp(record.get("released_at"))
        local = stamp.astimezone(zone)
        require(local.date().isoformat() == date and
                (local.hour, local.minute, local.second) == (8, 30, 0),
                "BLS embargo lift timestamp not 08:30 New York on official release date")


def replay(cutoff: str, manifest: dict | None = None) -> dict:
    """Output features and an optional PRIOR-OBSERVATION-only illustrative z-score.

    Normalization window is 4 consecutive PUBLISHED first-release values prior
    to the newest selected observation. No current value in mean or variance.
    This is not an econometric production normalization or a currency signal.
    """
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    validate_official_attestations(manifest)
    asof = timestamp(cutoff)
    clone = json.loads(json.dumps(manifest))
    clone["as_of"] = asof.isoformat()
    raw = build_features(clone)

    selected = [r for r in manifest["vintages"]
                if timestamp(r["released_at"]) <= asof]
    # The pilot explicitly contains only five unique FIRST observations.
    # This is not an archive of later revised readings for old periods.
    newest = selected[-1]
    require(newest["observation_period"] == raw["latest_period"],
            "PIT feature selection disagrees with pinned latest vintage")
    norm = {
        "schema": "GMFQ_MACRO_V2_TRAIN_ONLY_NORMALIZATION_V1",
        "status": "WITHHELD_INSUFFICIENT_PRIOR_RELEASES",
        "value": None, "training_observations": max(0, len(selected)-1),
        "training_rule": "PRIOR_4_FIRST_RELEASE_LEVELS_EXCLUDE_CURRENT",
        "training_mean": None, "training_population_sd": None,
        "training_periods": [], "ready_for_scoring": False,
    }
    if len(selected) >= 5:
        prior = selected[-5:-1]
        values = [float(r["value"]) for r in prior]
        mean = statistics.fmean(values)
        sd = statistics.pstdev(values)
        require(sd > 0.0 and math.isfinite(sd), "zero/nonfinite training-only variance")
        z = (float(newest["value"]) - mean) / sd
        require(math.isfinite(z), "normalization nonfinite")
        norm.update({
            "status": "PILOT_PRIOR_ONLY_Z_COMPUTED_NOT_ECONOMICALLY_VALIDATED",
            "value": z,
            "training_observations": len(values),
            "training_mean": mean,
            "training_population_sd": sd,
            "training_periods": [r["observation_period"] for r in prior],
        })
    identity = hashlib.sha256(json.dumps(
        manifest, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return {
        "schema": PILOT_SCHEMA, "status": "OFFICIAL_WEB_FIRST_RELEASE_PILOT_NO_BYTE_CERTIFICATION",
        "as_of": asof.isoformat(),
        "official_authority": "U.S. Bureau of Labor Statistics",
        "source_series_id": "LNS14000000", "first_release_only": True,
        "observed_official_archival_pages": len(PINNED_RELEASES),
        "archival_source_bytes_hashed": False,
        "official_archive_rechecked_at_ci_runtime": False,
        "complete_revision_history_available": False,
        "full_historical_pit_certified": False,
        "evidence_manifest_sha256": identity,
        "raw_features": raw, "illustrative_normalization": norm,
        "ready_for_macro_scoring": False,
        "ready_for_live_feature_replay": False,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "writes_live_data": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asof", default="2024-05-03T12:30:00Z")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    receipt = replay(args.asof)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "status": receipt["status"],
        "as_of": receipt["as_of"],
        "level": receipt["raw_features"]["level"],
        "velocity_per_period": receipt["raw_features"]["velocity_per_period"],
        "normalization_status": receipt["illustrative_normalization"]["status"],
        "ready_for_macro_scoring": False,
        "safe_to_publish_new_D": False,
    }))


if __name__ == "__main__":
    main()
