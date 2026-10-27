#!/usr/bin/env python3
"""Seven date-specific ALFRED CPIAUCSL LAST observation anchors.

These are Federal Reserve of St Louis historical *release date page*
readings from 2026-10-27 research, NOT original BLS publisher bytes
or a complete vintage CSV / 24-month point-in-time training history.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_us_bls_cpi_first_news_archive_v1 import (
    ASOF, audit as issuer_news_audit,
    PATH as ORIGINAL_NEWS_PATH
)

SCHEMA = "GMFQ_MACRO_V2_US_CPIAUCSL_ALFRED_SEVEN_RELEASE_DATE_HTML_INDEX_PILOT_V1"
PATH = ROOT / "validation/macro/fixtures/v2_us_cpiau_alfred_seven_release_day_html_index_2026_10_27.json"
ALFRED_PREFIX = "https://alfred.stlouisfed.org/release?rd="
FIXED_ANCHORS = {
    "2024-10": ("2024-11-13", 315.454),
    "2024-12": ("2025-01-15", 317.685),
    "2025-07": ("2025-08-12", 322.132),
    "2025-09": ("2025-10-24", 324.368),
    "2025-11": ("2025-12-18", 325.031),
    "2025-12": ("2026-01-13", 326.030),
    "2026-08": ("2026-09-11", 334.131),
}

def ensure(ok, reason):
    if not ok:
        raise ValueError("GMFQ_ALFRED_RELEASE_PAGE_PILOT_REJECTED: " + reason)

def audit(*, as_of=ASOF, fixture=None):
    ensure(as_of == ASOF, "fixed research cutoff, not full historical replay")
    record = fixture if fixture is not None else json.loads(PATH.read_text(encoding="utf-8"))
    ensure(record.get("schema") == SCHEMA and
           record.get("as_of_research_date") == "2026-10-27",
           "fixture identity/date")
    ensure(record.get("origin") ==
           "FEDERAL_RESERVE_BANK_ST_LOUIS_ALFRED_RELEASE_DATE_WEB_HTML_MIRROR" and
           record.get("canonical_core_target") == "CPIAUCSL" and
           record.get("observation_frequency") == "M" and
           record.get("units") == "INDEX_1982_1984_EQ_100",
           "ALFRED mirror, SA-index source identity or index units")
    ensure(record.get("source_original_BLS_bytes_captured") is False and
           record.get("capture_includes_original_publisher_PIT_full_history") is False and
           record.get("ALFRED_HTML_raw_download_sha256") is None and
           record.get("oct_2025_official_all_items_observation_missing") is True,
           "archive mirror cannot be promoted to exact original BLS PIT vintages")
    news = json.loads(ORIGINAL_NEWS_PATH.read_text(encoding="utf-8"))
    issuer_news_audit(cutoff=as_of, fixture=news)
    by_month = {entry["reference_month"]: entry for entry in news["records"]}
    ensure(len(by_month) == 25 and
           by_month["2025-10"]["source_evidence_level"] == "NO_OFFICIAL_ALL_ITEMS_CPI_RELEASE",
           "issuer original-news ledger or shutdown month has drifted")
    rows = record.get("records")
    ensure(isinstance(rows, list) and len(rows) == len(FIXED_ANCHORS),
           "exact seven independently checked ALFRED web page anchors required")
    ensure([r.get("economic_month") for r in rows] == list(FIXED_ANCHORS),
           "anchored months must be unique and in documented order")
    for row in rows:
        month = row["economic_month"]
        release_day, value = FIXED_ANCHORS[month]
        ensure(row.get("bls_release_date") == release_day
               and by_month[month]["publisher_release_day"] == release_day,
               "ALFRED historical release date is not the BLS dated CPI issue")
        ensure(date.fromisoformat(release_day) >
               date.fromisoformat(month + "-01"), "historical economic month must precede release")
        ensure(row.get("alfred_release_date_page_url") == ALFRED_PREFIX + release_day + "&rid=10"
               and row.get("observed_last_month") == month,
               "ALFRED page URL/date or its last economic observation mismatched")
        index = row.get("alfred_release_page_last_observation_SA_CPIAUCSL_index")
        ensure(type(index) in (float, int) and math.isfinite(index)
               and math.isclose(index, value, abs_tol=1e-9, rel_tol=0)
               and index > 100 and index < 500
               and math.isclose(index * 1000, round(index * 1000), abs_tol=1e-8),
               "first visible ALFRED three-decimal SA CPIAUCSL level disagrees with published page")
        ensure(row.get("source_status") == "ALFRED_PAGE_HTML"
               and row.get("bls_original_issuer_SA_index_level_independently_certified") is False,
               "FED mirror is never BLS original archive proof")
    ret = {
        "schema": SCHEMA, "as_of_utc": as_of,
        "status": "SEVEN_FED_ALFRED_RELEASE_DAY_INDEX_LEVELS_MIRROR_RESEARCH_ONLY",
        "source_kind": "ALFRED_HISTORICAL_RELEASE_DAY_HTML_NOT_BLS_ORIGINAL_BYTES",
        "source_page_count": len(rows),
        "source_economic_months": list(FIXED_ANCHORS),
        "ALFRED_release_day_SA_index_last_observations": [
            {"economic_month": r["economic_month"],
             "release_day": r["bls_release_date"],
             "SA_index_CPIAUCSL": r["alfred_release_page_last_observation_SA_CPIAUCSL_index"],
             "ALFRED_release_page_url": r["alfred_release_date_page_url"]}
            for r in rows],
        "issuer_first_web_news_release_coverage": 24,
        "BLS_original_issue_day_bytes_sha256_captured": 0,
        "ALFRED_historical_full_vintage_CSVs_acquired": 0,
        "canonical_CPIAUCSL_first_releases_source_day_certified": 0,
        "BLS_2025_10_original_all_items_absent": True,
        "not_24_prior_consecutive_months": True,
        "cannot_establish_original_BLS_issuer_SA_vintage_from_FED_mirror_alone": True,
        "safe_to_publish_new_D": False, "safe_to_recalculate_28_pairs": False,
        "safe_for_beta": False, "safe_for_forward": False, "writes_live_data": False
    }
    ret["receipt_sha256"] = hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return ret

def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--output", type=Path)
    args = cli.parse_args()
    if args.output:
        ensure(args.output.resolve().is_relative_to(Path("/tmp")),
               "receipt location only /tmp (never production)")
    result = audit()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"],
                      "source_page_count": result["source_page_count"],
                      "safe_to_publish_new_D": False}, sort_keys=True))

if __name__ == "__main__":
    main()
