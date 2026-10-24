#!/usr/bin/env python3
"""Read-only adapters from previously audited source-specific Macro V2 evidence.

The adapters preserve original metric identities and source semantics; they DO
NOT certify complete historical PIT. Official publisher web attestations are
not immutable bytes saved on original release day. Runtime series data are not
rewritten or inferred to be historical first-release events.

One normalized contract drives all eight currencies and all 24 slots.
"""
from __future__ import annotations

import json
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp
from validation.macro.v2_abs_complete_monthly_cpi_11_release_replay_v1 import (
    SOURCE as ABS_FIXTURE, audit_ledger as audit_abs,
)
from validation.macro.v2_bls_us_unrate_25_release_pilot_v1 import (
    read_fixture as bls_fixture, validate_manifest as validate_bls,
)
from validation.macro.v2_eurostat_dec2025_regime_bridge_replay_v1 import (
    replay as validated_eurostat_replay,
)

EURO_DIR = "validation/macro/fixtures/"
EURO_FIXTURES = (
    "v2_eurostat_hicp_dec2025_ea20_transition_v1.json",
    "v2_eurostat_hicp_jan_feb_2026_corrigenda_v1.json",
    "v2_eurostat_hicp_mar_apr_2026_release_addendum_v1.json",
    "v2_eurostat_hicp_may_june_2026_addendum_v1.json",
    "v2_eurostat_hicp_jul_sep_2026_flash_detailed_v1.json",
)
GBP_FILE = ROOT / "validation/macro/GBP_MGSX_ROLLING_WINDOW_FIRST_RELEASE_MAP_2026-10-20.json"
AUD_ID = "AU_CPI_HEADLINE_M_YOY_context_value"
EUR_ID = "EA_HICP_HEADLINE_YOY_history_value"
USD_ID = "LNS14000000"
GBP_ID = "MGSX"
PROVENANCE = "OFFICIAL_WEB_RELEASE_EVENT_ATTESTATION_NOT_ARCHIVED_ORIGINAL_DAY_BYTES"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def event(period, kind, utc, value, url):
    return {"observation_period": period, "kind": kind,
            "visible_from_utc": timestamp(utc).isoformat(),
            "reported_value": value, "source_url": url}


def source(currency, pillar, series, freq, unit, publisher, *, period_semantics,
           evidence, notes, events):
    return {
        "currency": currency, "pillar": pillar, "source_series_id": series,
        "frequency": freq, "metric_unit": unit, "publisher": publisher,
        "period_semantics": period_semantics,
        "provenance": PROVENANCE,
        "original_release_day_immutable_bytes_verified": False,
        "complete_revision_history_verified": False,
        "canonical_series_mapping_independently_certified": False,
        "evidence_contract": evidence, "limitations": notes,
        "events": events,
    }


def eurostat():
    # This is an *independent* chain of validated earlier source contracts:
    # 10 months incl. Dec'25 EA20, Jan–Sep'26 EA21, 20 official stages.
    checked = validated_eurostat_replay("2026-10-24T00:00:00Z")
    require(checked["research_scope"]["reference_months"] == 10
            and checked["research_scope"]["ordinary_release_events"] == 20
            and checked["eligible_for_macro_scoring"] is False,
            "Eurostat ten-month source contract not independently preserved")
    files = [read(ROOT / EURO_DIR / file) for file in EURO_FIXTURES]
    rows = []
    dec = files[0]
    rows.append({
        "reference_period": dec["reference_period"],
        "flash_at": dec["stage_publications"][0]["conservative_visible_from_utc"],
        "flash_source": dec["stage_publications"][0]["source_url"],
        "detailed_at": dec["stage_publications"][1]["conservative_visible_from_utc"],
        "detailed_source": dec["stage_publications"][1]["source_url"],
        "first": dec["components"][0]["flash_percent_yoy"],
        "detailed": dec["components"][0]["detailed_percent_yoy"],
    })
    for item in files[1]["months"]:
        rows.append({
            "reference_period": item["reference_period"],
            "flash_at": item["flash"]["conservative_visible_from_utc"],
            "flash_source": item["flash"]["source_url"],
            "detailed_at": item["detailed"]["conservative_visible_from_utc"],
            "detailed_source": item["detailed"]["source_url"],
            "first": item["annual_rate_components"][0]["flash_percent_yoy"],
            "detailed": item["annual_rate_components"][0]["detailed_percent_yoy"],
        })
    for item in files[2]["months"]:
        rows.append({
            "reference_period": item["reference_period"],
            "flash_at": item["flash"]["conservative_visible_from_utc"],
            "flash_source": item["flash"]["source_url"],
            "detailed_at": item["detailed"]["conservative_visible_from_utc"],
            "detailed_source": item["detailed"]["source_url"],
            "first": item["rate_components"][0]["flash_percent_yoy"],
            "detailed": item["rate_components"][0]["detailed_percent_yoy"],
        })
    for item in files[3]["months"]:
        rows.append({
            "reference_period": item["reference_period"],
            "flash_at": item["flash"]["conservative_visibility_from_utc"],
            "flash_source": item["flash"]["source_url"],
            "detailed_at": item["detailed"]["conservative_visibility_from_utc"],
            "detailed_source": item["detailed"]["source_url"],
            "first": item["annual_rate_components"][0]["flash_percent_yoy"],
            "detailed": item["annual_rate_components"][0]["detailed_percent_yoy"],
        })
    for item in files[4]["months"]:
        rows.append({
            "reference_period": item["reference_period"],
            "flash_at": item["flash"]["conservative_visible_from_utc"],
            "flash_source": item["flash"]["url"],
            "detailed_at": item["detailed"]["conservative_visible_from_utc"],
            "detailed_source": item["detailed"]["url"],
            "first": item["components"][0]["flash_rate_yoy_percent"],
            "detailed": item["components"][0]["detailed_rate_yoy_percent"],
        })
    expected = checked["vintage_by_economic_reference_month"]
    require(len(rows) == 10 and
            [x["reference_period"] for x in rows] ==
            [x["reference_period"] for x in expected],
            "Eurostat ten-month period composition drift")
    events = []
    for row, verified in zip(rows, expected):
        require(verified["original_flash_headline"] == row["first"]
                and verified["detailed_headline"] == row["detailed"]
                and verified["detailed_visible"] is True,
                "Eurostat annual headline not consistent with validated source replay")
        require(timestamp(row["flash_at"]) < timestamp(row["detailed_at"]),
                "Eurostat flash/detail source order reversed")
        events.append(event(row["reference_period"], "FIRST_WEB",
                            row["flash_at"], row["first"], row["flash_source"]))
        events.append(event(row["reference_period"], "DETAILED_WEB",
                            row["detailed_at"], row["detailed"], row["detailed_source"]))
    require(len(events) == 20, "Eurostat regular publisher event count changed")
    return source("EUR", "inflation", EUR_ID, "M", "percent YoY",
                  "Eurostat", period_semantics="MONTH_EA20_2025_TO_EA21_2026",
                  evidence="VALIDATED_EUROSTAT_10_MONTH_RELEASE_REPLAY_PRS_578_588",
                  notes=[
                      "EA20/EA21 and ECOICOP/base change forbid automatic old/new weighted aggregation",
                      "January/February flash web pages contain later corrigenda",
                      "Intraday publisher clock unverified; conservative next-UTC-day gates",
                      "Research ID differs from registry canonical EA_HICP_HEADLINE_YOY",
                  ], events=events)


def abs_monthly():
    manifest = read(ABS_FIXTURE)
    rows = audit_abs(manifest)
    require(len(rows) == 11, "original ABS eleven-release pilot drift")
    events = [
        event(x["period"], "FIRST_WEB", x["publication_at_utc"],
              x["headline"], x["source_url"])
        for x in rows
    ]
    return source("AUD", "inflation", AUD_ID, "M", "percent YoY",
                  "Australian Bureau of Statistics",
                  period_semantics="COMPLETE_MONTHLY_CPI_FROM_OCT_2025_ONLY",
                  evidence="VALIDATED_ABS_COMPLETE_MONTHLY_11_RELEASE_WEB_LEDGER_PR_581",
                  notes=[
                      "AUD canonical CPI in 2026-10-08 registry is quarterly, NOT this monthly contextual CPI",
                      "Do not treat April 2024–Sep 2025 retro-backcast as early first monthly releases",
                      "First-release day original source bytes and full revised vintages unavailable",
                  ], events=events)


def bls_unemployment():
    manifest = bls_fixture()
    validate_bls(manifest)
    vintages = manifest["vintages"]
    require(len(vintages) == 25 and manifest["series_id"] == USD_ID,
            "BLS old headline fixture changed")
    events = [event(x["observation_period"], "FIRST_WEB",
                    x["released_at"], x["value"], x["evidence_ref"])
              for x in vintages]
    return source("USD", "labour", USD_ID, "M", "percent",
                  "U.S. Bureau of Labor Statistics",
                  period_semantics="BLS_CPS_MONTHLY_U3_NOT_CANONICAL_UNRATE_MAPPING_CERTIFIED",
                  evidence="VALIDATED_BLS_25_ARCHIVED_RELEASE_WEB_HEADLINE_PILOT",
                  notes=[
                      "This BLS LNS14000000 first-release web headline pilot is not an automatically certified UNRATE canonical historical feed",
                      "Last source observation September 2025 released 20 November after shutdown; no October 2025 event is invented",
                      "25 reported monthly first values DO NOT certify full revised vintage history or source bytes",
                  ], events=events)


def ons_labour_windows():
    data = read(GBP_FILE)
    require(data.get("schema") ==
            "GMFQ_GBP_MGSX_ROLLING_WINDOW_FIRST_RELEASE_MAP_V1"
            and data.get("series_id") == GBP_ID
            and data.get("claim_full_historical_vintage_certified") is False
            and data.get("released_at_timestamps_utc") is None,
            "GBP LFS source month semantics / timing changed")
    expected = (
        ("2026-06", "2026-08-18", 4.9),
        ("2026-07", "2026-09-15", 4.9),
        ("2026-08", "2026-10-20", 4.7),
    )
    records = data.get("official_periods")
    require(isinstance(records,list) and len(records) == len(expected),
            "3 official ONS window evidence rows required")
    from datetime import date, datetime, timedelta, timezone
    ev=[]
    for row,(end,day,value) in zip(records,expected):
        require(row.get("canonical_end_month") == end
                and row.get("release_date") == day
                and row.get("unemployment_pct") == value,
                "GBP LFS period/window/value official evidence mismatch")
        require(row.get("source_center_month") != end
                and row.get("window_end_month") == end,
                "ONS center month is NOT the canonical end of three-month LFS window")
        gate=datetime.combine(date.fromisoformat(day)+timedelta(days=1),
                              datetime.min.time(),tzinfo=timezone.utc)
        ev.append(event(end, "FIRST_WEB", gate.isoformat(),
                        value, row["source_url"]))
    return source("GBP", "labour", GBP_ID, "M", "percent",
                  "UK Office for National Statistics",
                  period_semantics="THREE_MONTH_LFS_WINDOW_END_MONTH_NOT_SOURCE_CENTER_MONTH",
                  evidence="VALIDATED_GBP_MGSX_THREE_OFFICIAL_PERIOD_WEB_ANCHORS",
                  notes=[
                      "LFS source bulletin's CENTER month differs from canonical rolling-window END month",
                      "Only three limited web release anchors; no independently verified UTC clock",
                      "Registry series identity matches MGSX but source period mapping/revisions require further review",
                  ], events=ev)


def collect():
    """Only explicitly validated, source-isolated candidates; no live feed writes.

    Future countries/series can be added using the SAME normalized source()
    record without altering the G8 control plane. No candidate is a model input
    until an independent canonical series and source-vintage review passes.
    """
    # Import lazily: the latest-source adapter reuses source()/event() defined
    # here, and only adds separately attested single-release candidates.
    from validation.macro.v2_pit_g8_latest_web_adapters_v1 import collect_latest
    return ([eurostat(), abs_monthly(), bls_unemployment(), ons_labour_windows()]
            + collect_latest())
