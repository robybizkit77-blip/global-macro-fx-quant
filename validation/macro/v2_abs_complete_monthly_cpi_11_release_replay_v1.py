#!/usr/bin/env python3
"""Eleven period-specific ABS complete-monthly-CPI web attestations, shadow-only.

Publication-gated research series, not independently archived first-release
vintages. Backcast 2024-04..2025-09 values are NOT individual 2024/25 monthly
first-release events. Prior-month references are distinct from verified revised
vintages. No macro scores / backtests / live data writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp

SOURCE = ROOT / "validation/macro/fixtures/v2_abs_complete_monthly_cpi_11_release_web_ledger_2026-10-24.json"
SCHEMA = "GMFQ_MACRO_V2_ABS_COMPLETE_MONTHLY_CPI_2025_10_TO_2026_08_RELEASE_LEDGER_V1"
RECEIPT = "GMFQ_MACRO_V2_ABS_CPI_ELEVEN_RELEASE_PIT_GAP_AUDIT_V1"
BASE = "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/"
MIN_TRAINING_FIRST_RELEASES = 25
FIRST_COMPLETE_MONTH = "2025-10"

# Independently pinned from eleven period-specific ABS pages. Each tuple:
# (observation YYYY-MM, local official release clock, first web-report headline
# YoY, first web-report trimmed mean YoY, URL slug).
PINS = (
    ("2025-10", "2025-11-26T11:30:00+11:00", 3.8, 3.3, "oct-2025"),
    ("2025-11", "2026-01-07T11:30:00+11:00", 3.4, 3.2, "nov-2025"),
    ("2025-12", "2026-01-28T11:30:00+11:00", 3.8, 3.3, "dec-2025"),
    ("2026-01", "2026-02-25T11:30:00+11:00", 3.8, 3.4, "jan-2026"),
    ("2026-02", "2026-03-25T11:30:00+11:00", 3.7, 3.3, "feb-2026"),
    ("2026-03", "2026-04-29T11:30:00+10:00", 4.6, 3.3, "mar-2026"),
    ("2026-04", "2026-05-27T11:30:00+10:00", 4.2, 3.4, "apr-2026"),
    ("2026-05", "2026-06-24T11:30:00+10:00", 4.0, 3.6, "may-2026"),
    ("2026-06", "2026-07-29T11:30:00+10:00", 3.8, 3.6, "jun-2026"),
    ("2026-07", "2026-08-26T11:30:00+10:00", 3.5, 3.6, "jul-2026"),
    ("2026-08", "2026-09-30T11:30:00+10:00", 4.0, 3.6, "aug-2026"),
)
SYDNEY = ZoneInfo("Australia/Sydney")
SERIES = {
    "AU_CPI_HEADLINE_M_YOY_context_value": "headline_annual_percent",
    "AU_CPI_TRIMMED_MEAN_M_YOY_context_value": "trimmed_mean_annual_percent",
}


def period_index(period):
    require(isinstance(period, str) and re.fullmatch(r"\d{4}-\d{2}", period),
            "monthly observation period format required")
    year, month = int(period[:4]), int(period[5:])
    require(year > 0 and 1 <= month <= 12, "invalid monthly period")
    return year * 12 + month - 1


def audit_ledger(manifest):
    require(manifest.get("schema") == SCHEMA and manifest.get("review_as_of") == "2026-10-24",
            "unknown web attestation ledger")
    require(manifest.get("authority") == "Australian Bureau of Statistics"
            and manifest.get("first_full_monthly_period") == FIRST_COMPLETE_MONTH
            and manifest.get("monthly_backcast_reference_period_start") == "2024-04"
            and manifest.get("backcast_may_have_been_published_in_2025_but_not_as_2024_first_monthly_releases") is True,
            "monthly CPI data-regime boundary changed")
    require(manifest.get("official_migration_document") ==
            "https://www.abs.gov.au/media-centre/media-statements/abs-announces-monthly-cpi-start-november-2025"
            and manifest.get("official_rba_methodology") ==
            "https://www.rba.gov.au/publications/technical-notes/2025/the-transition-to-a-complete-monthly-cpi.html",
            "independent ABS/RBA transition references changed")
    for key in ("original_release_day_raw_bytes_certified",
                "complete_revision_vintages_certified", "sufficient_first_releases_for_25_month_training",
                "eligible_for_backtest", "safe_to_publish_new_D",
                "safe_to_update_pair_theses", "writes_live_data"):
        require(manifest.get(key) is False, "unsupported research promotion " + key)
    events = manifest.get("ledger")
    require(isinstance(events, list) and len(events) == len(PINS), "11 monthly release web pages required")
    audited = []
    preceding_period_index = None
    preceding_release = None
    for observed, pinned in zip(events, PINS):
        period, clock, headline, trimmed, slug = pinned
        require(observed.get("reference_period") == period
                and observed.get("release_timestamp_local") == clock
                and observed.get("source_url") == BASE + slug,
                "period-specific release identity/date/URL drift")
        require(observed.get("source_evidence") ==
                "PERIOD_SPECIFIC_OFFICIAL_WEB_HEADLINE_METRIC_WITH_RELEASE_CLOCK"
                and observed.get("immutable_original_release_html_bytes_preserved") is False,
                "false byte-certification of release-page evidence")
        for field, expected in (("headline_annual_percent", headline),
                                ("trimmed_mean_annual_percent", trimmed)):
            value = observed.get(field)
            require(type(value) in (float, int) and math.isfinite(value)
                    and value == expected, "pinned ABS numeric first-web-report mismatch")
        index = period_index(period)
        require(index >= period_index(FIRST_COMPLETE_MONTH), "retroactive backcast misclassified")
        if preceding_period_index is not None:
            require(index == preceding_period_index + 1,
                    "noncontiguous released monthly reference periods")
        preceding_period_index = index
        source = urlsplit(observed["source_url"])
        require(source.scheme == "https" and source.hostname == "www.abs.gov.au"
                and not source.query and not source.fragment,
                "ABS source must be a period-specific official page")
        local = datetime.fromisoformat(clock)
        require(local.tzinfo is not None and local.utcoffset() is not None,
                "offset-aware official ABS timestamp required")
        require((local.hour, local.minute, local.second) == (11, 30, 0)
                and local.astimezone(SYDNEY).utcoffset() == local.utcoffset()
                and local.astimezone(SYDNEY).replace(tzinfo=None) == local.replace(tzinfo=None),
                "ABS 11:30 Australia/Sydney original DST offset mismatch")
        in_utc = local.astimezone(timezone.utc)
        if preceding_release is not None:
            require(in_utc > preceding_release, "nonmonotonic release events")
        preceding_release = in_utc
        require(local.year >= int(period[:4]), "release predates observation")
        audited.append({
            "period": period, "publication_at_utc": in_utc.isoformat(),
            "publication_at_local": clock, "headline": headline,
            "trimmed_mean": trimmed, "source_url": observed["source_url"],
            "original_release_day_bytes_archived": False,
        })
    require(len(audited) == 11 and len({e["period"] for e in audited}) == 11,
            "missing or duplicate first regular monthly CPI event")
    discrepancy = manifest.get("cross_publication_discrepancy", {})
    require(discrepancy.get("series_id") == "AU_CPI_TRIMMED_MEAN_M_YOY_context_value"
            and discrepancy.get("reference_period") == "2026-01"
            and discrepancy.get("own_period_original_web_reported_value") == 3.4
            and discrepancy.get("later_february_web_reported_january_value") == 3.3
            and discrepancy.get("earlier_source_url") == BASE + "jan-2026"
            and discrepancy.get("later_source_url") == BASE + "feb-2026"
            and discrepancy.get("later_reference_visible_from") == "2026-03-25T11:30:00+11:00"
            and discrepancy.get("numerical_revision_confirmed") is False
            and discrepancy.get("historical_january_first_value_not_overwritten") is True
            and discrepancy.get("status") == "CONFLICT_REQUIRES_REVISION_AND_METHOD_REVIEW_NOT_CERTIFIED",
            "January trimmed-mean cross-publication discrepancy tampered")
    require(timestamp(discrepancy["later_reference_visible_from"]) ==
            timestamp(audited[4]["publication_at_utc"]), "later January reference prematurely available")
    return audited


def replay(as_of, manifest=None):
    if manifest is None:
        manifest = json.loads(SOURCE.read_text(encoding="utf-8"))
    audited = audit_ledger(manifest)
    cutoff = timestamp(as_of)
    known = [e for e in audited if timestamp(e["publication_at_utc"]) <= cutoff]
    discrepancy_visible = (timestamp(manifest["cross_publication_discrepancy"]
                                    ["later_reference_visible_from"]) <= cutoff)
    last = known[-1] if known else None
    first = known[0] if known else None
    head = [e["headline"] for e in known]
    trim = [e["trimmed_mean"] for e in known]
    out = {
        "schema": RECEIPT,
        "status": "ELEVEN_PERIOD_SPECIFIC_ABS_WEB_RELEASES_NO_IMMUTABLE_FIRST_VINTAGE_ARCHIVE",
        "as_of_utc": cutoff.isoformat(),
        "data_regime": "COMPLETE_MONTHLY_CPI_ONLY_FROM_OCT_2025_REGULAR_RELEASES",
        "monthly_backcast_not_counted_as_historical_first_releases": True,
        "source_periods_verified": len(audited),
        "source_publication_events_known_at_cutoff": len(known),
        "first_visible_reference_period": first["period"] if first else None,
        "last_visible_reference_period": last["period"] if last else None,
        "last_visible_publication_at_utc": last["publication_at_utc"] if last else None,
        "latest_headline_annual_percent": head[-1] if head else None,
        "latest_trimmed_mean_annual_percent": trim[-1] if trim else None,
        "latest_headline_reported_change_pp": round(head[-1]-head[-2],2) if len(head)>1 else None,
        "latest_trimmed_mean_reported_change_pp": round(trim[-1]-trim[-2],2) if len(trim)>1 else None,
        "january_trimmed_cross_publication_discrepancy_known": discrepancy_visible,
        "january_original_first_web_report_trimmed_mean_percent":
            next((e["trimmed_mean"] for e in known if e["period"] == "2026-01"), None),
        "january_later_february_reported_reference_percent": 3.3 if discrepancy_visible else None,
        "january_revision_confirmed": False,
        "minimum_prior_first_release_training_plus_oos": MIN_TRAINING_FIRST_RELEASES,
        "additional_first_releases_needed_at_this_cutoff":
            max(0, MIN_TRAINING_FIRST_RELEASES-len(known)),
        "training_requirement_met": False,
        "revision_lineage_complete": False,
        "original_release_day_source_bytes_hashed": False,
        "allow_cross_regime_2024_backcast_as_earlier_release_events": False,
        "source_events_sufficient_for_intraday_price_causality": False,
        "macro_score_computed": False,
        "eligible_for_backtest": False,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "writes_live_data": False,
        "manifest_sha256": hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asof", default="2026-10-24T00:00:00Z")
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    result = replay(args.asof)
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")), "research receipts only /tmp")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "known": result["source_publication_events_known_at_cutoff"],
        "remaining": result["additional_first_releases_needed_at_this_cutoff"],
        "backtest_ready": result["eligible_for_backtest"],
    }))


if __name__ == "__main__":
    main()
