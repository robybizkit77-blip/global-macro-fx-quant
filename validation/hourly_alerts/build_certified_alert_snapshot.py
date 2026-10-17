#!/usr/bin/env python3
"""Build a fail-closed, machine-readable eligibility receipt for hourly alerts.

This is deliberately an adapter over the certified runtime.  It neither changes
the payload nor upgrades estimated/proxy data to official data.  Consumers must
use ``alert_eligible`` rather than a source's self-described status.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
SECTIONS = ROOT / "live_data" / "sections"
CCYS = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
CERTIFIED_OIS_CCYS = frozenset(("GBP", "JPY", "CAD", "AUD"))
OFFICIAL_RATE_FRESHNESS = frozenset((
    "CURRENT_OFFICIAL_SAME_BASIS",
    "CURRENT_OFFICIAL_SAME_BASIS_MANUAL_VERIFIED",
))
OFFICIAL_RATE_QUALITY = frozenset((
    "FULL_CURRENT_OFFICIAL",
    "FULL_CURRENT_OFFICIAL_MANUAL_VERIFIED",
))


def load(name: str) -> Any:
    return json.loads((SECTIONS / name).read_text(encoding="utf-8"))


def load_path(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_as_of(value: Any) -> date | None:
    """Accept a date prefix, but never silently manufacture a date."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def age_days(value: Any, today: date) -> int | None:
    observed = parse_as_of(value)
    return (today - observed).days if observed else None


def record(
    *, name: str, as_of: Any, today: date, max_age_days: int,
    certified: bool, source: str | None, reason: str | None = None,
) -> dict[str, Any]:
    age = age_days(as_of, today)
    if not certified:
        state = "UNAVAILABLE"
        eligible = False
        reason = reason or "No certified source contract for this lane."
    elif not isinstance(source, str) or not source.strip():
        state = "UNAVAILABLE"
        eligible = False
        reason = "Certified status withheld because the source is missing."
    elif age is None:
        state = "UNAVAILABLE"
        eligible = False
        reason = reason or "Missing or unparseable as-of date."
    elif age < 0:
        state = "UNAVAILABLE"
        eligible = False
        reason = "As-of date is in the future."
    elif age > max_age_days:
        state = "STALE"
        eligible = False
        reason = reason or f"Age {age}d exceeds the {max_age_days}d alert limit."
    else:
        state = "AVAILABLE_CERTIFIED"
        eligible = True
        reason = reason or "Certified source and as-of freshness verified."
    return {
        "name": name,
        "state": state,
        "alert_eligible": eligible,
        "as_of": as_of if isinstance(as_of, str) else None,
        "age_days": age,
        "max_age_days": max_age_days,
        "source": source,
        "reason": reason,
        # This receipt is about the most recently verified observation only.
        # It intentionally does not assert an event surprise or a post-event
        # market reaction, which require a separately timestamped event feed.
        "value_scope": "LAST_VERIFIED_OBSERVATION_NOT_POST_EVENT_REACTION",
    }


def latest_cot_date(cot: dict[str, Any]) -> str | None:
    dates: list[str] = []
    for ccy in CCYS:
        series = cot.get(ccy, {})
        values = series.get("dates", []) if isinstance(series, dict) else []
        if isinstance(values, list) and values and isinstance(values[-1], str):
            dates.append(values[-1])
    # A weekly COT lane is usable only when the entire G8 cross-section refers
    # to the same CFTC positioning date.  Taking the maximum would mix vintages.
    return dates[0] if len(dates) == len(CCYS) and len(set(dates)) == 1 else None


def latest_macro_date(macro: dict[str, Any]) -> str | None:
    dates: list[str] = []
    for rows in macro.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            values = row.get("dates", []) if isinstance(row, dict) else []
            if isinstance(values, list) and values and isinstance(values[-1], str):
                dates.append(values[-1])
    return max(dates) if dates else None


def build(today: date, macro_feed_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    ois = load("OIS_OPERATIONAL_VIEW.json")
    rates = load("NATIVE_RATES_DATA.json")
    cot = load("V250_COT_CHART_DATA.json")
    pairs = load("PAIR_SETUP_OPERATIONAL_VIEW.json")
    macro = load("MACRO_SERIES.json")
    liquidity = load("NATIVE_LIQ_DATA.json")

    ois_rows = {}
    for ccy in CCYS:
        row = ois.get("currencies", {}).get(ccy, {})
        official = (
            ccy in CERTIFIED_OIS_CCYS
            and row.get("operational_status") == "GREEN_OFFICIAL"
            and row.get("official_status") == "ACTIVE"
            and row.get("quality") == "OFFICIAL_CERTIFIED"
            and row.get("backtest_eligible_as_official") is True
        )
        ois_rows[ccy] = record(
            name=f"OIS.{ccy}", as_of=row.get("as_of"), today=today,
            max_age_days=3, certified=official, source=row.get("source"),
            reason=(None if official else
                    "Only GBP, JPY, CAD and AUD have the certified OIS contract; "
                    "estimated/proxy OIS is informational only, never alert-certified."),
        )

    rate_rows = {
        ccy: record(name=f"G8_BOND.{ccy}", as_of=rates.get(ccy, {}).get("date"), today=today,
                    max_age_days=3,
                    certified=(rates.get(ccy, {}).get("freshness_status") in OFFICIAL_RATE_FRESHNESS
                               and rates.get(ccy, {}).get("quality") in OFFICIAL_RATE_QUALITY),
                    source=rates.get(ccy, {}).get("source"))
        for ccy in CCYS
    }
    treasury = rate_rows["USD"].copy()
    treasury["name"] = "TREASURY.USD"

    cot_record = record(
        name="COT.G8", as_of=latest_cot_date(cot), today=today, max_age_days=10,
        certified=latest_cot_date(cot) is not None,
        source="CFTC Legacy Commitments of Traders (weekly, Tuesday position date)",
    )
    fx_record = record(
        name="FX.G8", as_of=pairs.get("price_asof"), today=today, max_age_days=3,
        certified=(pairs.get("schema") == "GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1"
                   and pairs.get("status") == "CURRENT_CANONICAL_ENGINE"
                   and isinstance(pairs.get("price_source"), str)
                   and "ECB" in pairs["price_source"]),
        source=pairs.get("price_source"),
    )
    # The canonical macro payload is context only.  The separate event-feed
    # snapshot is the only possible hourly trigger because it carries release,
    # consensus, revision, source and as-of evidence in one contract.
    feed_events = macro_feed_snapshot.get("events", []) if isinstance(macro_feed_snapshot, dict) else []
    feed_ok = (isinstance(macro_feed_snapshot, dict)
               and macro_feed_snapshot.get("schema") == "GMFQ_CERTIFIED_MACRO_G8_SNAPSHOT_V1"
               and macro_feed_snapshot.get("alert_eligible") is True
               and isinstance(feed_events, list) and len(feed_events) == 1)
    feed_event = feed_events[0] if feed_ok else None
    macro_record = record(
        name="MACRO.G8", as_of=(feed_event.get("as_of_utc") if feed_event else latest_macro_date(macro)), today=today, max_age_days=0,
        certified=feed_ok,
        source=(feed_event.get("source", {}).get("authority") if feed_event else "Certified G8 macro feed unavailable"),
        reason=("Certified release event available; consult event evidence for timestamp, consensus, previous and revisions."
                if feed_ok else "No single fresh, complete and deduplicated G8 macro-release record; Macro remains withheld as an hourly trigger."),
    )
    if feed_event:
        macro_record["event"] = feed_event
    # NATIVE_LIQ_DATA is monetary/liquidity context.  It is not a certified
    # corporate-credit-spread feed; the latter must never be inferred from it.
    liquidity_rows = {
        ccy: record(name=f"CREDIT_MARKET.{ccy}", as_of=liquidity.get(ccy, {}).get("as_of"), today=today,
                    max_age_days=3, certified=False, source=None,
                    reason="No certified market-credit (IG/HY/spread) adapter exists; liquidity aggregates are not substituted.")
        for ccy in CCYS
    }
    sector_record = record(
        name="EQUITY_SECTORS", as_of=None, today=today, max_age_days=3, certified=False, source=None,
        reason="No certified equity-sector adapter exists in the runtime.",
    )

    lanes: dict[str, Any] = {
        "ois": ois_rows,
        "treasury": treasury,
        "g8_bonds": rate_rows,
        "cot": cot_record,
        "fx": fx_record,
        "macro": macro_record,
        "credit_liquidity": liquidity_rows,
        "equity_sectors": sector_record,
    }
    all_records = list(ois_rows.values()) + [treasury] + list(rate_rows.values()) + [cot_record, fx_record, macro_record] + list(liquidity_rows.values()) + [sector_record]
    stale = [x["name"] for x in all_records if x["state"] == "STALE"]
    unavailable = [x["name"] for x in all_records if x["state"] == "UNAVAILABLE"]
    available = [x["name"] for x in all_records if x["state"] == "AVAILABLE_CERTIFIED"]
    return {
        "schema": "GMFQ_HOURLY_ALERT_CERTIFIED_SNAPSHOT_V1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "as_of_evaluation_date": today.isoformat(),
        "policy": {
            "evaluation_timezone": "Europe/Rome",
            "fail_closed": True,
            "estimated_or_proxy_never_certified": True,
            "green_requires_certified_source_and_fresh_as_of": True,
            "no_external_notification_is_sent_by_this_builder": True,
            "last_verified_value_is_not_post_event_reaction": True,
            "government_bond_2y_is_not_ois": True,
        },
        "lanes": lanes,
        "summary": {
            "state": "WITHHELD" if stale or unavailable else "AVAILABLE_CERTIFIED",
            "available_certified": available,
            "stale": stale,
            "unavailable": unavailable,
            "green": False,
            "green_reason": "Aggregate GREEN is disabled; the consumer must inspect per-lane eligibility.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of-date", help="Evaluation date (YYYY-MM-DD); defaults to today in Europe/Rome.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--macro-feed-snapshot", type=Path, help="Validated G8 macro event snapshot; absent means Macro is withheld.")
    args = parser.parse_args()
    today = date.fromisoformat(args.as_of_date) if args.as_of_date else datetime.now(ZoneInfo("Europe/Rome")).date()
    macro_feed = load_path(args.macro_feed_snapshot) if args.macro_feed_snapshot and args.macro_feed_snapshot.exists() else None
    snapshot = build(today, macro_feed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(snapshot["summary"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
