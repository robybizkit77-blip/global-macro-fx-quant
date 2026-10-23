#!/usr/bin/env python3
"""Pre-registered, univariate, point-in-time Macro V2 research intensities.

NOT an FX-strength score, cycle classifier, legacy D.json reconstruction,
forecast, trade decision, or certified first-release archive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import (
    ROOT, build_features, number, period_index, require, timestamp,
)

SCHEMA = "GMFQ_MACRO_V2_SHADOW_INTENSITY_V1"
# Economic meaning and polarity are pre-registered, never fitted to D.json or FX.
# Positive inflation pressure is NOT automatically good for that currency.
SERIES = {
    "real_gdp_qoq": ("growth", "Q", "qoq_pct", 1, "REAL_ACTIVITY"),
    "industrial_production_yoy": ("growth", "M", "yoy_pct", 1, "REAL_ACTIVITY"),
    "unemployment_rate": ("labour", "M", "percent", -1, "LABOUR_TIGHTNESS"),
    "unemployment_rate_quarterly": ("labour", "Q", "percent", -1, "LABOUR_TIGHTNESS"),
    "headline_cpi_yoy": ("inflation", "M", "yoy_pct", 1, "PRICE_PRESSURE"),
    "headline_cpi_yoy_quarterly": ("inflation", "Q", "yoy_pct", 1, "PRICE_PRESSURE"),
}
WINDOW = {"M": 24, "Q": 12}
CLIP = 3.0
EPS = 1e-9


def build_shadow_intensity(manifest: dict) -> dict:
    """Robust expanding-context intensity at cutoff using prior FIRST releases.

    The rolling window is fixed at 24 monthly / 12 quarterly observations.
    Current observation is excluded from its normalization window. Future
    revisions cannot alter either training or the latest FIRST value.
    """
    require(isinstance(manifest, dict), "manifest must be an object")
    typ = manifest.get("variable_type")
    require(typ in SERIES, "unsupported pre-registered economic variable")
    pillar, frequency, unit, polarity, meaning = SERIES[typ]
    require((manifest.get("pillar"), manifest.get("frequency"),
             manifest.get("unit")) == (pillar, frequency, unit),
            "pillar/frequency/units inconsistent with economic series type")

    # This validates FIRST/REVISION integrity, offset-aware releases, 4-point
    # continuity, staleness, evidence refs, transport and non-finite values.
    raw = build_features(manifest)
    cutoff = timestamp(manifest["as_of"])
    first = []
    for event in manifest["vintages"]:
        if event["kind"] != "FIRST":
            continue
        when = timestamp(event["released_at"])
        if when > cutoff:
            continue
        first.append({
            "idx": period_index(event["observation_period"], frequency),
            "period": event["observation_period"],
            "value": float(event["value"]),
            "released_at": when.isoformat(),
            "evidence_ref": event["evidence_ref"],
        })
    first.sort(key=lambda p: p["idx"])
    n = WINDOW[frequency]
    require(len(first) >= n + 1,
            "insufficient independently dated first releases for training window")
    recent = first[-(n + 1):]
    require(all(recent[i+1]["idx"] - recent[i]["idx"] == 1
                for i in range(n)),
            "rolling training window contains a missing observation period")
    train = [x["value"] for x in recent[:-1]]
    current = recent[-1]
    med = statistics.median(train)
    mad = statistics.median([abs(x - med) for x in train])
    require(mad > EPS and math.isfinite(mad),
            "zero or near-zero robust training dispersion")
    robust_scale = 1.4826 * mad
    z = (current["value"] - med) / robust_scale
    require(number(z), "non-finite normalized intensity")
    clipped = max(-CLIP, min(CLIP, z))
    changes = [recent[-i]["value"] - recent[-(i+1)]["value"]
               for i in (1, 2)]
    v, pv = changes
    turning = ("DOWN_TO_UP" if pv < 0 < v else
               "UP_TO_DOWN" if pv > 0 > v else "NONE")
    signed = polarity * clipped
    # Do not use sign alone as a policy stance or currency recommendation.
    identity = {
        "method": SCHEMA, "variable_type": typ,
        "currency": manifest["currency"], "pillar": pillar,
        "series_id": manifest["series_id"], "frequency": frequency,
        "unit": unit, "source": manifest["source"],
        "as_of": cutoff.isoformat(), "training_n": n,
        "first_release_window": recent, "polarity": polarity,
        "clip": CLIP, "median_scale": 1.4826,
    }
    digest = hashlib.sha256(json.dumps(
        identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema": SCHEMA,
        "status": "ILLUSTRATIVE_PIT_SHADOW_INTENSITY_NOT_MODEL_CERTIFIED",
        "variable_type": typ,
        "currency": manifest["currency"], "pillar": pillar,
        "series_id": manifest["series_id"], "frequency": frequency,
        "unit": unit, "as_of": cutoff.isoformat(),
        "latest_period": current["period"],
        "latest_first_release_at": current["released_at"],
        "latest_evidence_ref": current["evidence_ref"],
        "latest_first_release_value": current["value"],
        "training_first_releases": n,
        "training_end_period": recent[-2]["period"],
        "training_median": med, "training_mad": mad,
        "robust_z_unclipped": z,
        "robust_z_clipped": clipped,
        "economic_polarity": polarity,
        "economic_dimension": meaning,
        "dimension_intensity": signed,
        "history_rank_percent": 100 * (sum(x < current["value"] for x in train)
                            + 0.5 * sum(x == current["value"] for x in train)) / n,
        "velocity_first_release_per_period": v,
        "acceleration_first_release_per_period_squared": v - pv,
        "turning_point_first_release": turning,
        "method_fingerprint_sha256": digest,
        "first_release_only_for_normalization": True,
        "current_observation_excluded_from_training": True,
        "cutoff_pit_event_integrity_checked": True,
        "raw_feature_receipt_fingerprint_sha256": raw["feature_fingerprint_sha256"],
        "source_evidence_is_independently_certified": False,
        "not_comparable_across_frequency_or_variable": True,
        "inflation_pressure_is_not_fx_strength": True,
        "currency_strength_score": None,
        "economic_cycle": None,
        "ready_for_macro_scoring": False,
        "usable_for_backtest": False,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "writes_live_data": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    # This is an opt-in research command, never a production publisher.
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")),
                "output must reside under /tmp; production paths are forbidden")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    receipt = build_shadow_intensity(manifest)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in (
        "currency", "pillar", "variable_type", "latest_period",
        "training_first_releases", "dimension_intensity",
        "safe_to_publish_new_D", "safe_to_update_pair_theses",
    )}))


if __name__ == "__main__":
    main()
