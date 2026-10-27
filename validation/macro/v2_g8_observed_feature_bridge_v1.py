#!/usr/bin/env python3
"""Observed-data -> Macro V2 *research* feature bridge, deliberately not D.json.

Reads the 16 registered inflation/labour history series, checks exact economic
periods and registry-vs-thermometer identities, and computes a strictly
prior-period median/MAD intensity only when the preceding 24 monthly / 12
quarterly observations are consecutive. The input series are CURRENTLY REVISED,
not publication-day PIT archives. This is NOT an FX strength signal.

Separately displays the eight documented Q2 2026 publisher GDP observations
(and subsequent disclosed revisions). GDP is research web evidence, never
normalized against these inflation/labour values or promoted into Growth scores.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.v2_g8_quarterly_gdp_web_release_ledger_v1 import review as gdp_review
from validation.macro.v2_shadow_features_v1 import ROOT

FX = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
PILLARS = ("inflation", "labour")
SCHEMA = "GMFQ_MACRO_V2_OBSERVED_G8_FEATURE_BRIDGE_V1"
SOURCE = ROOT / "live_data/sections"
REGISTRY = ROOT / "validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json"
WINDOW = {"M": 24, "Q": 12}
MAX_Z = 3.0


def require(ok, message):
    if not ok:
        raise ValueError("MACRO_V2_OBSERVED_BRIDGE_REJECTED: " + message)


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def period(raw, frequency):
    """Period identity, not a publication timestamp. Accept valid day aliases."""
    require(frequency in WINDOW and isinstance(raw, str), "invalid period/frequency")
    match = re.fullmatch(r"(\d{4})-(\d{2})(?:-(\d{2}))?", raw)
    require(match is not None, "noncanonical economic observation date")
    y, m = int(match[1]), int(match[2])
    require(1900 <= y <= 2100 and 1 <= m <= 12, "invalid economic month")
    if match[3]:
        date.fromisoformat(raw)  # refuse impossible calendar days
    if frequency == "Q":
        require(m in (3, 6, 9, 12), "quarterly series requires quarter-end month")
        return 4 * y + m // 3 - 1, f"{y:04d}Q{m // 3}"
    return 12 * y + m - 1, f"{y:04d}-{m:02d}"


def index_to_period(idx, frequency):
    if frequency == "M":
        return f"{idx // 12:04d}-{idx % 12 + 1:02d}"
    return f"{idx // 4:04d}Q{idx % 4 + 1}"


def normalized_source(row, frequency):
    """Collapse identical date-precision aliases, but never conflicting data."""
    dates, values = row.get("dates"), row.get("values")
    require(isinstance(dates, list) and isinstance(values, list)
            and len(dates) == len(values) and len(dates) >= 2,
            "missing registered dated historical observations")
    grouped, aliases = {}, 0
    for raw, value in zip(dates, values):
        idx, label = period(raw, frequency)
        require(finite(value), "nonfinite historical economic value")
        if idx in grouped:
            require(math.isclose(grouped[idx][1], value, rel_tol=0, abs_tol=1e-10),
                    "conflicting aliases for the same economic period")
            aliases += 1
        else:
            grouped[idx] = (label, float(value))
    return grouped, aliases


def transformed_series(source, transform):
    if transform == "yoy_pct_from_index":
        out = {}
        for idx, (label, level) in source.items():
            previous = source.get(idx - 12)
            if previous is not None:
                require(level > 0 and previous[1] > 0, "CPI index levels must be positive")
                out[idx] = (label, 100.0 * (level / previous[1] - 1.0))
        return out
    require(transform in ("level", "reported_yoy_rate", "derived_yoy_from_index"),
            "unknown registered transformation")
    # CAD derived_yoy_from_index is ALREADY a derived YoY series in MACRO_SERIES.
    return source


def pillar_feature(currency, dimension, registered, row, heat, as_of):
    """Current revised-history descriptive z, WITHOUT backtest/FX eligibility."""
    require(currency in FX and dimension in PILLARS, "noncanonical currency/pillar")
    frequency = registered.get("frequency")
    require(frequency in WINDOW and
            (heat.get("series_id"), heat.get("frequency"),
             heat.get("transformation")) ==
            (registered.get("series_id"), frequency, registered.get("transformation")),
            "thermometer and registered source identity/frequency/transform drift")
    require(all(heat.get("validation", {}).get(k) is True
                for k in ("source", "history", "latest", "transformation")),
            "source historical validation not completed")
    expected_id = ((registered.get("historical_replay_evidence") or {})
                   .get("macro_series_id") or registered["series_id"] + "_history_value")
    require(row.get("id") == expected_id, "registered MACRO_SERIES ID mismatch")
    samples, aliases = normalized_source(row, frequency)
    data = transformed_series(samples, registered["transformation"])
    require(data, "no economically transformed observations")
    newest = max(data)
    _, newest_label = period(heat.get("as_of"), frequency)
    require(data[newest][0] == newest_label, "source and thermometer latest period differ")
    _, cutoff_label = period(as_of.isoformat()[:7], "M")
    require(index_to_period(newest, frequency) <=
            (f"{as_of.year:04d}-{as_of.month:02d}" if frequency == "M"
             else f"{as_of.year:04d}Q{(as_of.month - 1) // 3 + 1}"),
            "economic observations from the future")
    value = data[newest][1]
    require(finite(heat.get("latest_value")) and
            math.isclose(value, heat["latest_value"], rel_tol=0, abs_tol=1e-7),
            "derived source observation disagrees with displayed thermometer")
    required = WINDOW[frequency]
    history_idx = list(range(newest - required, newest))
    missing = [index_to_period(i, frequency) for i in history_idx if i not in data]
    result = {
        "currency": currency, "pillar": dimension, "frequency": frequency,
        "canonical_series_id": registered["series_id"],
        "macro_series_id": expected_id,
        "transformation": registered["transformation"],
        "observation_period": data[newest][0],
        "observation_value": value,
        "observation_date_is_not_release_timestamp": True,
        "source_observation_is_current_revised_history_not_historic_pit": True,
        "date_precision_aliases_collapsed_with_equal_values": aliases,
        "required_prior_consecutive_periods": required,
        "missing_prior_periods": missing,
        "research_robust_z": None,
        "research_direction_velocity": None,
        "research_acceleration": None,
        "economic_interpretation": ("PRICE_PRESSURE_NOT_FX_STRENGTH" if dimension == "inflation"
                                   else "LABOUR_TIGHTNESS_NOT_FX_STRENGTH"),
        "eligible_for_macro_score": False,
        "eligible_for_historical_backtest": False,
    }
    if missing:
        result["status"] = "NO_Z_MISSING_PRIOR_ECONOMIC_PERIODS"
        return result
    train = [data[i][1] for i in history_idx]
    median = statistics.median(train)
    mad = statistics.median(abs(x - median) for x in train)
    if mad <= 1e-9:
        result["status"] = "NO_Z_ZERO_ROBUST_DISPERSION"
        return result
    signed = (value - median) / (1.4826 * mad)
    require(math.isfinite(signed), "nonfinite candidate intensity")
    direction = value - data[newest - 1][1]
    previous = data[newest - 1][1] - data[newest - 2][1]
    result.update({
        "status": "DESCRIPTIVE_REVISED_HISTORY_ROBUST_Z_NOT_PIT",
        "prior_window_first_period": data[history_idx[0]][0],
        "prior_window_last_period": data[history_idx[-1]][0],
        "prior_window_median": median,
        "prior_window_mad": mad,
        "research_robust_z": max(-MAX_Z, min(MAX_Z, signed)),
        "research_robust_z_unclipped": signed,
        "research_direction_velocity": direction,
        "research_acceleration": direction - previous,
        "labour_tightness_direction": (-direction if dimension == "labour" else None),
        "research_current_excluded_from_training": True,
    })
    return result


def growth_research(as_of):
    """Publisher-web Q2 description, retaining original units and source links."""
    ledger = gdp_review()
    require(ledger["summary"]["first_publisher_web_statements_documented"] == 8 and
            ledger["safe_to_update_live_macro_D"] is False,
            "GDP evidence cannot auto-promote Growth")
    rows = {}
    for event in ledger["events"]:
        ccy = event["currency"]
        visible = datetime.fromisoformat(event["conservative_available_from_utc"]).date()
        if visible > as_of:
            continue
        if ccy not in rows or event["stage_order"] > rows[ccy]["stage_order"]:
            rows[ccy] = event
    result = {}
    for ccy in FX:
        if ccy not in rows:
            result[ccy] = {"status": "GDP_WEB_RELEASE_NOT_YET_VISIBLE",
                           "growth_score": None}
            continue
        e = rows[ccy]
        value, unit = e["reported_value"], e["reported_unit"]
        if unit == "PERCENT_SAAR_ANNUALIZED":
            require(ccy == "USD" and value > -100, "GDP annualization mismatch")
            qoq = 100.0 * ((1.0 + value / 100.0) ** 0.25 - 1.0)
            conversion = "US_SAAR_RATE_CONVERTED_TO_NONANNUALIZED_QOQ"
        else:
            require(unit.startswith("PERCENT_QOQ_"), "unsupported GDP horizon")
            qoq = value
            conversion = "AS_REPORTED_NONANNUALIZED_QOQ"
        result[ccy] = {
            "status": "OFFICIAL_WEB_STATEMENT_RESEARCH_NOT_PIT_CERTIFIED",
            "quarter": e["reference_quarter"], "published_on": e["publisher_release_day"],
            "available_from_utc": e["conservative_available_from_utc"],
            "source_url": e["source_url"], "publication_stage": e["publication_stage"],
            "reported_value": value, "reported_unit": unit,
            "descriptive_qoq_nonannualized_pct": qoq, "conversion": conversion,
            "sports_adjusted_not_directly_comparable": "SPORTS" in unit,
            "historical_pit_training_vintages_certified": False,
            "growth_score": None,
        }
    return result


def build(series, heatmap, registry, *, as_of):
    day = date.fromisoformat(as_of)
    require(heatmap.get("schema_version") == "GMFQ_MACRO_HEATMAP_V1",
            "thermometer schema drift")
    require(registry.get("scope", {}).get("core_series_count") == 16 and
            set(registry.get("series", {})) ==
            {f"{c}.{d}" for c in FX for d in PILLARS},
            "16 registered source slots required")
    require(set(FX) <= set(series) and
            set(FX) <= set(heatmap.get("currencies", {})), "G8 source coverage missing")
    features = {}
    for c in FX:
        for dim in PILLARS:
            entry = registry["series"][f"{c}.{dim}"]
            rid = ((entry.get("historical_replay_evidence") or {})
                   .get("macro_series_id") or entry["series_id"] + "_history_value")
            hits = [x for x in series[c] if isinstance(x, dict) and x.get("id") == rid]
            require(len(hits) == 1, f"missing/duplicated registered history {c}.{dim}")
            features[f"{c}.{dim}"] = pillar_feature(
                c, dim, entry, hits[0], heatmap["currencies"][c][dim], day)
    growth = growth_research(day)
    scored = sum(x["research_robust_z"] is not None for x in features.values())
    receipt = {
        "schema": SCHEMA, "checked_as_of": as_of,
        "status": "OBSERVED_G8_RESEARCH_FEATURES_NOT_CERTIFIED_MACRO_MODEL",
        "source_class": "TODAY_REVISED_OBSERVATIONS_NOT_REPLAYABLE_HISTORICAL_PIT",
        "inflation_labour": features,
        "growth_quarterly_gdp_web": growth,
        "summary": {
            "g8_currencies": 8, "economic_dimension_slots": 24,
            "registered_inflation_labour_slots": len(features),
            "descriptive_research_z_available": scored,
            "descriptive_research_z_unavailable": 16 - scored,
            "growth_web_observations_visible": sum(
                x["status"] == "OFFICIAL_WEB_STATEMENT_RESEARCH_NOT_PIT_CERTIFIED"
                for x in growth.values()),
            "growth_scores_computed": 0, "fx_strength_scores_computed": 0,
        },
        "current_values_are_not_verified_first_release_vintages": True,
        "no_cross_country_rank_or_mixed_frequency_aggregation": True,
        "no_inference_from_inflation_pressure_to_fx_direction": True,
        "safe_to_publish_new_D": False, "safe_to_update_pair_theses": False,
        "safe_to_use_for_beta": False, "safe_to_use_for_forward": False,
        "writes_live_data": False,
    }
    receipt["input_fingerprint_sha256"] = hashlib.sha256(
        json.dumps({"as_of": as_of, "features": features, "growth": growth},
                   sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return receipt


def run(*, root=ROOT, as_of=None):
    day = as_of or datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
    load = lambda p: json.loads(p.read_text(encoding="utf-8"))
    return build(load(root / "live_data/sections/MACRO_SERIES.json"),
                 load(root / "live_data/sections/MACRO_THERMOMETER_DATA.json"),
                 load(root / "validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json"),
                 as_of=day)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    if args.output:
        require(args.output.resolve().is_relative_to(Path("/tmp")),
                "research artifacts must stay in /tmp")
    result = run(as_of=args.as_of)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    print(json.dumps({"status": result["status"], **result["summary"],
                      "safe_to_publish_new_D": False}, sort_keys=True))


if __name__ == "__main__":
    main()
