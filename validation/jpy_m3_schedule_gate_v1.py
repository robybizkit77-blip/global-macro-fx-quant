#!/usr/bin/env python3
"""Admit the original Rome JPY M3 slots even when GitHub dispatches late."""
from __future__ import annotations

import argparse
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
SLOTS = {
    "0 0 * * 1-5": (time(2, 0), 2),
    "0 1 * * 1-5": (time(2, 0), 1),
    "30 0 * * 1-5": (time(2, 30), 2),
    "30 1 * * 1-5": (time(2, 30), 1),
}


def gate(event: str, cron: str, now: datetime) -> tuple[bool, str]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware timestamp required")
    if event != "schedule":
        return True, "EXPLICIT_VALIDATION_OR_DISPATCH"
    if cron not in SLOTS:
        raise ValueError("unrecognized JPY M3 schedule")
    local = now.astimezone(ROME)
    slot, offset = SLOTS[cron]
    if local.weekday() >= 5:
        return False, "NON_BUSINESS_DAY"
    if local.utcoffset().total_seconds() != offset * 3600:
        return False, "DUPLICATE_DST_SLOT"
    if local.time() < slot:
        return False, "BEFORE_LOCAL_SLOT"
    return True, "VALID_DELAY_TOLERANT_ROME_SLOT"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--cron", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    admitted, reason = gate(args.event, args.cron, now)
    with Path(args.output).open("a", encoding="utf-8") as fp:
        fp.write(f"should_run={str(admitted).lower()}\n")
        fp.write(f"schedule_reason={reason}\n")
    with Path(args.summary).open("a", encoding="utf-8") as fp:
        fp.write(f"## JPY M3 schedule gate\n\n- {'RUN' if admitted else 'SKIPPED_INTENTIONALLY'}: {reason}\n")
        fp.write(f"- Actual Rome start: {now.astimezone(ROME).isoformat()}\n")
    print("JPY_M3_SCHEDULE_GATE", reason, now.astimezone(ROME).isoformat())


if __name__ == "__main__":
    main()
