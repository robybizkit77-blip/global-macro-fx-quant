#!/usr/bin/env python3
"""Run CHF/NZD informational source refresh before Rome 08:00, DST-safe.

The later original UTC slots remain for source updates during the day.
The pre-open optional paid-vendor retry can run once at the selected morning
slot only (unless explicitly dispatched); never at both DST duplicate slots.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
MORNING_CEST = "30 4 * * 1-5"  # 06:30 Rome summer
MORNING_CET = "30 5 * * 1-5"   # 06:30 Rome winter
LATER_SOURCE_SLOTS = ("45 8 * * 1-5", "30 18 * * 1-5")
RATES_PARENT = "Rates Persistent Daily V1"


def gate(event: str, cron: str, now: dt.datetime, *,
         upstream_name: str = "", upstream_branch: str = "",
         upstream_conclusion: str = "", upstream_event: str = "",
         upstream_started_at: str = "") -> tuple[bool, bool, str]:
    """(refresh, paid-vendor-eligible, reason). No live market API calls."""
    if now.tzinfo is None:
        raise ValueError("UTC-aware clock required")
    if event == "workflow_run":
        # A distinct, successful same-Rome-day Rates run recovers missed
        # source refreshes; NEVER spend a second vendor quota slot.
        local = now.astimezone(ROME)
        if (upstream_name != RATES_PARENT or upstream_branch != "main" or
            upstream_conclusion != "success" or
            upstream_event not in {"schedule", "workflow_run", "workflow_dispatch", "push"}):
            return False, False, "UNTRUSTED_OR_FAILED_RATES_PARENT"
        try:
            started = dt.datetime.fromisoformat(upstream_started_at.replace("Z", "+00:00"))
            if started.tzinfo is None:
                raise ValueError("upstream datetime must be timezone-aware")
        except (TypeError, ValueError, AttributeError):
            return False, False, "UNVERIFIED_PARENT_START_TIME"
        if started > now or started.astimezone(ROME).date() != local.date():
            return False, False, "PARENT_OUTSIDE_CURRENT_ROME_DAY"
        if local.weekday() >= 5:
            return False, False, "NOT_A_ROMAN_WORKDAY"
        if local.time() < dt.time(6, 30):
            return False, False, "BEFORE_MORNING_LOCAL_SLOT"
        return True, False, "INDEPENDENT_SUCCESSFUL_MAIN_RATES_RECOVERY"
    if event != "schedule":
        return True, event == "workflow_dispatch", "EVENT_OR_MANUAL_SOURCE_REFRESH"
    local = now.astimezone(ROME)
    if local.weekday() >= 5:
        return False, False, "NOT_A_ROMAN_WORKDAY"
    if cron in (MORNING_CEST, MORNING_CET):
        correct = MORNING_CEST if local.utcoffset() == dt.timedelta(hours=2) else MORNING_CET
        if cron != correct:
            return False, False, "DUPLICATE_DST_SLOT"
        if local.time() < dt.time(6, 30):
            return False, False, "BEFORE_MORNING_LOCAL_SLOT"
        return True, True, "ROME_0630_PREOPEN_SOURCE_REFRESH"
    if cron in LATER_SOURCE_SLOTS:
        return True, False, "LATER_OFFICIAL_SOURCE_RETRY"
    return False, False, "UNKNOWN_SCHEDULE_SLOT"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--event", required=True)
    p.add_argument("--cron", default="")
    p.add_argument("--upstream-name", default="")
    p.add_argument("--upstream-branch", default="")
    p.add_argument("--upstream-conclusion", default="")
    p.add_argument("--upstream-event", default="")
    p.add_argument("--upstream-started-at", default="")
    p.add_argument("--output", type=Path)
    p.add_argument("--summary", type=Path)
    args = p.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    refresh, vendor, reason = gate(
        args.event, args.cron, now,
        upstream_name=args.upstream_name,
        upstream_branch=args.upstream_branch,
        upstream_conclusion=args.upstream_conclusion,
        upstream_event=args.upstream_event,
        upstream_started_at=args.upstream_started_at)
    result = {
        "source_refresh": "RUN" if refresh else "SKIP_INTENTIONALLY",
        "authorized_optional_vendor_retry_eligible": vendor,
        "reason": reason,
        "checked_at_rome": now.astimezone(ROME).isoformat(),
        "observations_updated": None,
        "source_freshness_not_certified_by_schedule": True,
    }
    if args.output:
        with args.output.open("a", encoding="utf-8") as f:
            f.write("should_run=" + str(refresh).lower() + "\n")
            f.write("vendor_slot=" + str(vendor).lower() + "\n")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as f:
            f.write("### CHF/NZD V2 — source refresh gate\n")
            f.write("- Slot: **" + result["source_refresh"] + "** (" + reason + ")\n")
            f.write("- Local check: " + result["checked_at_rome"] + "\n")
            f.write("- This gate only authorizes an attempt: source dates are checked below.\n")
    print("FXV2_CHF_NZD_SCHEDULE_GATE", json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
