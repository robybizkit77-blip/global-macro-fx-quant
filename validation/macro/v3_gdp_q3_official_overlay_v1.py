"""Additive Q3 2026 official GDP source statements for Macro V3 only.

No inferred country GDP, first-release PIT training archive, currency scores,
or trade signals. The original Q2 comparison remains available as history.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from validation.macro.v2_g8_observed_feature_bridge_v1 import ROOT

LEDGER = ROOT / "validation/macro/fixtures/v3_gdp_q3_2026_official_web_updates_v1.json"
SCHEMA = "GMFQ_MACRO_V3_GDP_Q3_2026_OFFICIAL_WEB_RELEASES_V1"
PINNED = {
    "USD": ("2026Q3", "2026-10-29", 3.4, "PERCENT_SAAR_ANNUALIZED",
            "ADVANCE", "https://bea.gov/news/2026/gdp-advance-estimate-3rd-quarter-2026"),
    "EUR": ("2026Q3", "2026-10-30", 0.4, "PERCENT_QOQ_SA_CALENDAR",
            "PRELIMINARY_FLASH",
            "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-30102026-ap"),
    "GBP": ("2026Q3", "2026-11-12", 0.7, "PERCENT_QOQ_SA",
            "FIRST_QUARTERLY_ESTIMATE",
            "https://www.ons.gov.uk/economy/grossdomesticproductgdp/bulletins/"
            "gdpfirstquarterlyestimateuk/julytoseptember2026"),
    "CHF": ("2026Q3", "2026-11-16", 0.2, "PERCENT_QOQ_SA_CALENDAR_SPORTS",
            "PRELIMINARY_FLASH", "https://www.seco.admin.ch/en/newnsb/eOpqmkpQhZVQ"),
}
SECO_METHODOLOGY = ("https://www.seco.admin.ch/dam/en/sd-web/NuK0BItA1ufL/"
                    "2026-06-Factsheet-Quarterly-National-Accounts-SECO.pdf")
SECO_PRIOR = ("2026Q2", "2026-09-03", 1.5, "PERCENT_QOQ_SA_CALENDAR_SPORTS",
              "QUARTERLY_NATIONAL_ACCOUNTS", "https://www.seco.admin.ch/it/newnsb/xrrzuLVT1pbC")


def observed_q3_updates(as_of: str, *, evidence=None) -> dict:
    """Only verifiable releases known strictly before as_of; no look-ahead."""
    day = date.fromisoformat(as_of)
    ledger = evidence if evidence is not None else json.loads(LEDGER.read_text(encoding="utf-8"))
    expected = {
        "schema": SCHEMA,
        "policy": "OFFICIAL_PUBLISHER_RELEASE_VISIBLE_FROM_FOLLOWING_UTC_CALENDAR_DAY",
        "historical_point_in_time_archive_certified": False,
        "eligible_for_macro_scoring": False,
        "eligible_for_fx_signal": False,
    }
    if not isinstance(ledger, dict) or any(
        type(ledger.get(k)) is not type(v) or ledger.get(k) != v for k, v in expected.items()
    ):
        raise ValueError("MACRO_V3_GDP_Q3_OFFICIAL_EVIDENCE_BAD_POLICY")
    records = ledger.get("events")
    if not isinstance(records, list) or len(records) != len(PINNED):
        raise ValueError("MACRO_V3_GDP_Q3_OFFICIAL_EVIDENCE_BAD_COUNT")
    result = {}
    for r in records:
        if not isinstance(r, dict):
            raise ValueError("MACRO_V3_GDP_Q3_INVALID_EVENT")
        c = r.get("currency")
        keys = ("reference_quarter", "publisher_release_day", "reported_value",
                "reported_unit", "publication_stage", "source_url")
        observed = tuple(r.get(k) for k in keys)
        if c not in PINNED or c in result or observed != PINNED[c]:
            raise ValueError("MACRO_V3_GDP_Q3_SOURCE_VALUE_DATE_UNIT_DRIFT")
        if c == "CHF":
            prior = r.get("prior_documented_quarter")
            if (not isinstance(prior, dict) or tuple(prior.get(k) for k in keys) != SECO_PRIOR
                    or r.get("methodology_url") != SECO_METHODOLOGY):
                raise ValueError("MACRO_V3_GDP_Q3_SECO_COMPARISON_DRIFT")
        # Events are observable only after release, not from GDP quarter end.
        published = date.fromisoformat(r["publisher_release_day"])
        result[c] = None
        if day < published + timedelta(days=1):
            continue
        value = r["reported_value"]
        qoq = (100.0 * ((1.0 + value / 100.0) ** 0.25 - 1.0)
               if c == "USD" else value)
        result[c] = {
            "reference_quarter": r["reference_quarter"],
            "publisher_release_day": r["publisher_release_day"],
            "publisher_source": r["source_url"],
            "reported_value": value,
            "reported_unit": r["reported_unit"],
            "publication_stage": r["publication_stage"],
            "nonannualized_qoq_descriptive_pct": round(qoq, 6),
            "is_growth_strength_score": False,
            "national_definitions_are_not_fully_cross_country_equivalent": True,
            "later_revisions_not_identical_to_first_release": True,
            "historical_pit_training_vintages_certified": False,
        }
        if c == "CHF":
            # The Q2 detailed release uses the same definition as the Q3 flash.
            prior_quarter = {**result[c], **{k: prior[k] for k in keys[:-1]},
                             "publisher_source": prior["source_url"],
                             "nonannualized_qoq_descriptive_pct": prior["reported_value"]}
            result[c].update(
                prior_documented_quarter=prior_quarter,
                publisher_methodology=r["methodology_url"],
                comparison_uses_distinct_publisher_editions=True,
            )
    if set(result) != set(PINNED):
        raise ValueError("MACRO_V3_GDP_Q3_MISSING_SOURCE")
    return {c: v for c, v in result.items() if v is not None}
