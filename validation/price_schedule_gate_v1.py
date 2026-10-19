#!/usr/bin/env python3
"""Resolve ECB Price refresh's local cron slot despite delayed GitHub Actions runs.

Scheduled Price candidate fetching remains restricted to three Europe/Rome
post-publication slots (17:10, 17:40, 18:10). GitHub's cron dispatch time is
not its runner start time, so never compare the runner's HH:MM to exact slots.
Select a single CET/CEST UTC counterpart using github.event.schedule.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
# Schedule strings are the exact cron expressions of this workflow.
SLOTS = {
    "10 15 * * 1-5": ("17:10", 2),
    "10 16 * * 1-5": ("17:10", 1),
    "40 15 * * 1-5": ("17:40", 2),
    "40 16 * * 1-5": ("17:40", 1),
    "10 17 * * 1-5": ("18:10", 2),
    "10 18 * * 1-5": ("18:10", 1),
}


def gate(event: str, cron: str, now: dt.datetime) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(ROME)
    result = {
        "schema": "GMFQ_PRICE_SCHEDULE_GATE_V1",
        "event": event,
        "cron": cron,
        "started_at_rome": local.isoformat(),
        "should_run": False,
        "reason": "",
        "slot_local_time": None,
    }
    if event != "schedule":
        result.update(should_run=True, reason="MANUAL_OR_PUSH_OR_PR")
        return result

    if cron not in SLOTS:
        result["reason"] = "UNKNOWN_CRON_FAIL_CLOSED"
        return result
    time_str, required_offset = SLOTS[cron]
    result["slot_local_time"] = time_str
    offset = int(local.utcoffset().total_seconds() / 3600)
    if offset != required_offset:
        result["reason"] = "DUPLICATE_DST_UTC_SLOT"
        return result
    if local.weekday() >= 5:
        result["reason"] = "NOT_LOCAL_BUSINESS_DAY"
        return result
    hour, minute = map(int, time_str.split(":"))
    if local.time() < dt.time(hour, minute):
        result["reason"] = "BEFORE_LOCAL_SCHEDULED_SLOT"
        return result
    result.update(should_run=True, reason="VALID_ROME_PRICE_SLOT_DELAY_TOLERANT")
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", required=True)
    ap.add_argument("--cron", default="")
    ap.add_argument("--output")
    ap.add_argument("--summary")
    args = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    result = gate(args.event, args.cron, now)
    print("PRICE_SCHEDULE_GATE_V1 " + json.dumps(result, sort_keys=True), flush=True)
    if args.output:
        with Path(args.output).open("a", encoding="utf-8") as fp:
            fp.write(f"should_run={'true' if result['should_run'] else 'false'}\n")
            fp.write(f"schedule_reason={result['reason']}\n")
    if args.summary:
        with Path(args.summary).open("a", encoding="utf-8") as fp:
            fp.write("## ECB Price daily trigger gate\n\n")
            fp.write(f"- {'RUN' if result['should_run'] else 'SKIPPED_INTENTIONALLY'}: {result['reason']}\n")
            fp.write(f"- Local started: {result['started_at_rome']}\n")
            if result["slot_local_time"]:
                fp.write(f"- Target Rome slot: {result['slot_local_time']}\n")


if __name__ == "__main__":
    main()
