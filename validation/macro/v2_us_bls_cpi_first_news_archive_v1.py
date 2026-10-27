#!/usr/bin/env python3
"""Read-only original-publisher BLS CPI news-release evidence, NOT CPIAUCSL first-vintage levels.

25 calendar months, 2024-09 .. 2026-09. The original all-items SA rate
is rounded to 0.1%, not the exact CUSR0000SA0 index level, and not the
NSA headline year-over-year figure. October 2025 was never released.
The 2025-11 BLS 0.2% observation spans TWO months, September-November,
and is not a November 1-month rate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import ROOT

SCHEMA = "GMFQ_MACRO_V2_US_BLS_CPI_25_CALENDAR_FIRST_NEWS_RELEASE_LEDGER_V1"
PATH = ROOT / "validation/macro/fixtures/v2_bls_us_cpi_25_month_first_news_release_ledger_2026_10_27.json"
ASOF = "2026-10-26T23:59:59Z"
ARCHIVE = "https://www.bls.gov/bls/news-release/cpi.htm"
URL_PREFIX = "https://www.bls.gov/news.release/archives/cpi_"
EXPLANATION = "https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm"
STATUS = {"HTML_OPENED", "ARCHIVE_INDEX_LINK_ONLY_TIMEOUT",
          "NO_OFFICIAL_ALL_ITEMS_CPI_RELEASE"}


def require(ok, msg):
    if not ok:
        raise ValueError("USD_BLS_CPI_ISSUER_LEDGER_REJECTED: " + msg)


def month_add(period, shift):
    year, month = map(int, period.split("-"))
    n = year * 12 + month - 1 + shift
    return f"{n // 12:04d}-{n % 12 + 1:02d}"


def audit(*, cutoff=ASOF, fixture=None):
    # Only evaluate the fixed, already completed evidence cutoff. This
    # is NOT a historical replay of archives captured on issuer day.
    require(cutoff == ASOF, "fixed research evidence cutoff only, not historical PIT")
    doc = fixture if fixture is not None else json.loads(PATH.read_text(encoding="utf-8"))
    require(doc.get("schema") == SCHEMA, "ledger schema")
    require(doc.get("research_checked_on") == "2026-10-27", "audit observation day")
    require(doc.get("intended_canonical_series") == "CPIAUCSL"
            and doc.get("bls_sa_issuer_series") == "CUSR0000SA0"
            and doc.get("bls_nsa_distinct_series") == "CUUR0000SA0"
            and doc.get("structural_gap_explanation_url") == EXPLANATION,
            "SA/NSA identity or official missing-month source")
    records = doc.get("records")
    require(isinstance(records, list) and len(records) == 25, "25 calendar months required")
    expected = [month_add("2024-09", i) for i in range(25)]
    require([x.get("reference_month") for x in records] == expected
            and expected[-1] == "2026-09", "duplicate/missing/unordered economic month")
    counter = {key: 0 for key in STATUS}
    seen_release_days = set()
    for row in records:
        month = row["reference_month"]
        status = row.get("source_evidence_level")
        require(status in STATUS and row.get("issuer_archived_index_url") == ARCHIVE,
                "untrusted URL or source-confidence label")
        counter[status] += 1
        # No BLS originals captured as bytes; a web-opened HTML page is
        # weaker proof than a local SHA-256-verified publisher artifact.
        require(row.get("original_html_raw_sha256") is None and
                row.get("first_issuer_sa_index_level_CUSR0000SA0") is None,
                "cannot pretend to have source bytes or canonical SA level")
        day = row.get("publisher_release_day")
        url = row.get("issuer_archived_html_url")
        delta = row.get("first_issuer_reported_sa_all_items_change_pct_rounded_1dp")
        horizon = row.get("sa_change_horizon_months")
        if month == "2025-10":
            require(status == "NO_OFFICIAL_ALL_ITEMS_CPI_RELEASE" and
                    day is None and url is None and delta is None and horizon is None,
                    "October 2025 all-items CPI must be absent")
            continue
        require(status != "NO_OFFICIAL_ALL_ITEMS_CPI_RELEASE"
                and isinstance(day, str) and len(day) == 10,
                "issuer release day required for existing archive")
        try:
            released = date.fromisoformat(day)
        except (TypeError, ValueError) as exc:
            raise ValueError("USD_BLS_CPI_ISSUER_LEDGER_REJECTED: bad release day") from exc
        require(day == released.isoformat() and day not in seen_release_days,
                "invalid or duplicate issuer release day")
        seen_release_days.add(day)
        require(released > date.fromisoformat(month + "-01")
                and day[:7] in (month_add(month, 1), month_add(month, 2)),
                "release-day temporal mismatch")
        expected_url = URL_PREFIX + day[5:7] + day[8:10] + day[:4] + ".htm"
        require(url == expected_url, "issuer archive URL/date mismatch")
        if status == "ARCHIVE_INDEX_LINK_ONLY_TIMEOUT":
            require(delta is None and horizon is None,
                    "index-only source has no personally verified numeric value")
            continue
        require(type(delta) in (float, int) and math.isfinite(delta)
                and abs(delta) < 10 and abs(delta * 10 - round(delta * 10)) < 1e-8,
                "observed BLS report is rounded to one decimal")
        require(horizon == (2 if month == "2025-11" else 1),
                "November 2025 was 2-month change, never 1-month")
        if month == "2025-11":
            require(delta == 0.2, "BLS November shutdown bridge must be 0.2 over two months")
    require(counter == {"HTML_OPENED": 24,
                        "ARCHIVE_INDEX_LINK_ONLY_TIMEOUT": 0,
                        "NO_OFFICIAL_ALL_ITEMS_CPI_RELEASE": 1},
            "publisher link/open/gap confidence counts drift")
    anchors = {"2024-11": 0.3, "2024-12": 0.4, "2025-07": 0.2}
    for economic_month, original_change in anchors.items():
        found = [r for r in records if r["reference_month"] == economic_month]
        require(len(found) == 1 and found[0]["source_evidence_level"] == "HTML_OPENED"
                and found[0]["sa_change_horizon_months"] == 1
                and found[0]["first_issuer_reported_sa_all_items_change_pct_rounded_1dp"]
                == original_change, "recovered BLS HTML original headline anchor mismatch")
    require(records[-1]["reference_month"] == "2026-09"
            and records[-1]["first_issuer_reported_sa_all_items_change_pct_rounded_1dp"] == 0.6
            and records[12]["reference_month"] == "2025-09"
            and records[12]["first_issuer_reported_sa_all_items_change_pct_rounded_1dp"] == 0.3,
            "issuer anchor values differ from checked BLS archives")

    prior = records[:-1]
    require(sum(x["source_evidence_level"] != "NO_OFFICIAL_ALL_ITEMS_CPI_RELEASE"
                for x in prior) == 23,
            "last 24 calendar training months contain only 23 issuer release months")
    summary = {
        "calendar_periods": 25,
        "official_issuer_archive_links_documented": 24,
        "official_BLS_HTML_news_releases_opened_and_read": 24,
        "archive_index_only_unreadable_HTML_links": 0,
        "BLS_2025_10_all_items_officially_unpublished": 1,
        "one_month_rounded_SA_rate_readings": 23,
        "2025_11_two_month_rounded_SA_change_not_MOM": 1,
        "prior_24_calendar_months_with_issuer_archive_link": 23,
        "prior_24_calendar_months_truly_consecutive_CPIAUCSL_index_vintages": 0,
        "original_archived_BLS_HTML_sha256_captured": 0,
        "new_exact_CPIAUCSL_first_vintage_index_levels": 0,
        "source_slot_USD_inflation_first_release_training_approved": False,
        "source_gap_audit_22_of_24_unaltered": True,
    }
    return {
        "schema": SCHEMA, "cutoff": cutoff, "status":
            "BLS_ORIGINAL_WEB_NEWS_ARCHIVE_ROUNDED_SA_CHANGES_RESEARCH_ONLY",
        "source_archive_index": ARCHIVE,
        "BLS_oct_2025_gap_source": EXPLANATION,
        "reported_SA_rounded_changes_not_exact_CPIAUCSL_vintages": True,
        "2025_11_change_is_two_month_not_November_MOM": True,
        "news_archive_index_link_NOT_source_original_bytes": True,
        "SA_index_yearly_seasonal_revisions_not_removed": True,
        "summary": summary,
        "safe_to_publish_new_D": False, "safe_to_recalculate_28_pairs": False,
        "safe_for_beta": False, "safe_for_forward": False,
        "writes_live_data": False,
        "receipt_sha256": hashlib.sha256(
            json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        require(args.output.resolve().is_relative_to(Path("/tmp")),
                "only /tmp receipts allowed; never write Core, site or pair files")
    result = audit()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    print(json.dumps({"status": result["status"], **result["summary"],
                      "safe_to_publish_new_D": False}, sort_keys=True))


if __name__ == "__main__":
    main()
