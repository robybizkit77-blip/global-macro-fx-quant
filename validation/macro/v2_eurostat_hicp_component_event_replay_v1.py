#!/usr/bin/env python3
"""Eurostat September 2026 HICP flash-vs-detailed components; shadow research ONLY.

Report two official publication *dates* with next-UTC-day conservative gates:
the publisher's intraday clock is NOT independently verified. Ten comparable
annual-rate lines are not ten release events. Final-only contribution estimates
must not be treated as differences against unavailable flash contributions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp

PATH = ROOT / "validation/macro/fixtures/v2_eurostat_hicp_sep2026_components_flash_final.json"
PREVIOUS = ROOT / "validation/macro/MACRO_V2_EUR_HICP_SEP_2026_RELEASE_SEQUENCE_2026-10-24.json"
SCHEMA = "GMFQ_MACRO_V2_EUROSTAT_HICP_COMPONENT_FLASH_FINAL_SEP_2026_V1"
RECEIPT = "GMFQ_MACRO_V2_EUROSTAT_HICP_COMPONENTS_EVENT_REPLAY_V1"
FLASH_URL = "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-02102026-ap"
FINAL_URL = "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-16102026-ap"
# Independently hard-pinned to the two period-specific Eurostat web tables.
# Every numeric number is an HICP year-over-year percentage, NOT a contribution
# to headline and NOT a monthly change.
EXPECTED = (
    ("ALL_ITEMS_HICP", 3.8, 3.8),
    ("EX_ENERGY_FOOD_ALCOHOL_TOBACCO", 2.5, 2.5),
    ("EX_ENERGY", 2.3, 2.3),
    ("EX_ENERGY_UNPROCESSED_FOOD", 2.2, 2.2),
    ("FOOD_ALCOHOL_TOBACCO", 1.4, 1.3),
    ("PROCESSED_FOOD_ALCOHOL_TOBACCO", 0.4, 0.4),
    ("UNPROCESSED_FOOD", 4.0, 4.0),
    ("ENERGY", 18.8, 18.9),
    ("NON_ENERGY_INDUSTRIAL_GOODS", 1.1, 1.1),
    ("SERVICES", 3.2, 3.2),
)
EXPECTED_CONTRIBUTIONS = (
    ("ENERGY", 1.71),
    ("SERVICES", 1.52),
    ("NON_ENERGY_INDUSTRIAL_GOODS", 0.29),
    ("FOOD_ALCOHOL_TOBACCO", 0.25),
)


def _source_event(event, date_expected, url_expected):
    require(event.get("published_on") == date_expected and
            event.get("published_at_local_verified") is None and
            event.get("source_url") == url_expected, "Eurostat official event identity drift")
    parsed = urlsplit(url_expected)
    require(parsed.hostname == "ec.europa.eu" and parsed.scheme == "https" and
            not parsed.query and not parsed.fragment, "official EU web page needed")
    floor = datetime.combine(date.fromisoformat(date_expected) + timedelta(days=1),
                             datetime.min.time(), tzinfo=timezone.utc)
    require(timestamp(event.get("conservative_visible_from_utc")) == floor,
            "date-only Eurostat source cannot obtain invented same-day clock")
    return floor


def validate(fixture, original):
    require(fixture.get("schema") == SCHEMA and fixture.get("review_as_of") == "2026-10-24" and
            (fixture.get("publisher"), fixture.get("currency"), fixture.get("pillar"),
             fixture.get("reference_period"), fixture.get("geography"), fixture.get("unit")) ==
            ("Eurostat", "EUR", "inflation", "2026-09", "EA21", "percent YoY"),
            "source/metric identity or observation period drift")
    require(fixture.get("source_metric") ==
            "HICP annual rate by selected aggregate (prc_hicp_minr)",
            "do not conflate HICP annual rates with MoM/contributions")
    for key in ("publisher_page_bytes_from_original_release_archived",
                "official_intraday_release_clock_certified",
                "full_revision_vintage_chain_certified", "eligible_for_macro_score",
                "eligible_for_backtest", "safe_to_publish_new_D",
                "safe_to_update_pair_theses", "writes_live_data"):
        require(fixture.get(key) is False, "false research/evidence promotion " + key)

    flash_gate = _source_event(fixture["flash"], "2026-10-02", FLASH_URL)
    detailed_gate = _source_event(fixture["detailed"], "2026-10-16", FINAL_URL)
    require(flash_gate < detailed_gate, "flash must precede detailed publication")
    require(original.get("schema") ==
            "GMFQ_MACRO_V2_EUR_HICP_SEP_2026_OFFICIAL_WEB_RELEASE_SEQUENCE_V1" and
            original.get("full_historical_first_release_chain_certified") is False and
            original.get("official_page_bytes_archived") is False,
            "original Eurostat headline event ledger was promoted/changed")
    require(original.get("series_id") == "EA_HICP_HEADLINE_YOY_history_value"
            and original.get("reference_period") == "2026-09",
            "headline/period source identity drift")
    old_rows = original.get("observations")
    require(len(old_rows) == 2 and
            [(x["event_type"], x["published_on"], x["source_url"], x["value"])
             for x in old_rows] ==
            [("FLASH_ESTIMATE", "2026-10-02", FLASH_URL, 3.8),
             ("DETAILED_RELEASE", "2026-10-16", FINAL_URL, 3.8)],
            "crosswalk's published headline source evidence differs")

    measures = fixture.get("components")
    require(isinstance(measures, list) and len(measures) == len(EXPECTED),
            "ten HICP yearly-rate metrics required")
    parsed = []
    for row, expected in zip(measures, EXPECTED):
        component, first, last = expected
        require(row.get("component_id") == component and
                isinstance(row.get("label"), str) and bool(row["label"].strip()),
                "component identity or label missing")
        for key, value in (("flash_percent_yoy", first), ("detailed_percent_yoy", last)):
            actual = row.get(key)
            require(type(actual) in (float, int) and math.isfinite(actual) and
                    actual == value, "official HICP component rate changed without re-audit")
        parsed.append({"component_id": component, "label": row["label"],
                       "flash_percent_yoy": first, "detailed_percent_yoy": last,
                       "difference_pp": round(last - first, 1)})
    require(sum(r["difference_pp"] != 0 for r in parsed) == 2 and
            next(r for r in parsed if r["component_id"] == "ALL_ITEMS_HICP")
            ["difference_pp"] == 0,
            "2 underlying component changes and headline equality must be retained")
    contributions = fixture.get("final_only_contributions")
    require(isinstance(contributions, list) and
            len(contributions) == len(EXPECTED_CONTRIBUTIONS),
            "four detailed-only contributions required")
    for value, expected in zip(contributions, EXPECTED_CONTRIBUTIONS):
        component, pp = expected
        require(value.get("component_id") == component and
                value.get("value_pp") == pp and type(value.get("value_pp")) in (int, float)
                and value.get("publication_stage") == "DETAILED_ONLY" and
                value.get("metric") == "PERCENTAGE_POINT_CONTRIBUTION_TO_HEADLINE" and
                value.get("source_url") == FINAL_URL,
                "do not treat final-only contribution as flash-revised annual rate")
    return flash_gate, detailed_gate, parsed


def replay(as_of, fixture=None, original=None):
    if fixture is None:
        fixture = json.loads(PATH.read_text(encoding="utf-8"))
    if original is None:
        original = json.loads(PREVIOUS.read_text(encoding="utf-8"))
    flash_gate, detailed_gate, parsed = validate(fixture, original)
    cutoff = timestamp(as_of)
    has_flash = cutoff >= flash_gate
    has_detailed = cutoff >= detailed_gate
    stage = ("DETAILED_PUBLICATION" if has_detailed else
             "FLASH_ESTIMATE" if has_flash else "NOT_YET_VISIBLE")
    rows = []
    for r in parsed:
        rows.append({
            "component_id": r["component_id"],
            "metric": "HICP_ANNUAL_RATE_PERCENT_YOY",
            "value_known_at_cutoff": (
                r["detailed_percent_yoy"] if has_detailed else
                r["flash_percent_yoy"] if has_flash else None),
            "flash_value_visible": r["flash_percent_yoy"] if has_flash else None,
            "detailed_value_visible": r["detailed_percent_yoy"] if has_detailed else None,
            "flash_to_detailed_difference_pp": r["difference_pp"] if has_detailed else None,
            "reported_stage": stage,
            "economic_driver_score": None,
        })
    return {
        "schema": RECEIPT, "as_of_utc": cutoff.isoformat(),
        "scope": {"reference_periods": 1, "distinct_official_publications": 2,
                  "independently_comparable_annual_rate_metrics": 10},
        "date_only_conservative_cutoff_not_actual_publication_hour": True,
        "flash_visible": has_flash, "detailed_visible": has_detailed,
        "source_publications_visible": int(has_flash) + int(has_detailed),
        "latest_publication_stage": stage,
        "components": rows,
        "comparable_components_with_changed_reported_annual_rate":
            sum(x["difference_pp"] != 0 for x in parsed) if has_detailed else None,
        "headline_changed_between_flash_and_detailed":
            (False if has_detailed else None),
        "final_only_contributions_known": (
            [{"component_id": x["component_id"], "value_pp": x["value_pp"],
              "unit": "percentage points contribution to headline (not YoY percent)"}
             for x in fixture["final_only_contributions"]]
            if has_detailed else []),
        "original_publication_day_bytes_verified": False,
        "complete_historical_revision_matrix_certified": False,
        "official_intraday_release_timestamp_certified": False,
        "market_surprise_or_fx_rate_effect_inferred": False,
        "eligible_for_macro_score": False,
        "eligible_for_backtest": False,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "writes_live_data": False,
        "manifest_fingerprint_sha256": hashlib.sha256(
            json.dumps(fixture, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asof", default="2026-10-24T00:00:00Z")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = replay(args.asof)
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")), "research receipts only /tmp")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stage": result["latest_publication_stage"],
                      "changed_components": result["comparable_components_with_changed_reported_annual_rate"],
                      "backtest": result["eligible_for_backtest"]}))


if __name__ == "__main__":
    main()
