#!/usr/bin/env python3
"""G8 quarterly GDP: prior-only descriptive Growth features from web statements.

This is a *reproducible shadow calculation*, NOT first-day source-byte PIT
certification, NOT an economic strength/risk/cycle score and NOT a new D.json.

Use 13 consecutive QUARTERS of attested initial publisher statements:
12 PRIOR quarters (training) and the current first statement (held out).
Later published revisions remain separately visible; they must never leak
into the first-statement normalization. The earliest time usable here is the
calendar day AFTER the publisher release because intraday clocks are unproven.

GBP/EUR/GDP family unit definitions and country revisions are not inherently
equivalent. EUR population continuity and CHF sports/flash adjustments remain
conspicuously qualified. No FX ranking / Beta / Forward promotion.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from validation.macro.v2_g8_gdp_unified_web_research_v1 import unified_research_rows
from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate

SCHEMA = "GMFQ_MACRO_V2_G8_GDP_INITIAL_WEB_GROWTH_DESCRIPTIVE_V1"
FX = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
TRAIN = 12
CLIP = 3.0
UNIT = {
    "USD": {"PERCENT_SAAR_ANNUALIZED"},
    "EUR": {"PERCENT_QOQ_SA_CALENDAR"},
    "GBP": {"PERCENT_QOQ_SA"},
    "JPY": {"PERCENT_QOQ_SA"},
    "CHF": {"PERCENT_QOQ_SA_CALENDAR", "PERCENT_QOQ_SA_CALENDAR_NO_SPORTS",
            "PERCENT_QOQ_SA_CALENDAR_SPORTS",
            "PERCENT_QOQ_FLASH_ADJUSTMENT_UNSPECIFIED"},
    "CAD": {"PERCENT_QOQ_SA"},
    "AUD": {"PERCENT_QOQ_SA_CHAIN_VOLUME"},
    "NZD": {"PERCENT_QOQ_SA_CHAIN_VOLUME_PRODUCTION"},
}

def check(ok, reason):
    if not ok:
        raise ValueError("MACRO_GDP_RESEARCH_REJECTED: " + reason)

def qidx(q):
    match = re.fullmatch(r"(20\d{2})Q([1-4])", str(q))
    check(match is not None, "invalid quarter")
    return int(match[1]) * 4 + int(match[2]) - 1

def qlabel(i):
    return f"{i // 4:04d}Q{i % 4 + 1}"

def utc(iso):
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError) as err:
        raise ValueError("MACRO_GDP_RESEARCH_REJECTED: invalid cutoff") from err
    check(d.tzinfo is not None and d.utcoffset() == timedelta(0),
          "cutoff must be UTC offset aware")
    return d

def asof_visible(row):
    # Historical original-day bytes and exact clocks are not verified.
    return datetime.combine(date.fromisoformat(row["publisher_release_day"]) +
                            timedelta(days=1), datetime.min.time(), timezone.utc)

def nonannualized(row):
    c, val, unit = row["currency"], row["reported_value"], row["reported_unit"]
    check(c in UNIT and unit in UNIT[c], "unexpected currency or GDP metric/horizon")
    check(type(val) in (int, float) and math.isfinite(val), "GDP value must be finite")
    if unit == "PERCENT_SAAR_ANNUALIZED":
        check(c == "USD" and val > -100, "invalid US annualized GDP growth")
        return 100.0 * ((1.0 + val / 100.0) ** 0.25 - 1.0)
    return float(val)

def receipt(rows, *, as_of):
    cutoff = utc(as_of)
    # Recheck the upstream issuer, release sequence and no unauthorized scores.
    canonical = validate(rows)
    selected, revisions = {}, {}
    for r in canonical:
        if asof_visible(r) > cutoff:
            continue
        c = r["currency"]
        check(c in FX and r["eligible_for_macro_scoring"] is False and
              r["PIT_training_vintage_certified"] is False,
              "publisher statement presented as PIT approved")
        check(r["conservative_available_from_utc"] == asof_visible(r).isoformat(),
              "publisher day and conservative visible timestamp differ")
        key = (c, r["reference_quarter"])
        if r["stage_order"] == 0:
            check(key not in selected, "duplicate initial statement")
            selected[key] = r
        else:
            revisions.setdefault(key, []).append(r)
    features = {}
    for c in FX:
        first = {qidx(q): row for (ccy, q), row in selected.items() if ccy == c}
        check(first, "no initial observed GDP source for " + c)
        current = max(first)
        heldout = first[current]
        quarter_indices = list(range(current - TRAIN, current + 1))
        missed = [qlabel(i) for i in quarter_indices if i not in first]
        item = {
            "currency": c, "status": "INSUFFICIENT_CONSECUTIVE_INITIAL_WEB_QUARTERS",
            "latest_initial_period": qlabel(current),
            "latest_first_web_release_day": heldout["publisher_release_day"],
            "latest_source_url": heldout["source_url"],
            "latest_reported_value": heldout["reported_value"],
            "latest_reported_unit": heldout["reported_unit"],
            "latest_nonannualized_qoq_pct": nonannualized(heldout),
            "current_initial_value_excluded_from_training": True,
            "training_prior_quarters_required": TRAIN,
            "training_window_start": qlabel(current - TRAIN),
            "training_window_end": qlabel(current - 1),
            "missing_required_reference_quarters": missed,
            "research_robust_growth_z": None,
            "research_growth_velocity_pp_per_quarter": None,
            "research_growth_acceleration_pp_per_quarter_sq": None,
            "historical_original_publisher_day_bytes_certified": False,
            "current_data_not_certified_for_intraday_PIT": True,
            "actual_PIT_backtest_eligible": False,
            "numeric_model_growth_score": None,
            "safe_to_promote_growth_score": False,
            "safe_to_update_28_pairs": False,
        }
        # Keep within-currency measurement caveats separate from a math failure.
        if not missed:
            trailing = [first[i] for i in quarter_indices]
            units = sorted({r["reported_unit"] for r in trailing})
            population = sorted({r.get("population_reference", "NOT_PINNED")
                                 for r in trailing}) if c == "EUR" else []
            quality_issues = []
            if c == "EUR" and (len(population) != 1 or "NOT_PINNED" in population):
                quality_issues.append("EURO_AREA_POPULATION_DEFINITION_NOT_UNIFORM_OR_UNPINNED")
            if c == "CHF" and len(units) != 1:
                quality_issues.append("SWISS_INITIAL_GDP_SPORTS_FLASH_DEFINITION_MIXED")
            samples = [nonannualized(row) for row in trailing]
            train = samples[:-1]
            med = statistics.median(train)
            mad = statistics.median(abs(x - med) for x in train)
            if mad > 1e-9:
                raw_z = (samples[-1] - med) / (1.4826 * mad)
                check(math.isfinite(raw_z), "nonfinite GDP research intensity")
                v = samples[-1] - samples[-2]
                pv = samples[-2] - samples[-3]
                item.update({
                    "status": ("DESCRIPTIVE_INITIAL_WEB_GROWTH_Z_DEFINITION_CAVEAT"
                               if quality_issues else
                               "DESCRIPTIVE_INITIAL_WEB_GROWTH_Z_NOT_MODEL_CERTIFIED"),
                    "historical_first_web_observations_used": TRAIN,
                    "training_median_nonannualized_qoq_pct": med,
                    "training_mad_nonannualized_qoq_pct": mad,
                    "research_robust_growth_z_unclipped": raw_z,
                    "research_robust_growth_z": max(-CLIP, min(CLIP, raw_z)),
                    "research_growth_velocity_pp_per_quarter": v,
                    "research_growth_acceleration_pp_per_quarter_sq": v - pv,
                    "training_first_web_unit_variants": units,
                    "population_reference_variants": population,
                    "growth_definition_caveats": quality_issues,
                    "economic_comparability_quality":
                        "MIXED_OR_UNVERIFIED_MEASUREMENT_DEFINITION"
                        if quality_issues else
                        "SAME_WITHIN_COUNTRY_REPORTED_UNIT_RESEARCH_ONLY",
                })
            else:
                item["status"] = "NO_GDP_RESEARCH_Z_ZERO_MEDIAN_ABSOLUTE_DEVIATION"
        versions = sorted(revisions.get((c, qlabel(current)), []),
                          key=lambda r: r["stage_order"])
        if versions:
            latest = versions[-1]
            item["latest_visible_revision"] = {
                "publisher_release_day": latest["publisher_release_day"],
                "stage_order": latest["stage_order"],
                "reported_value": latest["reported_value"],
                "reported_unit": latest["reported_unit"],
                "nonannualized_qoq_pct": nonannualized(latest),
                "NOT_used_to_train_initial_web_z": True,
            }
        else:
            item["latest_visible_revision"] = None
        features[c] = item
    zcount = sum(x["research_robust_growth_z"] is not None for x in features.values())
    caveated = sum(bool(x.get("growth_definition_caveats")) for x in features.values())
    out = {
        "schema": SCHEMA, "as_of_utc": cutoff.isoformat(),
        "status": "G8_GDP_WEB_FIRST_STATEMENT_DESCRIPTIVE_RESEARCH_NOT_PIT_CERTIFIED",
        "features": features,
        "summary": {
            "g8_currencies": len(features),
            "growth_observational_features_computed": zcount,
            "growth_observational_features_with_definition_caveats": caveated,
            "model_growth_scores_computed": 0,
            "certified_historical_training_vintages": 0,
            "fx_pair_decisions_changed": 0,
        },
        "lookahead_guard": "FIRST_STATEMENTS_VISIBLE_ONLY_AFTER_NEXT_UTC_DAY",
        "training_excludes_latest_quarter_and_later_revisions": True,
        "historical_first_day_archival_bytes_certified": False,
        "revisions_not_merged_into_initial_release_sample": True,
        "macro_model_score_authorized": False,
        "can_publish_D_json": False,
        "can_use_for_beta": False,
        "can_use_for_forward": False,
        "can_recalculate_28_pairs": False,
        "writes_live_data": False,
    }
    out["receipt_sha256"] = hashlib.sha256(json.dumps(
        {"as_of": out["as_of_utc"], "features": features},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return out

def run(*, as_of=None):
    if as_of is None:
        as_of = (datetime.now(ZoneInfo("Europe/Rome")).astimezone(timezone.utc)
                 .isoformat())
    return receipt(unified_research_rows(), as_of=as_of)

if __name__ == "__main__":
    import argparse
    from pathlib import Path
    cli = argparse.ArgumentParser()
    cli.add_argument("--as-of")
    cli.add_argument("--out", type=Path)
    args = cli.parse_args()
    if args.out:
        check(args.out.resolve().is_relative_to(Path("/tmp")),
              "GDP research receipt must remain under /tmp")
    report = run(as_of=args.as_of)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
    print(json.dumps({"status": report["status"], **report["summary"],
                      "can_publish_D_json": False}, sort_keys=True))
