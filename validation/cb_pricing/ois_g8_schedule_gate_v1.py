#!/usr/bin/env python3
"""Select the single valid Rome 08:15 UTC cron slot, even if GitHub starts late."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
CEST_CRON = "15 6 * * 1-5"
CET_CRON = "15 7 * * 1-5"


def gate(event: str, cron: str, utc_now: dt.datetime) -> tuple[bool, str]:
    if event != "schedule":
        return True, "MANUAL_OR_EVENT_TRIGGER"
    local = utc_now.astimezone(ROME)
    expected = CEST_CRON if local.utcoffset() == dt.timedelta(hours=2) else CET_CRON
    if cron != expected:
        return False, "DUPLICATE_DST_UTC_SLOT"
    if local.weekday() >= 5:
        return False, "NOT_WORKDAY"
    if local.time() < dt.time(8, 15):
        return False, "BEFORE_SCHEDULED_LOCAL_TIME"
    # GitHub Actions scheduled workflows may be delayed past the old 08:44
    # cutoff. A valid scheduled UTC slot should still refresh on arrival.
    return True, "VALID_ROME_0815_SLOT_DELAY_TOLERANT"


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
        "local_started_at": now.astimezone(ROME).isoformat(),
        "schedule_utc": args.cron,
    }
    if args.output:
        with Path(args.output).open("a", encoding="utf-8") as out:
            out.write("should_run=" + ("true" if allowed else "false") + "\n")
            out.write("skip_reason=" + reason + "\n")
    if args.summary:
        with Path(args.summary).open("a", encoding="utf-8") as out:
            out.write("### OIS G8 schedule gate\n\n")
            out.write("Status: **" + receipt["status"] + "** (" + reason + ")\n\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
