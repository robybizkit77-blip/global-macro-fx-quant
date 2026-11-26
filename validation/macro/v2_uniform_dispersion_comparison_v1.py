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


def domestic_panel(axes):
    """Compare the same fixed domestic equation under two estimators.

    The SD panel may use explicitly tagged BLS gap estimates only in this
    separate research view. No change to the preregistered strict candidate.
    """
    from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
        activity_class, price_class, indicative_regime, continuous_weight_interval,
    )
    expected = {c+"."+p for c in FX for p in ("growth", "labour", "inflation")}
    if set(axes) != expected:
        raise ValueError("exactly 24 G8 economic axes required")
    result = {}
    for c in FX:
        coords, strict, quality = {}, {}, {}
        for p in ("growth", "labour", "inflation"):
            row = axes[c+"."+p]
            sign = -1 if p == "labour" else 1
            z, mad = row["sample_sd_z"], row["strict_mad_z"]
            gap = row.get("separate_bls_gap_estimate")
            tier = "COMPLETE_OBSERVATION_WINDOW_RESEARCH_ONLY"
            if z is None and gap is not None:
                if (c != "USD" or p == "growth" or
                    gap["missing_value_imputed"] is not False or
                    gap["eligible_for_live_scoring"] is not False or
                    gap["missing_periods"] != ["2025-10"] or
                    gap["prior_count"] != 24 or gap["calendar_months"] != 25):
                    raise ValueError("invalid separate BLS estimate")
                z = gap["sample_sd_z"]
                tier = "BLS_GAP_ESTIMATE_RESEARCH_ONLY"
            if z is None:
                tier = "WITHHELD"
            for v in (z, mad):
                if v is not None and (type(v) not in (int, float) or not math.isfinite(v) or abs(v)>3):
                    raise ValueError("invalid normalized research coordinate")
            coords[p] = sign*z if z is not None else None
            strict[p] = sign*mad if mad is not None else None
            quality[p] = {"period": row["period"], "tier": tier,
                          "growth_definition_caveats": row.get("growth_definition_caveats", [])}
        def evaluate(values):
            if any(v is None for v in values.values()):
                return None
            g, l, p = (values[k] for k in ("growth", "labour", "inflation"))
            a = .5*g + .5*l
            return {"activity": a, "activity_class": activity_class(a),
                    "price_class": price_class(p), "regime": indicative_regime(a, p),
                    "weight_sensitivity": continuous_weight_interval(g, l)}
        alternative, original = evaluate(coords), evaluate(strict)
        result[c] = {"sample_sd_axes": coords, "strict_mad_axes": strict,
                     "quality": quality, "sample_sd_domestic": alternative,
                     "strict_mad_domestic": original,
                     "activity_class_agrees": (alternative["activity_class"] == original["activity_class"]
                         if alternative is not None and original is not None else None),
                     "cross_country_rank": None, "fx_strength": None}
    return result


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
            # The official BLS non-release is already independently scoped by
            # the existing one-gap research policy. Keep strict outputs null.
            if c == "USD" and strict["missing_prior_periods"]:
                from validation.macro.v2_us_shutdown_gap_research_v1 import (
                    shadow_gap_estimate, MAX_PRIOR_CALENDAR_MONTHS,
                    TRAIN_PRIOR_ACTUAL_N,
                )
                gap = shadow_gap_estimate(dim, reg, row, heat["currencies"][c][dim], strict, today)
                result["separate_bls_gap_estimate"] = None
                if gap["status"] == "BLS_SHUTDOWN_GAP_AWARE_RESEARCH_ESTIMATE_NOT_PIT":
                    grouped, _ = normalized_source(row, "M")
                    data = transformed_series(grouped, reg["transformation"])
                    newest = max(data)
                    prior = [data[i][1] for i in range(newest-MAX_PRIOR_CALENDAR_MONTHS, newest)
                             if i in data]
                    if len(prior) != TRAIN_PRIOR_ACTUAL_N:
                        raise ValueError(key + ": invalid gap training count")
                    cmp = compare(prior, data[newest][1])
                    if cmp["strict_mad_z"] != gap["estimated_research_robust_z"]:
                        raise ValueError(key + ": gap comparator drift")
                    z = cmp["sample_sd_z"]
                    result["separate_bls_gap_estimate"] = {
                        "status": "OBSERVED_24_OF_25_MONTHS_RESEARCH_ESTIMATE_NOT_PIT",
                        "sample_sd_z": z,
                        "sample_sd_z_unclipped": cmp["sample_sd_z_unclipped"],
                        "economic_polarity_sample_sd_z": -z if dim == "labour" and z is not None else z,
                        "prior_count": len(prior),
                        "calendar_months": MAX_PRIOR_CALENDAR_MONTHS,
                        "missing_periods": gap["missing_calendar_periods"],
                        "official_evidence_url": gap["official_evidence_url"],
                        "missing_value_imputed": False,
                        "eligible_for_live_scoring": False,
                    }
            out[key] = result
    from datetime import timezone
    from validation.macro.v2_g8_gdp_unified_web_research_v1 import unified_research_rows
    growth = growth_comparison(unified_research_rows(),
                               as_of=datetime.now(timezone.utc).isoformat())
    all_axes = {**out, **growth}
    return {"schema": SCHEMA, "policy": POLICY, "as_of": today.isoformat(),
            "rows": out, "growth_rows": growth,
            "domestic_panel_RESEARCH_ONLY": domestic_panel(all_axes),
            "strict_numeric_count": sum(r["strict_mad_z"] is not None for r in out.values()),
            "alternative_numeric_count": sum(r["sample_sd_z"] is not None for r in out.values()),
            "all_24_axis_strict_numeric_count": sum(r["strict_mad_z"] is not None for r in all_axes.values()),
            "all_24_axis_alternative_numeric_count": sum(r["sample_sd_z"] is not None for r in all_axes.values()),
            "complete_alternative_countries": [c for c in FX if all(
                all_axes[c+"."+dim]["sample_sd_z"] is not None
                for dim in ("growth", "labour", "inflation"))],
            "separate_bls_gap_alternative_estimate_count": sum(
                (r.get("separate_bls_gap_estimate") or {}).get("sample_sd_z") is not None
                for r in out.values()),
            "mixed_evidence_classes_not_synchronized_PIT_panel": True,
            "current_revised_not_historical_PIT": True, "growth_not_in_scope": False,
            "safe_to_publish_D": False, "safe_to_update_pairs": False,
            "safe_for_beta_forward": False, "writes_live_data": False}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
