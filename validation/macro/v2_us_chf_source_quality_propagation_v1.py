#!/usr/bin/env python3
"""USD CPI gap and CHF SECO rounding -> existing domestic Macro V2 RESEARCH.

This is NOT historical point-in-time model training. The existing shadow
candidate uses revised-source information. We stress source quality *outside*
that candidate without overwriting its scores, FX pairs, or source registry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    FORMULA, activity_class, price_class, run as candidate_run,
)
from validation.macro.v2_us_cpi_prior24_issuer_revised_sensitivity_v1 import (
    audit as usd_issuer_audit,
)
from validation.macro.v2_chf_seco_first_month_rounded_alternative_v1 import (
    audit as chf_seco_audit,
)

SCHEMA = "GMFQ_MACRO_V2_US_CHF_SOURCE_QUALITY_PROPAGATION_RESEARCH_V1"
CANDIDATE_DATE = "2026-10-27"
STRESS_WEIGHTS = (0.25, 0.50, 0.75)


def need(valid, why):
    if not valid:
        raise ValueError("MACRO_US_CHF_SOURCE_PROPAGATION_REJECTED: " + why)


def finite(z):
    return type(z) in (int, float) and math.isfinite(z)


def evaluate(candidate, usd, chf):
    need(candidate.get("formula_version") == FORMULA
         and candidate.get("economic_as_of") == CANDIDATE_DATE
         and candidate.get("status") == "EXPLICIT_8_COUNTRY_MACRO_CANDIDATE_RESEARCH_NO_PIT_NO_FX"
         and candidate.get("safe_to_publish_D") is False
         and candidate.get("safe_to_update_pair_theses") is False
         and candidate.get("summary", {}).get("FX_scores_produced") == 0
         and candidate.get("summary", {}).get("D_json_rebuilt") is False,
         "only unchanged unpromoted domestic formula candidate")
    economies = candidate.get("countries", {})
    need(set(economies) == {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"},
         "expected exactly eight original domestic research economies")
    for c, row in economies.items():
        need(row.get("FX_strength_candidate") is None
             and row.get("eligible_to_recalculate_28_pairs") is False,
             "research axis promoted into FX or pair ranking: " + c)

    need(usd.get("status") ==
         "US_CPI_24_PRECEDING_PUBLISHED_VINTAGE_SENSITIVITY_RESEARCH_ONLY"
         and usd.get("source_2025_10_all_items_not_published") is True
         and usd.get("24_prior_observed_not_24_consecutive") is True
         and usd.get("comparison_first_issue_vs_asof_revised_never_full_PIT") is True
         and usd.get("safe_to_publish_D_json") is False
         and usd.get("safe_to_recalculate_28_pairs") is False,
         "USD issuer-month evidence cannot become a strict 24-month PIT series")
    us = usd["summary"]
    need(us.get("official_published_prior_months") == 24
         and us.get("prior_calendar_months") == 25
         and us.get("missing_prior_month") == "2025-10"
         and us.get("issuer_original_day_binary_certifications") == 0,
         "USD BLS missing-month or first-day quality identity changed")
    issuer = us["issuer_month_candidate_robust_z"]["clipped_z"]
    revised = us["asof_revised_series_robust_z"]["clipped_z"]
    need(finite(issuer) and finite(revised) and
         math.isclose(issuer-revised, us["robust_z_candidate_minus_revised"],
                      abs_tol=1e-9, rel_tol=0),
         "USD independent issuer-vs-revised source calculation disagreement")
    need(all(economies["USD"]["source_quality_details"][k]["is_estimate"]
             for k in ("inflation", "labour"))
         and economies["USD"]["FX_strength_candidate"] is None,
         "USD existing candidate has no certified original-source strength")
    us_classes = [price_class(issuer), price_class(revised)]

    need(chf.get("schema") ==
         "GMFQ_MACRO_V2_CHF_25_MONTH_FIRST_SECO_ROUNDED_ISSUER_ALTERNATIVE_V1"
         and chf.get("safe_to_publish_new_D") is False
         and chf.get("historical_24_SNB_exact_first_release_percentages_unavailable") is True,
         "SECO issued rounded series cannot replace SNB exact vintage")
    ch = chf["statistical_research"]
    summary = chf["summary"]
    need(ch.get("24_prior_calendar_months_present_for_alternative_metric") is True
         and ch.get("24_prior_observations_from_FIRST_MONTH_WEB_REPORTS") is True
         and summary.get("official_PDF_raw_bytes_SHA_captured_now") == 21
         and summary.get("original_PDF_bytes_still_missing_despite_indexed_text") == 4
         and summary.get("separate_new_SNB_canonical_first_release_history_periods") == 0,
         "CHF original source quality changed")
    envelope = ch["hypothetical_unrounded_SECO_precision_envelope"]
    lo, hi = envelope["descriptive_robust_z_clipped_conservative_interval"]
    rounded = ch["descriptive_robust_z_of_rounded_first_SECO_rates"]
    need(all(finite(z) for z in (lo, hi, rounded))
         and -3 <= lo <= rounded <= hi <= 3
         and envelope["rounding_half_width_percentage_points"] == 0.05
         and envelope["pre_rounding_rates_observed_or_recovered"] is False
         and envelope["exact_SNB_amarbma_vintages_reconstructed"] is False
         and envelope["safe_for_macro_score"] is False,
         "CHF SECO uncertainty cannot assert hypothetical precision")
    g = economies["CHF"]["growth_within_history_z"]
    baseline_labour_tightness = economies["CHF"]["unemployment_tightness_within_history_z"]
    baseline_activity = economies["CHF"]["domestic_activity_candidate_z"]
    need(finite(g) and finite(baseline_labour_tightness) and finite(baseline_activity)
         and math.isclose(baseline_activity, .5*(g+baseline_labour_tightness),
                          rel_tol=0, abs_tol=1e-9),
         "CHF candidate's existing 50/50 research model changed")
    # The source alternative reports unemployment: invert its sign for
    # tightness. This is a HYPOTHETICAL different statistical source, not
    # an update to the historical precise SNB first releases.
    fixed = [0.5*g-0.5*hi, 0.5*g-0.5*lo]
    corners = [weight*g-(1-weight)*unemployment
               for weight in (STRESS_WEIGHTS[0], STRESS_WEIGHTS[-1])
               for unemployment in (lo, hi)]
    both = [min(corners), max(corners)]
    # Bilinear in (weight, unemployment), hence extrema on rectangle corners.
    need(all(math.isfinite(z) for z in fixed+both),
         "finite CHF source/weight uncertainty interval required")
    uncertain_source_class = activity_class(fixed[0]) != activity_class(fixed[1])
    uncertain_joint_class = activity_class(both[0]) != activity_class(both[1])
    return {
        "schema": SCHEMA,
        "status": "TWO_MISSING_CORE_SOURCE_QUALITY_STRESSED_NO_PIT_FX_PROMOTION",
        "research_as_of": CANDIDATE_DATE,
        "USD_inflation": {
            "canonical_source": "CPIAUCSL_SA_INDEX_YOY_NOT_HEADLINE_NSA",
            "issuer_month_current_research_z": issuer,
            "current_revised_research_z": revised,
            "issuer_minus_revised_z": issuer-revised,
            "same_descriptive_inflation_class_for_two_non_PIT_sources":
                us_classes[0] == us_classes[1],
            "classes": us_classes,
            "training_observations": 24,
            "training_calendar_months": 25,
            "unpublished_period": "2025-10",
            "first_release_day_original_binary_certified": False,
            "strict_consecutive_PIT_training_eligible": False,
            "inflation_is_separate_from_domestic_activity": True,
            "can_replace_candidate_inflation_z": False,
        },
        "CHF_labour": {
            "source_alternative": "FIRST_REPORTED_SECO_ROUNDED_NOT_SNB_FIRST_EXACT",
            "official_rounded_seco_labour_z": rounded,
            "hypothetical_precise_seco_unemployment_z_bounds": [lo, hi],
            "revised_snb_labour_tightness_z_from_original_candidate":
                baseline_labour_tightness,
            "original_candidate_activity_z_not_changed": baseline_activity,
            "hypothetical_fixed_50_50_activity_interval": fixed,
            "hypothetical_25_to_75_growth_weight_activity_interval": both,
            "fixed_weight_class_not_guaranteed_by_print_precision": uncertain_source_class,
            "joint_weight_and_print_precision_class_not_guaranteed":
                uncertain_joint_class,
            "source_can_be_equated_to_original_SNB_precise_series": False,
            "seco_original_first_report_pdf_bytes_downloaded_now": 21,
            "seco_2024_report_text_index_only": 4,
            "exact_historical_snb_source_day_vintages": 0,
            "safe_to_replace_candidate_labour_axis": False,
        },
        "summary": {
            "residual_source_quality_cases": 2,
            "candidate_macro_scores_authorized": 0,
            "pair_rankings_recomputed": 0,
            "source_day_training_vintage_series_certified": 0,
            "unchanged_candidate_form": FORMULA,
        },
        "safe_to_publish_new_D": False,
        "safe_to_recalculate_28_pairs": False,
        "safe_for_beta": False,
        "safe_for_forward": False,
        "writes_live_data": False,
    }


def run():
    obj = evaluate(candidate_run(as_of=CANDIDATE_DATE),
                   usd_issuer_audit(), chf_seco_audit())
    obj["receipt_sha256"] = hashlib.sha256(json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.out:
        need(args.out.resolve().is_relative_to(Path("/tmp")),
             "only temporary research receipts, no live data")
    obj = run()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n",
                            encoding="utf-8")
    print(json.dumps({
        "status": obj["status"],
        "USD": obj["USD_inflation"],
        "CHF": obj["CHF_labour"],
        "summary": obj["summary"],
        "safe_to_publish_new_D": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
