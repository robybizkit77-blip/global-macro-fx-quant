#!/usr/bin/env python3
"""5-month Eurostat HICP flash/detail research event replay, NO PIT certification.

May/June addendum composed with previously validated July-Sept source ledger.
Ten release dates, 5 reference months, six comparable annual-rate components.
Eurostat date-only news pages use conservative next UTC day cutoff: NOT the
actual official intraday timestamp and NOT an intraday market-event study.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp
from validation.macro.v2_eurostat_hicp_three_month_replay_v1 import (
    CATEGORIES, replay as prior_replay, month_index,
)

SOURCE = ROOT / "validation/macro/fixtures/v2_eurostat_hicp_may_june_2026_addendum_v1.json"
SCHEMA = "GMFQ_MACRO_V2_EUROSTAT_HICP_MAY_JUNE_ADDENDUM_V1"
RECEIPT = "GMFQ_MACRO_V2_EUROSTAT_HICP_FIVE_MONTH_WEB_RELEASE_REPLAY_V1"
BASE = "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/"
# Independent pinned publisher web facts. Each tuple:
# month, flash date, detailed date, flash slug, detailed slug, YoY pairs
# ordered according to legacy six-category CATEGORIES.
PINS = (
    ("2026-05", "2026-06-02", "2026-06-17",
     "2-02062026-ap", "2-17062026-ap",
     ((3.2, 3.2), (2.5, 2.6), (10.9, 10.8),
      (2.0, 1.9), (0.9, 0.9), (3.5, 3.5))),
    ("2026-06", "2026-07-01", "2026-07-17",
     "2-01072026-ap", "2-17072026-ap",
     ((2.8, 2.8), (2.4, 2.4), (8.7, 8.5),
      (1.6, 1.5), (0.9, 0.7), (3.2, 3.2))),
)


def validate(addendum):
    require(addendum.get("schema") == SCHEMA
            and addendum.get("review_as_of") == "2026-10-24"
            and (addendum.get("publisher"), addendum.get("currency"),
                 addendum.get("geography")) == ("Eurostat", "EUR", "EA21")
            and addendum.get("source_measure") ==
            "ANNUAL_PERCENT_CHANGE_NOT_INDEX_OR_CONTRIBUTION"
            and addendum.get("evidence_class") ==
            "PERIOD_SPECIFIC_PUBLISHER_WEB_AS_CURRENTLY_RETRIEVED_NOT_ORIGINAL_BYTE_ARCHIVE",
            "Eurostat publisher, metric or provenance contract changed")
    for key in ("first_release_day_byte_archive_certified",
                "full_historical_first_and_revised_vintage_chain_certified",
                "live_score_or_backtest_eligible", "writes_live_data",
                "safe_to_publish_new_D", "safe_to_update_pair_theses"):
        require(addendum.get(key) is False,
                "research-only gate cannot be promoted: " + key)
    months = addendum.get("months")
    require(isinstance(months, list) and len(months) == len(PINS),
            "two source-specific May/June observations required")
    audited = []
    last_period, last_detail = None, None
    for m, (period, flash_day, detail_day, flash_slug, detail_slug, expected) in zip(months, PINS):
        require(m.get("reference_period") == period, "reference period drift")
        current_period = month_index(period)
        if last_period is not None:
            require(current_period == last_period + 1, "missing economic month")
        last_period = current_period
        stamps = []
        for stage, day, slug in (("flash", flash_day, flash_slug),
                                 ("detailed", detail_day, detail_slug)):
            item = m.get(stage, {})
            require(item.get("published_on") == day
                    and item.get("source_url") == BASE + slug
                    and item.get("actual_intraday_release_clock_certified") is False,
                    "dated official page contract changed")
            conservative = datetime.combine(
                date.fromisoformat(day) + timedelta(days=1),
                datetime.min.time(), tzinfo=timezone.utc)
            require(timestamp(item.get("conservative_visibility_from_utc")) ==
                    conservative, "do not invent Eurostat intraday release clock")
            stamps.append(conservative)
        require(stamps[0] < stamps[1]
                and (last_detail is None or last_detail < stamps[0]),
                "publication chronology overlap")
        last_detail = stamps[1]
        metrics = m.get("annual_rate_components")
        require(isinstance(metrics, list) and len(metrics) == len(CATEGORIES),
                "exactly six annual-rate metrics required")
        result = {}
        for item, category, (flash, detail) in zip(metrics, CATEGORIES, expected):
            require(item.get("component_id") == category,
                    "HICP metric or order changed")
            for name, val in (("flash_percent_yoy", flash),
                              ("detailed_percent_yoy", detail)):
                actual = item.get(name)
                require(type(actual) in (float, int)
                        and math.isfinite(actual) and actual == val,
                        "reported source number deviates from independent pin")
            result[category] = (flash, detail)
        audited.append({"period": period, "flash_gate": stamps[0],
                        "detail_gate": stamps[1], "metrics": result,
                        "flash_url": BASE + flash_slug,
                        "detailed_url": BASE + detail_slug})
    retrospective = addendum.get("retrospective_prior_month_observation", {})
    contract = {
        "reference_period": "2026-03",
        "series_component": "SERVICES",
        "earlier_report_period": "2026-05",
        "earlier_report_released_on": "2026-06-17",
        "earlier_reported_percent_yoy": 3.3,
        "earlier_report_source_url": BASE + "2-17062026-ap",
        "later_report_period": "2026-06",
        "later_report_released_on": "2026-07-01",
        "later_reported_percent_yoy": 3.2,
        "later_report_has_explicit_r_marker": True,
        "later_report_source_url": BASE + "2-01072026-ap",
        "later_report_conservative_visible_from_utc": "2026-07-02T00:00:00Z",
        "exact_revision_effective_time_verified": False,
        "original_release_day_page_bytes_certified": False,
        "interpretation":
            "CROSS_PUBLICATION_MARCH_SERVICES_REVISION_INDICATED_BY_R_NOT_FULL_VINTAGE",
    }
    require(retrospective == contract,
            "March 2026 services official retrospective evidence or revision limits drift")
    require(timestamp(contract["later_report_conservative_visible_from_utc"]) ==
            audited[1]["flash_gate"], "retrospective March services source time drift")
    return audited


def replay(as_of, addendum=None):
    if addendum is None:
        addendum = json.loads(SOURCE.read_text(encoding="utf-8"))
    new = validate(addendum)
    cutoff = timestamp(as_of)
    legacy = prior_replay(as_of)
    require(legacy["research_scope"]["reference_months"] == 3
            and legacy["research_scope"]["source_publications"] == 6
            and legacy["eligible_for_macro_scoring"] is False
            and legacy["eligible_for_backtest"] is False
            and legacy["writes_live_data"] is False,
            "original three-month replay must remain unchanged and research-only")
    rows = []
    for event in new:
        flash = cutoff >= event["flash_gate"]
        detailed = cutoff >= event["detail_gate"]
        rows.append({
            "reference_period": event["period"],
            "stage_at_cutoff": ("DETAILED_PUBLICATION" if detailed
                                else "FLASH_ESTIMATE" if flash else "NOT_KNOWN"),
            "flash_visible": flash, "detailed_visible": detailed,
            "visible_metric_values": {
                name: (pair[1] if detailed else pair[0] if flash else None)
                for name, pair in event["metrics"].items()},
            "component_flash_to_detailed_change_pp": {
                name: round(pair[1] - pair[0], 1)
                for name, pair in event["metrics"].items()
            } if detailed else None,
            "original_flash_headline":
                event["metrics"]["ALL_ITEMS_HICP"][0] if flash else None,
            "detailed_headline":
                event["metrics"]["ALL_ITEMS_HICP"][1] if detailed else None,
            "source_web_url_known": (
                event["detailed_url"] if detailed else
                event["flash_url"] if flash else None),
        })
    rows.extend(legacy["snapshot_by_reference_period"])
    require([r["reference_period"] for r in rows] ==
            ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"],
            "five consecutive HICP months and periods required")
    published = sum(r["flash_visible"] + r["detailed_visible"] for r in rows)
    known_months = sum(r["flash_visible"] for r in rows)
    latest = next((r for r in reversed(rows) if r["flash_visible"]), None)
    revision_visible = cutoff >= new[1]["flash_gate"]
    first_report_visible = cutoff >= new[0]["detail_gate"]
    retro = {
        "reference_period": "2026-03",
        "component_id": "SERVICES",
        "earlier_reported_yoy_percent": 3.3 if first_report_visible else None,
        "later_reported_yoy_percent": 3.2 if revision_visible else None,
        "difference_pp": -0.1 if revision_visible else None,
        "later_report_source_has_r_marker": True if revision_visible else None,
        "first_different_web_source_gate_utc":
            new[1]["flash_gate"].isoformat() if revision_visible else None,
        "original_march_first_publication_was_verified": False,
        "actual_revision_effective_time_verified": False,
        "additional_independent_first_release_month_count": 0,
    }
    # The March item is a RETROSPECTIVE reading, not an extra first-release month.
    return {
        "schema": RECEIPT, "as_of_utc": cutoff.isoformat(),
        "research_scope": {
            "reference_months": 5, "distinct_publisher_publications": 10,
            "comparable_annual_rate_metrics_per_stage": 6,
            "annual_rate_metric_publication_observations": 60,
            "extra_retrospective_reference_observations": 2,
        },
        "source_publications_visible": published,
        "reference_months_with_any_flash_visible": known_months,
        "latest_visible_reference_month": (
            latest["reference_period"] if latest else None),
        "latest_visible_headline_yoy_percent": (
            latest["visible_metric_values"]["ALL_ITEMS_HICP"] if latest else None),
        "snapshot_by_reference_period": rows,
        "headline_flash_detailed_changes_visible": {
            r["reference_period"]:
            r["component_flash_to_detailed_change_pp"]["ALL_ITEMS_HICP"]
            for r in rows if r["detailed_visible"]},
        "visible_nonzero_component_comparisons": sum(
            sum(abs(v) > 1e-9
                for v in r["component_flash_to_detailed_change_pp"].values())
            for r in rows if r["detailed_visible"]),
        "march_services_retrospective_cross_report": retro,
        "additional_first_release_months_needed_for_25": 25 - known_months,
        "reconstructed_from_historical_first_release_day_byte_archive": False,
        "complete_historical_revision_matrix_certified": False,
        "actual_intraday_publication_clocks_certified": False,
        "source_web_pages_rechecked_at_ci_runtime": False,
        "eligible_for_backtest": False,
        "eligible_for_macro_scoring": False,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "writes_live_data": False,
        "evidence_manifest_sha256": hashlib.sha256(
            json.dumps(addendum, sort_keys=True,
                       separators=(",", ":")).encode()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asof", default="2026-10-24T00:00:00Z")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    data = replay(args.asof)
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")),
                "research receipts restricted to /tmp")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"months": data["reference_months_with_any_flash_visible"],
                      "publications": data["source_publications_visible"],
                      "nonzero_component_pairs": data["visible_nonzero_component_comparisons"],
                      "backtest": data["eligible_for_backtest"]}))


if __name__ == "__main__":
    main()
