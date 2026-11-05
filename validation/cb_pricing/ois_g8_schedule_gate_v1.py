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
RATES_PARENT = "Rates Persistent Daily V1"


def gate(event: str, cron: str, utc_now: dt.datetime, *,
         upstream_name: str = "", upstream_branch: str = "",
         upstream_conclusion: str = "", upstream_event: str = "") -> tuple[bool, str]:
    if utc_now.tzinfo is None:
        raise ValueError("UTC-aware clock required")
    local = utc_now.astimezone(ROME)
    if event == "workflow_run":
        # Recover a delayed/missed morning OIS schedule only from a proven
        # successful main Rates run, after the intended 08:15 Rome slot.
        # Never let a failed PR/source job, yesterday's run or weekend
        # manufacture an OIS update. Rebuilding remains source dated.
        if (upstream_name != RATES_PARENT or upstream_branch != "main" or
            upstream_conclusion != "success" or
            upstream_event not in {"schedule", "workflow_run", "workflow_dispatch", "push"}):
            return False, "UNTRUSTED_OR_FAILED_RATES_PARENT"
        if local.weekday() >= 5:
            return False, "NOT_WORKDAY"
        if local.time() < dt.time(8, 15):
            return False, "BEFORE_OIS_0815_ROME_TARGET"
        return True, "INDEPENDENT_SUCCESSFUL_MAIN_RATES_RECOVERY"
    if event != "schedule":
        return True, "MANUAL_OR_EVENT_TRIGGER"
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
    parser.add_argument("--upstream-name", default="")
    parser.add_argument("--upstream-branch", default="")
    parser.add_argument("--upstream-conclusion", default="")
    parser.add_argument("--upstream-event", default="")
    args = parser.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    allowed, reason = gate(
        args.event, args.cron, now,
        upstream_name=args.upstream_name,
        upstream_branch=args.upstream_branch,
        upstream_conclusion=args.upstream_conclusion,
        upstream_event=args.upstream_event)
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
