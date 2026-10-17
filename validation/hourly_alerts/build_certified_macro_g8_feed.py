#!/usr/bin/env python3
"""Validate a portable, auditable G8 macro-release snapshot.

The snapshot is intentionally *input only*: an official-release collector and
the licensed consensus collector must create it before this program runs.  This
program never fills missing values from the canonical dashboard, nor does it
turn an observed-period date into a release timestamp.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA = "GMFQ_CERTIFIED_MACRO_G8_FEED_V1"
SNAPSHOT_SCHEMA = "GMFQ_CERTIFIED_MACRO_G8_SNAPSHOT_V1"
G8 = frozenset(("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"))
MAX_AGE = timedelta(hours=6)
REQUIRED = (
    "event_id", "currency", "indicator", "period", "release_timestamp_utc",
    "as_of_utc", "actual", "consensus", "previous", "revisions", "source",
)


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def failure(event: Any, reason: str) -> dict[str, Any]:
    return {"event_id": event.get("event_id") if isinstance(event, dict) else None,
            "reason": reason}


def validate_event(event: Any, now: datetime) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(event, dict):
        return None, failure(event, "Event is not an object.")
    missing = [name for name in REQUIRED if name not in event]
    if missing:
        return None, failure(event, f"Missing required fields: {', '.join(missing)}.")
    if not all(isinstance(event[x], str) and event[x].strip() for x in ("event_id", "currency", "indicator", "period")):
        return None, failure(event, "Event identity fields must be non-empty strings.")
    if event["currency"] not in G8:
        return None, failure(event, "Currency is outside the G8 scope.")
    if not all(number(event[x]) for x in ("actual", "consensus", "previous")):
        return None, failure(event, "Actual, consensus and previous must be numeric; unavailable values are withheld.")
    if not isinstance(event["revisions"], list):
        return None, failure(event, "Revisions must be an explicit list (empty is allowed).")
    source = event["source"]
    if not isinstance(source, dict) or not all(isinstance(source.get(x), str) and source[x].strip() for x in ("authority", "release_url", "consensus_provider", "consensus_as_of_utc")):
        return None, failure(event, "Source must name authority, official release URL, consensus provider and consensus as-of.")
    released = parse_utc(event["release_timestamp_utc"])
    as_of = parse_utc(event["as_of_utc"])
    consensus_as_of = parse_utc(source["consensus_as_of_utc"])
    if not released or not as_of or not consensus_as_of:
        return None, failure(event, "Release, as-of and consensus timestamps must be ISO-8601 UTC.")
    if released > now or as_of > now or consensus_as_of > released:
        return None, failure(event, "Timestamps are causally inconsistent or in the future.")
    age = now - released
    if age > MAX_AGE:
        return None, failure(event, "Release is older than the six-hour alert freshness limit.")
    # The primary key and semantic key prevent both exact and source-side repeats.
    row = dict(event)
    row["release_age_minutes"] = round(age.total_seconds() / 60, 3)
    row["semantic_key"] = "|".join((event["currency"], event["indicator"], event["period"], event["release_timestamp_utc"]))
    row["event_fingerprint"] = hashlib.sha256(event["event_id"].encode("utf-8")).hexdigest()
    return row, None


def build(feed: Any, now: datetime, delivered_ids: set[str] | None = None) -> dict[str, Any]:
    delivered_ids = delivered_ids or set()
    failures: list[dict[str, Any]] = []
    if not isinstance(feed, dict) or feed.get("schema") != SCHEMA:
        return {"schema": SNAPSHOT_SCHEMA, "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
                "alert_eligible": False, "events": [], "rejected": [failure(feed, "Missing or unexpected feed schema.")],
                "deduplication": {"scope": "BATCH_AND_OPTIONAL_DELIVERY_LEDGER", "delivered_ledger_loaded": bool(delivered_ids)}}
    if not isinstance(feed.get("as_of_utc"), str) or parse_utc(feed["as_of_utc"]) is None:
        failures.append(failure(feed, "Feed-level as_of_utc is required and must be UTC."))
    events = feed.get("events")
    if not isinstance(events, list):
        failures.append(failure(feed, "events must be a list."))
        events = []
    accepted: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_semantic: set[str] = set()
    for event in events:
        row, rejected = validate_event(event, now)
        if rejected:
            failures.append(rejected)
            continue
        assert row is not None
        if row["event_id"] in seen_ids or row["semantic_key"] in seen_semantic:
            failures.append(failure(event, "Duplicate event_id or semantic release key in feed batch."))
            continue
        seen_ids.add(row["event_id"])
        seen_semantic.add(row["semantic_key"])
        if row["event_id"] in delivered_ids:
            failures.append(failure(event, "Event already present in immutable delivery ledger."))
            continue
        accepted.append(row)
    accepted.sort(key=lambda x: x["release_timestamp_utc"], reverse=True)
    return {"schema": SNAPSHOT_SCHEMA, "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
            "feed_as_of_utc": feed.get("as_of_utc"), "alert_eligible": bool(accepted) and not failures,
            "events": accepted if not failures else [], "rejected": failures,
            "deduplication": {"scope": "BATCH_AND_OPTIONAL_DELIVERY_LEDGER", "delivered_ledger_loaded": bool(delivered_ids),
                              "accepted_event_ids": [x["event_id"] for x in accepted] if not failures else []},
            "fail_closed_reason": None if accepted and not failures else "No fully certified, fresh and unique macro release is available."}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feed", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--delivered-event-ids", type=Path)
    ap.add_argument("--now-utc", help="Deterministic ISO-8601 UTC clock for tests.")
    args = ap.parse_args()
    now = parse_utc(args.now_utc) if args.now_utc else datetime.now(timezone.utc)
    if now is None:
        raise SystemExit("--now-utc must be ISO-8601 UTC")
    feed: Any = json.loads(args.feed.read_text(encoding="utf-8")) if args.feed.exists() else None
    delivered = set(json.loads(args.delivered_event_ids.read_text(encoding="utf-8"))) if args.delivered_event_ids and args.delivered_event_ids.exists() else set()
    result = build(feed, now, delivered)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"alert_eligible": result["alert_eligible"], "events": len(result["events"]), "rejected": len(result["rejected"]) }))


if __name__ == "__main__":
    main()
