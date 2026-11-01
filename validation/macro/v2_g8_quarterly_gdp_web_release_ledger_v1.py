#!/usr/bin/env python3
"""Review dated official GDP publisher statements for one G8 quarter.

Eight Q2 2026 first-publisher-web statements, two observed later revisions.
The ledger is a web-page historical *statement* record, NOT release-day
immutable bytes, full first-release vintage archive, historical training,
or a certified GDP comparison/FX scoring or backtest input.
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
from validation.macro.v2_g8_quarterly_gdp_research_target_v1 import (
    CURRENCIES, SOURCES, QUARTERLY_GOAL
)

SCHEMA = "GMFQ_G8_REAL_GDP_Q2_2026_PUBLISHER_WEB_RELEASE_EVENTS_V1"
FILE = ROOT / "validation/macro/fixtures/v2_g8_quarterly_gdp_q2_2026_web_release_ledger_v1.json"
# Independently pinned known, publisher-attested first statements.
# Units and first-stage dates are essential, not presentation metadata.
FIRST = {
    "USD": ("2026-07-30", 1.5, "PERCENT_SAAR_ANNUALIZED", "ADVANCE", "www.bea.gov"),
    "EUR": ("2026-07-30", 0.4, "PERCENT_QOQ_SA_CALENDAR", "PRELIMINARY_FLASH", "ec.europa.eu"),
    "GBP": ("2026-08-13", 0.4, "PERCENT_QOQ_SA", "FIRST_QUARTERLY_ESTIMATE", "www.ons.gov.uk"),
    "JPY": ("2026-08-17", 0.3, "PERCENT_QOQ_SA", "FIRST_PRELIMINARY", "www.esri.cao.go.jp"),
    "CHF": ("2026-08-14", 1.5, "PERCENT_QOQ_SA_CALENDAR_SPORTS", "FLASH",
            "www.seco.admin.ch"),
    "CAD": ("2026-08-28", 0.8, "PERCENT_QOQ_SA", "FIRST_RELEASE", "www150.statcan.gc.ca"),
    "AUD": ("2026-09-02", 0.4, "PERCENT_QOQ_SA_CHAIN_VOLUME", "FIRST_RELEASE", "www.abs.gov.au"),
    "NZD": ("2026-09-17", 0.2, "PERCENT_QOQ_SA_CHAIN_VOLUME_PRODUCTION", "FIRST_RELEASE", "www.stats.govt.nz"),
}
FOLLOWUP = {
    "EUR": ("2026-09-07", 0.6, "PERCENT_QOQ_SA_CALENDAR",
            "REGULAR_ESTIMATE_REVISED", "ec.europa.eu"),
    "GBP": ("2026-09-30", 0.5, "PERCENT_QOQ_SA",
            "QUARTERLY_NATIONAL_ACCOUNTS_REVISION", "www.ons.gov.uk"),
}
# Explicit safe nonannualized unit: US SAAR and Swiss sports-adjusted
# statistic cannot be ranked as identical unqualified quarterly GDP.
CONDITIONAL_UNITS = {"PERCENT_SAAR_ANNUALIZED", "PERCENT_QOQ_SA_CALENDAR_SPORTS"}


def visible_at(day: str):
    # No source-certified intraday clock for ALL 8 records; preserve
    # full-date uncertainty rather than guessing release times.
    published = date.fromisoformat(day)
    return datetime.combine(published + timedelta(days=1),
                            datetime.min.time(), timezone.utc)


def review(data=None):
    if data is None:
        data = json.loads(FILE.read_text(encoding="utf-8"))
    require(data.get("schema") == SCHEMA and data.get("reviewed_on") == "2026-10-26",
            "GDP statement ledger schema or scope changed")
    for field, expected in (
        ("release_artifact_original_day_bytes_archived", False),
        ("release_timestamp_intraday_independently_verified", False),
        ("gdp_reporting_horizon_not_uniform", True),
        ("eligible_for_macro_scoring", False), ("eligible_for_beta", False),
        ("eligible_for_forward", False), ("may_rewrite_D_json", False),
        ("observed_first_web_releases", 8), ("observed_follow_up_revisions", 2),
    ):
        require(data.get(field) is expected or
                (type(expected) is int and type(data.get(field)) is int
                 and data[field] == expected),
                "GDP web evidence certification illegally changed: " + field)
    require(data.get("asof_policy") ==
            "CONSERVATIVE_DATE_ONLY_PUBLICLY_VISIBLE_FROM_NEXT_UTC_DAY",
            "GDP release-day clock cannot be inferred")
    recs = data.get("records")
    require(isinstance(recs, list) and len(recs) == 10,
            "eight first releases and two independently dated revisions required")
    seen_first, seen_later, clean = {}, {}, []
    for r in recs:
        require(isinstance(r, dict), "invalid GDP event")
        c, stage = r.get("currency"), r.get("stage_order")
        require(c in CURRENCIES and stage in (0, 1) and type(stage) is int,
                "invalid GDP currency or revision order")
        ref = FIRST if stage == 0 else FOLLOWUP
        require(c in ref and c not in (seen_first if stage == 0 else seen_later),
                "duplicate/unauthorized GDP event for same stage")
        day, value, unit, label, host = ref[c]
        require(r.get("reference_quarter") == "2026Q2"
                and r.get("publisher_release_day") == day
                and type(r.get("reported_value")) in (int, float)
                and math.isfinite(r["reported_value"])
                and r["reported_value"] == value
                and r.get("reported_unit") == unit
                and r.get("publication_stage") == label
                and isinstance(r.get("source_description"), str)
                and len(r["source_description"]) >= 20,
                "GDP original publisher statement date/value/stage/definition mismatch")
        url = r.get("source_url")
        require(isinstance(url, str), "GDP source URL missing")
        parsed = urlsplit(url)
        require(parsed.scheme == "https" and parsed.hostname == host
                and not parsed.username and not parsed.password
                and not parsed.fragment, "GDP source is not the pinned official issuer")
        origin = SOURCES[c]
        require(isinstance(origin[0], str) and len(origin[0]) > 5,
                "GDP research source publisher missing")
        vis = visible_at(day)
        require(vis <= datetime(2026, 10, 27, tzinfo=timezone.utc),
                "future GDP webpage masquerades as October review")
        item = {
            **r,
            "conservative_available_from_utc": vis.isoformat(),
            "source_artifact_original_day_sha256": None,
            "publisher_release_instant_verified": False,
            "PIT_training_vintage_certified": False,
            "eligible_for_macro_scoring": False,
        }
        clean.append(item)
        (seen_first if stage == 0 else seen_later)[c] = item
    require(set(seen_first) == set(FIRST) == set(CURRENCIES)
            and set(seen_later) == set(FOLLOWUP),
            "missing first-release GDP source or revision")
    for c, later in seen_later.items():
        require(visible_at(later["publisher_release_day"]) >
                visible_at(seen_first[c]["publisher_release_day"]),
                "later revision cannot precede first publisher statement")
        require(later["reported_unit"] == seen_first[c]["reported_unit"],
                "revision cannot switch metric units or GDP definition")
    evidence_sha = hashlib.sha256(json.dumps(
        data["records"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema": "GMFQ_G8_GDP_WEB_RELEASE_RESEARCH_AUDIT_V1",
        "status": "EIGHT_G8_Q2_FIRST_OFFICIAL_WEB_VALUES_TWO_REVISIONS_NO_HISTORICAL_PIT",
        "research_asof_date": "2026-10-26",
        "research_target": QUARTERLY_GOAL,
        "web_evidence_record_sha256": evidence_sha,
        "events": clean,
        "summary": {
            "first_publisher_web_statements_documented": 8,
            "documented_followup_revisions": 2,
            "different_reported_GDP_horizon_or_special_adjustment": 2,
            "certified_historical_first_vintage_training_windows": 0,
            "approved_macro_growth_scores": 0,
        },
        "source_document_is_not_release_day_archive": True,
        "identical_quarterly_growth_horizon_approved_for_G8_ranking": False,
        "safe_to_update_live_macro_D": False,
        "safe_to_change_28_pairs": False,
        "safe_to_use_for_beta": False,
        "safe_to_use_for_forward": False,
        "writes_live_data": False,
    }


def asof(receipt: dict, at: str) -> dict:
    cutoff = timestamp(at)
    chosen = {}
    for row in receipt["events"]:
        if timestamp(row["conservative_available_from_utc"]) <= cutoff:
            current = chosen.get(row["currency"])
            if current is None or (
                row["stage_order"], row["publisher_release_day"]
            ) > (current["stage_order"], current["publisher_release_day"]):
                chosen[row["currency"]] = row
    return {
        "cutoff_utc": cutoff.isoformat(),
        "visible_currency_count": len(chosen),
        "available_by_currency": {
            c: {
                "date": chosen[c]["publisher_release_day"],
                "publication_stage": chosen[c]["publication_stage"],
                "raw_publisher_value": chosen[c]["reported_value"],
                "publisher_unit": chosen[c]["reported_unit"],
                "source_url": chosen[c]["source_url"],
                # Avoid pretending annualized US GDP or CHF sport adjusted
                # share a simple identical score with the other six.
                "research_nonannualized_qoq_publisher_value":
                    chosen[c]["reported_value"]
                    if chosen[c]["reported_unit"] not in CONDITIONAL_UNITS
                    else None,
                "certified_for_common_G8_growth_score": False,
                "historical_release_day_source_archive_verified": False,
            } for c in CURRENCIES if c in chosen
        },
        "safe_to_publish_new_D": False,
    }


def markdown(receipt):
    lines = [
        "# G8 GDP 2026Q2 - dated official publisher web-release history",
        "",
        "**One quarter only. Not a full historical PIT training archive.** "
        "Source pages reviewed 26 October 2026; no historical byte snapshots claimed.",
        "",
        "| Currency | First release day | Publisher reading | Unit/stage | Latest documented revision |",
        "| --- | --- | ---: | --- | --- |",
    ]
    by = {r["currency"]: r for r in receipt["events"] if r["stage_order"] == 0}
    revised = {r["currency"]: r for r in receipt["events"] if r["stage_order"] == 1}
    for c in CURRENCIES:
        first = by[c]
        latter = revised.get(c)
        desc = ("No follow-up pinned" if latter is None else
                f"{latter['publisher_release_day']}: {latter['reported_value']} "
                f"({latter['publication_stage']})")
        lines.append(
            f"| {c} | {first['publisher_release_day']} | "
            f"{first['reported_value']} | {first['reported_unit']} / "
            f"{first['publication_stage']} | {desc} |"
        )
    lines += [
        "",
        "**US: 1.5% SAAR cannot be compared directly with 0.4% QoQ; "
        "CHF GDP flash sports-event adjustment is a separate definition.**",
        "UK Q2 first +0.4 on 13 Aug revised to +0.5 on 30 Sep. "
        "EA21 GDP first +0.4 on 30 Jul revised to +0.6 on 7 Sep.",
        "",
        "Historical publisher web statement is NOT original release-day archived "
        "bytes or a full 13-quarterly-series first-release/revision archive.",
        "No source-to-score formula, backtest, Beta or Forward promotion.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--asof", default="2026-10-26T23:59:59Z")
    args = parser.parse_args()
    for out in (args.out, args.markdown):
        if out:
            require(out.resolve().is_relative_to(Path("/tmp")),
                    "GDP web research artifacts must remain under /tmp")
    audited = review()
    snapshot = asof(audited, args.asof)
    payload = {"audit": audited, "snapshot": snapshot}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(audited) + "\n")
    print(json.dumps({**audited["summary"],
                      "visible_at_cutoff": snapshot["visible_currency_count"],
                      "safe_to_update_live_macro_D": False}, sort_keys=True))


if __name__ == "__main__":
    main()
