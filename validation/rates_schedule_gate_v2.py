#!/usr/bin/env python3
"""Fail-closed Rome-local GitHub Actions scheduler gate for official G8 Rates.

An event's exact UTC cron expresses the scheduled 07:20 / 08:00 / 09:00
Rome slot. GitHub can start a run late; use the cron identity and the
Europe/Rome offset rather than the runner's current minute. Do not conflate
the CET/CEST duplicate cron expressions. A bounded 4-hour delay window
prevents a queued job from running against the wrong local session.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
UTC = dt.timezone.utc
MAX_QUEUE_DELAY_MINUTES = 240
SLOTS = {
    "20 5 * * 1-5": {2: "07:20"},
    "20 6 * * 1-5": {1: "07:20"},
    "0 6 * * 1-5": {2: "08:00"},
    # UTC 07:00 means 09:00 CEST or 08:00 CET.
    "0 7 * * 1-5": {2: "09:00", 1: "08:00"},
    "0 8 * * 1-5": {1: "09:00"},
}


def resolve(event: str, cron: str, now: dt.datetime) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("offset-aware timestamp required")
    local = now.astimezone(ROME)
    out = {
        "schema": "GMFQ_RATES_SCHEDULE_GATE_V2",
        "event": event,
        "cron": cron,
        "runner_started_at_rome": local.isoformat(),
        "slot_rome": None,
        "should_run": False,
        "reason": "",
    }
    if event != "schedule":
        out.update(should_run=True, reason="EXPLICIT_EVENT")
        return out
    slot = SLOTS.get(cron)
    if slot is None:
        out["reason"] = "UNKNOWN_CRON_FAIL_CLOSED"
        return out
    actual_offset = int(local.utcoffset().total_seconds() // 3600)
    if local.weekday() >= 5:
        out["reason"] = "NOT_BUSINESS_DAY"
        return out
    clock = slot.get(actual_offset)
    if clock is None:
        out["reason"] = "DUPLICATE_CET_CEST_UTC_SLOT"
        return out
    out["slot_rome"] = clock
    hh, mm = (int(part) for part in clock.split(":"))
    scheduled = dt.datetime.combine(local.date(), dt.time(hh, mm), tzinfo=ROME)
    elapsed = int((now.astimezone(UTC) - scheduled.astimezone(UTC)).total_seconds() // 60)
    out["queue_delay_minutes"] = elapsed
    if elapsed < 0:
        out["reason"] = "BEFORE_SCHEDULED_SLOT"
        return out
    if elapsed > MAX_QUEUE_DELAY_MINUTES:
        out["reason"] = "STALE_DELAYED_RUN"
        return out
    out.update(should_run=True, reason="VALID_RATES_SLOT_DELAY_TOLERANT")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", required=True)
    ap.add_argument("--cron", default="")
    ap.add_argument("--output")
    ap.add_argument("--summary")
    args = ap.parse_args()
    result = resolve(args.event, args.cron, dt.datetime.now(UTC))
    print("RATES_SCHEDULE_GATE_V2 " + json.dumps(result, sort_keys=True), flush=True)
    if args.output:
        with Path(args.output).open("a", encoding="utf-8") as file:
            file.write("should_run=" + ("true" if result["should_run"] else "false") + "\n")
            file.write("schedule_reason=" + result["reason"] + "\n")
    if args.summary:
        with Path(args.summary).open("a", encoding="utf-8") as file:
            file.write("### G8 Official Rates UTC/Rome schedule gate\n\n")
            file.write(f"- Result: **{'RUN' if result['should_run'] else 'SKIPPED_INTENTIONALLY'}**\n")
            file.write(f"- Reason: {result['reason']}\n")
            file.write(f"- Runner: {result['runner_started_at_rome']}\n")
            if result["slot_rome"]:
                file.write(f"- Scheduled Rome slot: {result['slot_rome']}\n")
                file.write(f"- Queue delay (min): {result.get('queue_delay_minutes', 'n/a')}\n")


if __name__ == "__main__":
    main()
