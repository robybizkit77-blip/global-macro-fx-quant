#!/usr/bin/env python3
"""DST-aware, GitHub-delay-tolerant gate for the three Rome CB Pricing slots.

The five UTC cron lines cover both CET and CEST. Identify the intended local
slot from github.event.schedule and the current Rome weekday, rather than
comparing wall-clock time to an exact HH:MM. No new schedule is introduced.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
LOCAL_SLOTS = ((6, 7), (6, 37), (7, 7))


def gate(event: str, cron: str, utc_now: dt.datetime) -> tuple[bool, str]:
    if event != "schedule":
        return True, "MANUAL_OR_EVENT_TRIGGER"
    if utc_now.tzinfo is None:
        raise ValueError("CB_PRICING_GATE_NEEDS_AWARE_UTC_TIMESTAMP")
    local_now = utc_now.astimezone(ROME)
    if local_now.weekday() >= 5:
        return False, "NOT_ROME_WORKDAY"
    for hour, minute in LOCAL_SLOTS:
        local_slot = dt.datetime(
            local_now.year, local_now.month, local_now.day,
            hour, minute, tzinfo=ROME
        )
        utc_slot = local_slot.astimezone(dt.timezone.utc)
        expected = f"{utc_slot.minute} {utc_slot.hour} * * 1-5"
        if cron != expected:
            continue
        if utc_now < utc_slot:
            return False, "BEFORE_SCHEDULED_LOCAL_SLOT"
        return True, "VALID_ROME_SLOT_DELAY_TOLERANT"
    return False, "WRONG_CET_CEST_UTC_SLOT"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--cron", default="")
    parser.add_argument("--output")
    parser.add_argument("--summary")
    args = parser.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    allowed, reason = gate(args.event, args.cron, now)
    receipt = {
        "status": "RUN" if allowed else "SKIPPED_INTENTIONALLY",
        "reason": reason,
        "rome_started_at": now.astimezone(ROME).isoformat(),
        "scheduled_utc_cron": args.cron,
        "slots_rome": ["06:07", "06:37", "07:07"],
    }
    if args.output:
        with Path(args.output).open("a", encoding="utf-8") as f:
            f.write(f"should_run={'true' if allowed else 'false'}\n")
            f.write(f"gate_reason={reason}\n")
    if args.summary:
        with Path(args.summary).open("a", encoding="utf-8") as f:
            f.write(f"### CB Pricing Rome schedule gate\n\n**{receipt['status']}**: {reason}\n\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
