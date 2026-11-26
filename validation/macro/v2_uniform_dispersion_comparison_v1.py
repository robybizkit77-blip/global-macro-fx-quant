"""Research-only comparison of two prior-window normalizations for every G8 core series.

No per-country fallback, no change to strict MAD, no imputation or historical PIT claim.
Conventional sample-SD z is a distinct candidate, not a replacement robust z.
"""
from __future__ import annotations
import json
import math
import statistics
from datetime import date, datetime
from zoneinfo import ZoneInfo
from validation.macro.v2_g8_observed_feature_bridge_v1 import (
    ROOT, FX, PILLARS, WINDOW, normalized_source, transformed_series, pillar_feature,
)

SCHEMA = "GMFQ_MACRO_V2_UNIFORM_DISPERSION_COMPARISON_V1"
POLICY = "PRIOR_24M_12Q_MEAN_SAMPLE_SD_ALL_24_AXES_V2"


def compare(prior, current):
    if len(prior) < 2 or not all(type(v) in (int, float) and math.isfinite(v)
                                 for v in [*prior, current]):
        raise ValueError("invalid finite prior window")
    mean = statistics.mean(prior)
    sd = statistics.stdev(prior)
    median = statistics.median(prior)
    mad = statistics.median(abs(v - median) for v in prior)
    raw = (current - mean) / sd if sd > 1e-9 else None
    robust = (current - median) / (1.4826 * mad) if mad > 1e-9 else None
    clip = lambda z: max(-3., min(3., z)) if z is not None else None
    return {
        "prior_count": len(prior), "prior_mean": mean, "prior_sample_sd": sd,
        "prior_median": median, "prior_mad": mad,
        "sample_sd_z": clip(raw), "sample_sd_z_unclipped": raw,
        "strict_mad_z": clip(robust), "strict_mad_z_unclipped": robust,
        "midrank_percentile": (sum(v < current for v in prior) +
                               .5 * sum(v == current for v in prior)) / len(prior),
        "velocity": current - prior[-1],
        "acceleration": current - 2 * prior[-1] + prior[-2],
        "turning_point": ("DOWN_TO_UP" if prior[-1] < prior[-2] and current > prior[-1]
                          else "UP_TO_DOWN" if prior[-1] > prior[-2] and current < prior[-1]
                          else "NONE"),
    }


def growth_comparison(rows, *, as_of):
    """Use exactly the existing GDP first-statement cutoff and 12 prior quarters.

    Do not substitute a later revision or hide country measurement caveats.
    """
    from validation.macro.v2_g8_gdp_first_web_growth_features_v1 import (
        receipt, validate, utc, asof_visible, qidx, nonannualized, TRAIN,
    )
    audited = receipt(rows, as_of=as_of)
    cutoff = utc(as_of)
    first = {}
    for row in validate(rows):
        if row["stage_order"] == 0 and asof_visible(row) <= cutoff:
            first[(row["currency"], qidx(row["reference_quarter"]))] = row
    out = {}
    for c in FX:
        feat = audited["features"][c]
        newest = qidx(feat["latest_initial_period"])
        item = {
            "period": feat["latest_initial_period"],
            "value": feat["latest_nonannualized_qoq_pct"],
            "strict_status": feat["status"],
            "missing_prior_periods": feat["missing_required_reference_quarters"],
            "sample_sd_z": None,
            "strict_mad_z": feat["research_robust_growth_z"],
            "source_class": "INITIAL_PUBLISHER_WEB_STATEMENTS_NOT_ARCHIVAL_PIT",
            "growth_definition_caveats": feat.get("growth_definition_caveats", []),
            "latest_visible_revision": feat["latest_visible_revision"],
        }
        if not item["missing_prior_periods"]:
            prior = [nonannualized(first[(c, i)]) for i in range(newest-TRAIN, newest)]
            cmp = compare(prior, item["value"])
            if cmp["strict_mad_z"] != item["strict_mad_z"]:
                raise ValueError(c + ": strict GDP comparator drift")
            item.update(cmp)
            item["economic_polarity_sample_sd_z"] = cmp["sample_sd_z"]
        out[c + ".growth"] = item
    return out


def run(root=ROOT):
    load = lambda p: json.loads((root / p).read_text(encoding="utf-8"))
    series = load("live_data/sections/MACRO_SERIES.json")
    heat = load("live_data/sections/MACRO_THERMOMETER_DATA.json")
    registry = load("validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json")["series"]
    today = datetime.now(ZoneInfo("Europe/Rome")).date()
    out = {}
    for c in FX:
        for dim in PILLARS:
            key = c + "." + dim
            reg = registry[key]
            rid = (reg.get("historical_replay_evidence") or {}).get("macro_series_id") or reg["series_id"] + "_history_value"
            hits = [r for r in series[c] if r.get("id") == rid]
            if len(hits) != 1:
                raise ValueError(key + ": source identity")
            row = hits[0]
            strict = pillar_feature(c, dim, reg, row, heat["currencies"][c][dim], today)
            result = {"period": strict["observation_period"],
                      "value": strict["observation_value"],
                      "strict_status": strict["status"],
                      "missing_prior_periods": strict["missing_prior_periods"],
                      "sample_sd_z": None, "strict_mad_z": strict["research_robust_z"]}
            if not strict["missing_prior_periods"]:
                freq = reg["frequency"]
                grouped, _ = normalized_source(row, freq)
                data = transformed_series(grouped, reg["transformation"])
                newest = max(data)
                prior = [data[i][1] for i in range(newest - WINDOW[freq], newest)]
                cmp = compare(prior, data[newest][1])
                if cmp["strict_mad_z"] != strict["research_robust_z"]:
                    raise ValueError(key + ": strict comparator drift")
                result.update(cmp)
                result["economic_polarity_sample_sd_z"] = (
                    -cmp["sample_sd_z"] if dim == "labour" and cmp["sample_sd_z"] is not None
                    else cmp["sample_sd_z"])
            out[key] = result
    from datetime import timezone
    from validation.macro.v2_g8_gdp_unified_web_research_v1 import unified_research_rows
    growth = growth_comparison(unified_research_rows(),
                               as_of=datetime.now(timezone.utc).isoformat())
    all_axes = {**out, **growth}
    return {"schema": SCHEMA, "policy": POLICY, "as_of": today.isoformat(),
            "rows": out, "growth_rows": growth,
            "strict_numeric_count": sum(r["strict_mad_z"] is not None for r in out.values()),
            "alternative_numeric_count": sum(r["sample_sd_z"] is not None for r in out.values()),
            "all_24_axis_strict_numeric_count": sum(r["strict_mad_z"] is not None for r in all_axes.values()),
            "all_24_axis_alternative_numeric_count": sum(r["sample_sd_z"] is not None for r in all_axes.values()),
            "complete_alternative_countries": [c for c in FX if all(
                all_axes[c+"."+dim]["sample_sd_z"] is not None
                for dim in ("growth", "labour", "inflation"))],
            "mixed_evidence_classes_not_synchronized_PIT_panel": True,
            "current_revised_not_historical_PIT": True, "growth_not_in_scope": False,
            "safe_to_publish_D": False, "safe_to_update_pairs": False,
            "safe_for_beta_forward": False, "writes_live_data": False}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
