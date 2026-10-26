#!/usr/bin/env python3
"""Preregister one G8 Growth GDP research target, distinct from faster activity proxies.

This is NOT a canonical Macro score, not the historical 2026-09-25 generator,
not a verified first-release dataset, and not a change to the 28 FX pair votes.
Each target is a *publisher/metric research plan* only. Official webpage identity
does not establish the historical release-day bytes or revision trail.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from validation.macro.v2_g8_growth_transform_proposal_gate_v1 import PINNED
from validation.macro.v2_shadow_features_v1 import ROOT, timestamp, require

SCHEMA = "GMFQ_G8_GROWTH_QUARTERLY_GDP_RESEARCH_TARGET_V1"
CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
QUARTERLY_GOAL = "REAL_GDP_TOTAL_SEASONALLY_ADJUSTED_QOQ_NOT_ANNUALIZED"
SOURCES = {
    "USD": ("U.S. Bureau of Economic Analysis", "BEA National Income and Product Accounts / real GDP",
            "https://www.bea.gov/data/gdp/gross-domestic-product",
            "US_ANNUALIZED_HEADLINE_NOT_QOQ", "GDP_EXPENDITURE_TOTAL"),
    "EUR": ("Eurostat", "namq_10_gdp Q SCA B1GQ real GDP volumes EA21/EA20 break",
            "https://ec.europa.eu/eurostat/databrowser/product/view/namq_10_gdp?lang=en",
            "EURO_AREA_MEMBERSHIP_VINTAGE_MUST_BE_PINNED", "GDP_EXPENDITURE_TOTAL"),
    "GBP": ("Office for National Statistics", "ABMI chained-volume seasonally-adjusted real GDP",
            "https://www.ons.gov.uk/economy/grossdomesticproductgdp/timeseries/abmi",
            "ONS_QOQ_FROM_SAME_VINTAGE_ABMI_LEVELS", "GDP_EXPENDITURE_TOTAL"),
    "JPY": ("Cabinet Office / ESRI Japan", "Quarterly estimates of GDP real seasonally-adjusted series",
            "https://www.esri.cao.go.jp/en/sna/data/sokuhou/files/2026/toukei_2026.html",
            "FIRST_AND_SECOND_PRELIMINARY_DISTINCT", "GDP_EXPENDITURE_TOTAL"),
    "CHF": ("State Secretariat for Economic Affairs (SECO)", "Quarterly real GDP seasonally/calendar and sport-event adjusted",
            "https://www.seco.admin.ch/en/gross-domestic-product",
            "SPORTS_ADJUSTMENT_CHOICE_PRE_REGISTERED_FOR_RESEARCH", "GDP_EXPENDITURE_TOTAL"),
    "CAD": ("Statistics Canada", "36-10-0104-01 quarterly real GDP market prices chained-dollar SAAR level",
            "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610010401",
            "SAAR_LEVEL_RATIO_QOQ_NOT_ANNUALIZED_RATE", "GDP_EXPENDITURE_TOTAL"),
    "AUD": ("Australian Bureau of Statistics", "National accounts seasonally adjusted chain-volume GDP",
            "https://www.abs.gov.au/statistics/economy/national-accounts/australian-national-accounts-national-income-expenditure-and-product/jun-2026",
            "OFFICIAL_GDP_QUARTER_QOQ_AVAILABLE", "GDP_EXPENDITURE_TOTAL"),
    "NZD": ("Stats NZ", "Quarterly production real GDP seasonally adjusted chain volume",
            "https://www.stats.govt.nz/information-releases/gross-domestic-product-june-2026-quarter/",
            "QOQ_VS_SAME_QUARTER_YOY_VS_ANNUAL_AVERAGE_MUST_NOT_MIX", "GDP_PRODUCTION_TOTAL"),
}
TRUSTED_DOMAINS = {
    "USD": "www.bea.gov", "EUR": "ec.europa.eu", "GBP": "www.ons.gov.uk",
    "JPY": "www.esri.cao.go.jp", "CHF": "www.seco.admin.ch",
    "CAD": "www150.statcan.gc.ca", "AUD": "www.abs.gov.au",
    "NZD": "www.stats.govt.nz",
}
# Publisher period-specific reference only, never training/PIT replay observations.
NZ_2026Q2_PUBLICATION_REFERENCE = {
    "publisher_release_day": "2026-09-17",
    "quarterly_qoq_pct": 0.2,
    "same_quarter_prior_year_yoy_pct": 2.6,
    "year_ended_average_annual_growth_pct": 1.7,
}

def quarter_index(q: str) -> int:
    m = re.fullmatch(r"(20[0-9]{2})Q([1-4])", str(q))
    require(m is not None, "quarter must have 20xxQ1..Q4 format")
    return int(m.group(1)) * 4 + int(m.group(2)) - 1


def research_qoq_from_same_vintage_levels(prior: dict, current: dict, *, cutoff: str) -> float:
    """Pure mathematics, caller-supplied snapshots; NEVER auto-admits source data."""
    until = timestamp(cutoff)
    require(isinstance(prior, dict) and isinstance(current, dict),
            "two GDP quarter-level records required")
    require(quarter_index(current.get("quarter")) -
            quarter_index(prior.get("quarter")) == 1,
            "QoQ needs consecutive calendar quarters")
    for name, row in (("prior", prior), ("current", current)):
        v = row.get("real_gdp_sa_level")
        require(type(v) in (int, float) and math.isfinite(v) and v > 0,
                name + " real GDP level must be finite positive")
        require(row.get("measure") == "REAL_GDP_TOTAL_SA_LEVEL",
                name + " cannot be annualized GDP growth or IP level")
        require(row.get("publication_stage") in ("FIRST", "REVISION"),
                name + " source release stage must be declared")
        require(timestamp(row.get("visible_at_utc")) <= until,
                name + " source data not yet available at cutoff")
        require(isinstance(row.get("source_snapshot_sha256"), str) and
                re.fullmatch(r"[0-9a-f]{64}", row["source_snapshot_sha256"]),
                name + " frozen dataset digest missing")
    require(prior["source_snapshot_sha256"] == current["source_snapshot_sha256"],
            "GDP quarters must come from the same dated published vintage")
    require(prior.get("publisher_dataset") == current.get("publisher_dataset") and
            isinstance(prior.get("publisher_dataset"), str) and
            prior["publisher_dataset"],
            "GDP levels use different series, economic definitions or transport")
    return 100.0 * (current["real_gdp_sa_level"] /
                    prior["real_gdp_sa_level"] - 1.0)


def audit():
    require(set(SOURCES) == set(PINNED) == set(CURRENCIES),
            "eight existing candidate identities must remain visible")
    require(set(TRUSTED_DOMAINS) == set(CURRENCIES),
            "eight official publisher source domains required")
    rows = []
    for ccy in CURRENCIES:
        publisher, dataset, url, caveat, family = SOURCES[ccy]
        link = urlparse(url)
        require(link.scheme == "https" and link.hostname == TRUSTED_DOMAINS[ccy]
                and link.username is None and link.password is None
                and link.query in ("", "lang=en", "pid=3610010401") and
                not link.fragment and dataset and publisher and caveat,
                ccy + " unverified official GDP target")
        old = PINNED[ccy]
        candidate_series, freq, unit, period, value, n, web, transform, family_old, relation = old
        require(freq in ("M", "Q") and transform in (
            "LEVEL_3M3M", "REPORTED_QOQ_RATE", "REPORTED_YOY_RATE"),
            "existing faster Growth candidate changed without review")
        rows.append({
            "currency": ccy,
            "primary_research_economic_target": QUARTERLY_GOAL,
            "primary_source_publisher": publisher,
            "primary_publisher_dataset_description": dataset,
            "primary_official_source_url": url,
            "primary_quarterly_measure_type": "GDP_REAL_SA_LEVEL_OR_OFFICIAL_NONANNUALIZED_QOQ",
            "primary_source_research_caveat": caveat,
            "economic_family": family,
            "preexisting_activity_candidate_source_id": candidate_series,
            "preexisting_activity_candidate_frequency": freq,
            "preexisting_activity_candidate_transform": transform,
            "preexisting_activity_candidate_economic_family": family_old,
            "preexisting_candidate_first_release_vintage_certified": False,
            "primary_quarterly_GDP_release_vintage_certified": False,
            "primary_quarterly_GDP_live_adapter_selected": False,
            "official_source_webpage_is_not_immutable_PIT_archive": True,
            "comparable_cross_country_growth_score_certified": False,
            "economic_growth_model_weights_approved": False,
            "pair_ranking_use_permitted": False,
        })
    require(len(rows) == 8 and len({r["primary_official_source_url"] for r in rows}) == 8,
            "eight unique publisher research references required")
    digest = hashlib.sha256(json.dumps(
        {"rows": rows, "nz_semantics": NZ_2026Q2_PUBLICATION_REFERENCE},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema": SCHEMA,
        "status": "EIGHT_GDP_RESEARCH_TARGETS_DESIGNATED_NOT_PIT_ADMITTED",
        "primary_economic_dimension": QUARTERLY_GOAL,
        "research_contract_sha256": digest,
        "rows": rows,
        "summary": {
            "quarterly_GDP_research_targets_documented": 8,
            "old_activity_proxies_retained_separately": 8,
            "official_primary_GDP_PIT_source_series_admitted": 0,
            "numeric_macro_scores_reconstructed": 0,
            "cross_currency_GDP_comparability_certified": False,
            "nz_growth_horizon_disambiguated": True,
        },
        "new_zealand_publisher_2026Q2_observation_semantics":
            NZ_2026Q2_PUBLICATION_REFERENCE,
        "exclusions": [
            "BEA annualized QoQ headline is not the non-annualized quarterly level change",
            "Quarterly SAAR GDP levels can use same-vintage ratios, never annualized rate as QoQ",
            "NZD 2.6% same-quarter YoY is NOT 0.2% QoQ or 1.7% year-ended average annual",
            "Euro area EA20/EA21 and CHF sports adjustment definitions remain explicit",
            "Preexisting monthly industrial production is a faster but narrower activity proxy",
            "Original historical release-day PIT datasets and independent formula validation are still missing",
        ],
        "can_replace_2026_09_25_D_macro": False,
        "can_publish_new_growth_scores": False,
        "can_change_28_pair_theses": False,
        "can_use_for_beta": False,
        "can_use_for_forward_restarts": False,
        "writes_live_data": False,
    }


def markdown(r):
    s = r["summary"]
    lines = [
        "# Macro V2 - Quarterly GDP target for 8 G8 currencies",
        "",
        "**Research source choice ONLY. Baseline 2026-09-25 is unchanged.**",
        "",
        "| FX | Preferred broad-economy Growth target | Publisher | Existing faster source (NOT GDP) | Source caveat |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in r["rows"]:
        lines.append(
            f"| {row['currency']} | Quarterly real GDP QoQ, SA (not annualized) | "
            f"{row['primary_source_publisher']} | "
            f"{row['preexisting_activity_candidate_source_id']} | "
            f"{row['primary_source_research_caveat']} |"
        )
    lines += [
        "",
        "No source vintage is promoted. No scores, pair rankings, historical Beta, "
        "forward tests, or live data are changed.",
        "",
        "**NZD June 2026**: QoQ +0.2%; same-quarter YoY +2.6%; annual-average +1.7%. "
        "Three different official measures, none substituted for the others.",
        "",
        "## Next actual work",
        "1. Pin an exact quarterly real GDP data-series dimension and its units per publisher.",
        "2. Acquire original release-day first values, revisions and consecutive quarter levels.",
        "3. Prove same-vintage exact QoQ across eight countries, with explicit SAAR and regime controls.",
        "4. Test comparability, score method and independent OOS before any new Macro/FX release.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    for dest in (args.out, args.markdown):
        if dest is not None:
            require(dest.resolve().is_relative_to(Path("/tmp")),
                    "research-only outputs must stay under /tmp")
    receipt = audit()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(receipt) + "\n")
    print(json.dumps({"status": receipt["status"], **receipt["summary"],
                      "can_replace_2026_09_25_D_macro": False}, sort_keys=True))


if __name__ == "__main__":
    main()
