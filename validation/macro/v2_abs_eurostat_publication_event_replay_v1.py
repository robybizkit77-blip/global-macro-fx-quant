#!/usr/bin/env python3
"""Small, web-attested ABS/Eurostat release event replay; research only, NOT PIT certified.

Crucial: date-only Eurostat official webpages do not certify an intraday timestamp.
Their values become visible only from the *next* UTC day in this conservative
replay. This is a policy floor, not an assertion about the actual release hour.

A detailed release after a flash estimate is a subsequent publication; do not
automatically label it a measured value revision.
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

MANIFEST = ROOT / "validation/macro/fixtures/v2_abs_eurostat_2026_official_event_pilot.json"
SCHEMA = "GMFQ_MACRO_V2_ABS_EUROSTAT_RELEASE_EVENT_PILOT_V1"
RECEIPT = "GMFQ_MACRO_V2_ABS_EUROSTAT_RELEASE_EVENT_REPLAY_V1"
AUD_H = "AU_CPI_HEADLINE_M_YOY_context_value"
AUD_T = "AU_CPI_TRIMMED_MEAN_M_YOY_context_value"
EUR_H = "EA_HICP_HEADLINE_YOY_history_value"

# These independent pinned facts are intentionally *not* generated from the
# manifest: tampering with a release value, stage, date or URL fails closed.
PINNED = (
    (AUD_H, "2026-07", "INITIAL_OFFICIAL_RELEASE", 3.5,
     "2026-08-26T11:30:00+10:00", "2026-08-26", "jul-2026"),
    (AUD_T, "2026-07", "INITIAL_OFFICIAL_RELEASE", 3.6,
     "2026-08-26T11:30:00+10:00", "2026-08-26", "jul-2026"),
    (AUD_H, "2026-08", "INITIAL_OFFICIAL_RELEASE", 4.0,
     "2026-09-30T11:30:00+10:00", "2026-09-30", "aug-2026"),
    (AUD_T, "2026-08", "INITIAL_OFFICIAL_RELEASE", 3.6,
     "2026-09-30T11:30:00+10:00", "2026-09-30", "aug-2026"),
    (EUR_H, "2026-09", "FLASH_INITIAL_ESTIMATE", 3.8,
     None, "2026-10-02", "2-02102026-ap"),
    (EUR_H, "2026-09", "DETAILED_PUBLICATION", 3.8,
     None, "2026-10-16", "2-16102026-ap"),
)
IDENTITY = {
    AUD_H: ("AUD", "percent YoY", "Australian Bureau of Statistics",
            "CPI all groups annual percent change"),
    AUD_T: ("AUD", "percent YoY SA", "Australian Bureau of Statistics",
            "CPI trimmed mean annual percent change"),
    EUR_H: ("EUR", "Percent YoY", "Eurostat",
            "Euro area all-items HICP annual percent change"),
}
ABS_URL = "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/"
EUR_URL = "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/"


def validate(manifest):
    require(manifest.get("schema") == SCHEMA
            and manifest.get("review_as_of") == "2026-10-24",
            "unknown official event manifest")
    for field in ("historical_full_pit_certified",
                  "per_period_revision_history_complete", "eligible_for_macro_scores",
                  "eligible_for_backtest", "safe_to_publish_new_D",
                  "safe_to_update_pair_theses", "writes_live_data"):
        require(manifest.get(field) is False, "restricted research status changed: " + field)
    method = manifest.get("methodology", {})
    require(method.get("aud_visibility") == "KNOWN_OFFICIAL_AEST_RELEASE_CLOCK"
            and method.get("eur_visibility") ==
            "DATE_ONLY_NEXT_UTC_DAY_CONSERVATIVE_NOT_ACTUAL_RELEASE_CLOCK"
            and method.get("no_model_promotion") is True,
            "known-clock vs date-only policy drift")
    events = manifest.get("events")
    require(isinstance(events, list) and len(events) == len(PINNED),
            "six official metric-event records required")
    result = []
    seen = set()
    for event, expected in zip(events, PINNED):
        (sid, period, stage, value, local_clock, release_on, suffix) = expected
        require(event.get("series_id") == sid and
                event.get("reference_period") == period and
                event.get("publication_stage") == stage and
                type(event.get("value")) in (int, float) and math.isfinite(event["value"])
                and event["value"] == value,
                "official released metric/value/stage tampered")
        ccy, unit, publisher, metric = IDENTITY[sid]
        require((event.get("currency"), event.get("pillar"),
                 event.get("unit"), event.get("publisher"),
                 event.get("source_metric")) ==
                (ccy, "inflation", unit, publisher, metric),
                "economic contract mismatch")
        require(event.get("official_release_date") == release_on
                and event.get("official_release_at_local") == local_clock
                and event.get("source_page_bytes_at_original_release_archived") is False
                and event.get("web_page_can_change_after_release") is True,
                "official timing/archive evidence altered")
        url = event.get("source_url")
        require(isinstance(url, str), "release source URL required")
        parts = urlsplit(url)
        source_base = ABS_URL if ccy == "AUD" else EUR_URL
        require(url == source_base + suffix and parts.query == "" and parts.fragment == "",
                "official release-specific source URL changed")
        observed = date.fromisoformat(period + "-01")
        publication_day = date.fromisoformat(release_on)
        require(publication_day >= observed, "publication before reference period")
        key = (sid, period, stage)
        require(key not in seen, "duplicate official metric-event")
        seen.add(key)
        if ccy == "AUD":
            require(event.get("conservative_visibility_from_utc") is None,
                    "known ABS hour must not be overwritten with a day-only surrogate")
            stamp = timestamp(local_clock)
            local = datetime.fromisoformat(local_clock)
            require(local.date() == publication_day and
                    (local.hour, local.minute, local.second) == (11, 30, 0) and
                    local.utcoffset() == timedelta(hours=10),
                    "ABS original 11:30 AEST timestamp mismatch")
            visible_at = stamp
            precision = "OFFICIAL_LOCAL_TIME_WITH_OFFSET"
        else:
            require(local_clock is None, "Eurostat official intraday timestamp not sourced")
            visible_at = timestamp(event.get("conservative_visibility_from_utc"))
            required_floor = datetime.combine(
                publication_day + timedelta(days=1), datetime.min.time(),
                tzinfo=timezone.utc,
            )
            require(visible_at == required_floor,
                    "Eurostat day-only conservative next-UTC-day gate missing")
            precision = "DATE_ONLY_CONSERVATIVE_VISIBILITY_NOT_ACTUAL_RELEASE_TIME"
        result.append({
            "series_id": sid, "currency": ccy, "pillar": "inflation",
            "reference_period": period, "unit": unit, "value": value,
            "publication_stage": stage, "official_release_date": release_on,
            "official_release_at_local": local_clock,
            "visible_from_utc": visible_at.isoformat(),
            "availability_precision": precision,
            "source_url": url,
            "original_publication_bytes_verified": False,
        })
    require(len({x["series_id"] for x in result}) == 3,
            "exactly three distinct series in scoped pilot")
    return result


def replay(as_of, manifest=None):
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    events = validate(manifest)
    cutoff = timestamp(as_of)
    event_visible = [
        x for x in events
        if timestamp(x["visible_from_utc"]) <= cutoff
    ]
    latest = {}
    # Record each first estimate / detailed release for a given period. Select
    # the last *known* publication per series + period, then last known period.
    # Never interpolate absent months or select a late event at an earlier cutoff.
    for record in event_visible:
        sid, period = record["series_id"], record["reference_period"]
        current = latest.get(sid)
        if current is None or period >= current["reference_period"]:
            latest[sid] = record
    selected = [latest.get(s) for s in (AUD_H, AUD_T, EUR_H)]
    first_events = sum(e["publication_stage"] in
                       ("INITIAL_OFFICIAL_RELEASE", "FLASH_INITIAL_ESTIMATE")
                       for e in event_visible)
    later_events = sum(e["publication_stage"] == "DETAILED_PUBLICATION"
                       for e in event_visible)
    fingerprint = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema": RECEIPT,
        "status": "BOUNDED_OFFICIAL_WEB_RELEASE_EVENT_REPLAY_NO_ARCHIVE_BYTES",
        "as_of_utc": cutoff.isoformat(),
        "scope": {"series": 3, "reference_periods": 3,
                  "pinned_metric_publication_records": 6},
        "visible_metric_publication_records": len(event_visible),
        "visible_initial_metric_releases": first_events,
        "visible_later_detailed_metric_publications": later_events,
        "latest_visible_per_series": [
            {"series_id": sid, "known": entry is not None,
             "reference_period": entry["reference_period"] if entry else None,
             "value": entry["value"] if entry else None,
             "unit": entry["unit"] if entry else IDENTITY[sid][1],
             "publication_stage": entry["publication_stage"] if entry else None,
             "visible_from_utc": entry["visible_from_utc"] if entry else None}
            for sid, entry in zip((AUD_H, AUD_T, EUR_H), selected)
        ],
        "eurostat_unchanged_flash_to_detailed_not_numerical_revision":
            (len([x for x in event_visible if x["series_id"] == EUR_H]) == 2
             and events[-1]["value"] == events[-2]["value"]),
        "source_official_web_pages_rechecked_at_ci_runtime": False,
        "source_archival_bytes_verified": False,
        "full_first_release_training_window_certified": False,
        "complete_revision_history_certified": False,
        "intraday_eurostat_release_timing_verified": False,
        "event_replay_sufficient_for_backtest": False,
        "historical_macro_score_computed": False,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "eligible_for_backtest": False,
        "writes_live_data": False,
        "manifest_fingerprint_sha256": fingerprint,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asof", default="2026-10-24T00:00:00Z")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    receipt = replay(args.asof)
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")), "research receipt only /tmp")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": receipt["status"],
        "visible": receipt["visible_metric_publication_records"],
        "initial": receipt["visible_initial_metric_releases"],
        "later": receipt["visible_later_detailed_metric_publications"],
        "eligible_for_backtest": False,
    }))


if __name__ == "__main__":
    main()
