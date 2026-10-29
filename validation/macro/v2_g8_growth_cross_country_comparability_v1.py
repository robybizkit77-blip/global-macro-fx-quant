#!/usr/bin/env python3
"""G8 real GDP: same-quarter QoQ levels versus *within-country* 12Q z.

Detects a demonstrable ranking fallacy, not currency/FX strength.
All source statements are first-WEB research, not independently certified
original publication-day bytes or a synchronized joint GDP vintage panel.
Never applies ranking, changes D.json, or evaluates forward FX prices.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import itertools
import json
import math
from pathlib import Path

from validation.macro.v2_g8_gdp_first_web_growth_features_v1 import (
    SCHEMA as GDP_SCHEMA, run as gdp_run, nonannualized,
)
from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    FORMULA, run as candidate_run,
)

SCHEMA = "GMFQ_MACRO_V2_G8_GDP_QOQ_VS_OWN_HISTORY_COMPARABILITY_AUDIT_V1"
CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD")
GDP_CUTOFF = "2026-10-28T23:59:59Z"
CANDIDATE_ASOF = "2026-10-27"
LATEST_QUARTER = "2026Q2"
# Frozen original statistical definitions, not authorizations to compare FX.
UNITS = {
    "USD": "PERCENT_SAAR_ANNUALIZED",
    "EUR": "PERCENT_QOQ_SA_CALENDAR",
    "GBP": "PERCENT_QOQ_SA",
    "JPY": "PERCENT_QOQ_SA",
    "CHF": "PERCENT_QOQ_SA_CALENDAR_SPORTS",
    "CAD": "PERCENT_QOQ_SA",
    "AUD": "PERCENT_QOQ_SA_CHAIN_VOLUME",
    "NZD": "PERCENT_QOQ_SA_CHAIN_VOLUME_PRODUCTION",
}
CAVEATS = {
    "EUR": ("EURO_AREA_POPULATION_DEFINITION_NOT_UNIFORM_OR_UNPINNED",),
    "CHF": ("SWISS_INITIAL_GDP_SPORTS_FLASH_DEFINITION_MIXED",),
}


def need(ok, why):
    if not ok:
        raise ValueError("GDP_G8_CROSS_COUNTRY_COMPARABILITY_REJECTED: " + why)


def value(x, name):
    need(type(x) in (int, float) and math.isfinite(x), name + " finite numeric")
    return float(x)


def direction(a, b, tol=1e-9):
    return 0 if abs(a - b) <= tol else (1 if a > b else -1)


def audit(gdp, candidate):
    need(gdp.get("schema") == GDP_SCHEMA
         and gdp.get("as_of_utc") == "2026-10-28T23:59:59+00:00"
         and gdp.get("status") ==
            "G8_GDP_WEB_FIRST_STATEMENT_DESCRIPTIVE_RESEARCH_NOT_PIT_CERTIFIED"
         and gdp.get("historical_first_day_archival_bytes_certified") is False
         and gdp.get("can_publish_D_json") is False
         and gdp.get("can_recalculate_28_pairs") is False
         and gdp.get("summary", {}).get("certified_historical_training_vintages") == 0,
         "GDP first-web receipt must not be promoted to PIT model")
    need(candidate.get("formula_version") == FORMULA
         and candidate.get("economic_as_of") == CANDIDATE_ASOF
         and candidate.get("safe_to_publish_D") is False
         and candidate.get("safe_to_update_pair_theses") is False
         and candidate.get("summary", {}).get("FX_scores_produced") == 0,
         "only original non-FX domestic research candidate")
    data = gdp.get("features")
    strength = candidate.get("countries")
    need(isinstance(data, dict) and set(data) == set(CURRENCIES)
         and isinstance(strength, dict) and set(strength) == set(CURRENCIES),
         "all G8 original GDP statements and original candidate required")
    rows = {}
    releases = []
    for c in CURRENCIES:
        x = data[c]
        y = strength[c]
        need(x.get("currency") == c and y.get("FX_strength_candidate") is None
             and y.get("eligible_to_recalculate_28_pairs") is False
             and x.get("latest_initial_period") == LATEST_QUARTER
             and x.get("latest_reported_unit") == UNITS[c]
             and x.get("training_prior_quarters_required") == 12
             and x.get("historical_first_web_observations_used") == 12
             and x.get("missing_required_reference_quarters") == []
             and x.get("current_initial_value_excluded_from_training") is True
             and x.get("actual_PIT_backtest_eligible") is False
             and x.get("numeric_model_growth_score") is None
             and x.get("safe_to_promote_growth_score") is False,
             c + " quarterly GDP sample, source or no-FX contract drift")
        caveats = tuple(x.get("growth_definition_caveats") or ())
        need(caveats == CAVEATS.get(c, ()), c + " GDP GDP population/sports caveat disappeared")
        raw = value(x.get("latest_reported_value"), c + " reported GDP")
        qoq = value(x.get("latest_nonannualized_qoq_pct"), c + " harmonized QoQ")
        expected = (100*((1+raw/100)**(.25)-1)
                    if c == "USD" else raw)
        need(math.isclose(qoq, expected, rel_tol=0, abs_tol=1e-10),
             c + " US SAAR-to-QoQ transform or direct QoQ identity changed")
        z = value(x.get("research_robust_growth_z"), c + " within-history Z")
        need(-3-1e-10 <= z <= 3+1e-10
             and math.isclose(z, value(y.get("growth_within_history_z"), c+" candidate z"),
                              rel_tol=0, abs_tol=1e-10),
             c + " GDP research z mismatch with V2 original candidate")
        day = date.fromisoformat(x["latest_first_web_release_day"])
        need(date(2026, 7, 1) < day <= date(2026, 10, 28),
             c + " first-web release date outside completed known Q2")
        releases.append(day)
        rows[c] = {
            "reference_quarter": LATEST_QUARTER,
            "first_statement_day": day.isoformat(),
            "original_reported_value": raw,
            "original_reported_unit": UNITS[c],
            "nonannualized_qoq_pct_research": qoq,
            "within_own_12_prior_quarters_z_research": z,
            "definition_warning": list(caveats),
            "historical_PIT_first_day_original_bytes_certified": False,
            "new_core_growth_score": None,
            "FX_direction": None,
        }

    pairs = {}
    counts = {"ORDER_INVERSION": 0, "ORDER_AGREEMENT": 0,
              "TIE_IN_AT_LEAST_ONE_REPRESENTATION": 0}
    caveated = 0
    for a, b in itertools.combinations(CURRENCIES, 2):
        qa, qb = rows[a], rows[b]
        raw = direction(qa["nonannualized_qoq_pct_research"],
                        qb["nonannualized_qoq_pct_research"])
        normalized = direction(qa["within_own_12_prior_quarters_z_research"],
                               qb["within_own_12_prior_quarters_z_research"])
        case = ("TIE_IN_AT_LEAST_ONE_REPRESENTATION" if raw == 0 or normalized == 0
                else "ORDER_INVERSION" if raw != normalized else "ORDER_AGREEMENT")
        counts[case] += 1
        issue = bool(qa["definition_warning"] or qb["definition_warning"])
        caveated += int(issue)
        pairs[a+"/"+b] = {
            "same_economic_quarter": True,
            "raw_qoq_diff_percentage_points": round(
                qa["nonannualized_qoq_pct_research"] -
                qb["nonannualized_qoq_pct_research"], 12),
            "within_history_z_difference_not_common_strength_units": round(
                qa["within_own_12_prior_quarters_z_research"] -
                qb["within_own_12_prior_quarters_z_research"], 12),
            "order_comparison": case,
            "definition_or_population_caveat": issue,
            "eligible_for_fx_strength_ranking": False,
            "joint_original_publisher_vintage_certified": False,
        }
    need(len(pairs) == 28 and sum(counts.values()) == 28,
         "all 28 cross-economy diagnostics required, including ties")
    need(len(releases) == 8 and min(releases) < max(releases),
         "Q2 economic quarter has staggered publication dates")
    return {
        "schema": SCHEMA,
        "status": "GDP_G8_QOQ_WITHIN_HISTORY_DIAGNOSTICS_NOT_FX_COMPARABILITY_CERTIFIED",
        "source_gdp_receipt_sha256": gdp["receipt_sha256"],
        "source_domestic_candidate_sha256": candidate["receipt_sha256"],
        "economic_reference_quarter": LATEST_QUARTER,
        "issuer_first_statement_days_span": {
            "first": min(releases).isoformat(),
            "last": max(releases).isoformat(),
            "calendar_days": (max(releases)-min(releases)).days,
        },
        "countries": rows,
        "all_28_GDP_representation_comparisons": pairs,
        "summary": {
            "economies": 8,
            "pairs_audited_for_descriptive_representation": 28,
            "within_history_vs_qoq_order_agreements": counts["ORDER_AGREEMENT"],
            "within_history_vs_qoq_order_inversions": counts["ORDER_INVERSION"],
            "pairs_with_order_ties": counts["TIE_IN_AT_LEAST_ONE_REPRESENTATION"],
            "pairs_with_EUR_or_CHF_definition_caveats": caveated,
            "distinct_issuer_first_web_release_days": len(set(releases)),
            "original_release_day_binary_certified_training_panels": 0,
            "eligible_cross_country_FX_strength_pairs": 0,
        },
        "GDP_is_real_activity_not_currency_valuation_or_CB_pricing": True,
        "same_quarter_does_not_equal_simultaneously_available": True,
        "own_history_z_cross_section_not_a_common_GDP_level_or_FX_strength": True,
        "EUR_population_and_CHF_sports_definition_breaks_not_silently_harmonized": True,
        "GDP_first_web_bytes_not_immutable_at_historical_release_instant": True,
        "no_cross_country_FX_predictive_validation_or_executable_return": True,
        "safe_to_publish_D": False,
        "safe_to_recalculate_28_pairs": False,
        "safe_for_beta": False,
        "safe_for_forward": False,
        "writes_live_data": False,
    }


def run():
    result = audit(gdp_run(as_of=GDP_CUTOFF),
                   candidate_run(as_of=CANDIDATE_ASOF))
    result["receipt_sha256"] = hashlib.sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode()).hexdigest()
    return result


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--out", type=Path)
    args = cli.parse_args()
    if args.out:
        need(args.out.resolve().is_relative_to(Path("/tmp")),
             "research-only GDP diagnostics may be written under /tmp only")
    obj = run()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(obj, indent=2, ensure_ascii=False)+"\n",
                            encoding="utf-8")
    print(json.dumps({"status": obj["status"], "summary": obj["summary"],
                      "GDP_comparison": {
                          k: {"qoq_pct": v["nonannualized_qoq_pct_research"],
                              "within_history_z": v["within_own_12_prior_quarters_z_research"]}
                          for k, v in obj["countries"].items()
                      }, "safe_to_publish_D": False}, sort_keys=True))


if __name__ == "__main__":
    main()
