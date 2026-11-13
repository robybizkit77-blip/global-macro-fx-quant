#!/usr/bin/env python3
"""Admit CFTC catch-up after officially delayed Monday releases.

Run within the existing two COT workflows. A schedule is merely a polling
opportunity: the CFTC candidate builder remains the authoritative, fail-closed
test that all eight contracts have a genuinely new matching official as-of.
"""
from __future__ import annotations

from datetime import datetime, time
import json
import os
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
# UTC twin cron hours map to the same intended local Saturday retry hour.
SATURDAY_SLOTS = {
    "0 22 * * 5": 2,  # Saturday 00:00 CEST
    "0 23 * * 5": 1,  # Saturday 00:00 CET
    "0 0 * * 6": 2,   # Saturday 02:00 CEST
    "0 1 * * 6": 1,   # Saturday 02:00 CET
    "0 3 * * 6": 2,   # Saturday 05:00 CEST
    "0 4 * * 6": 1,   # Saturday 05:00 CET
    "0 6 * * 6": 2,   # Saturday 08:00 CEST
    "0 7 * * 6": 1,   # Saturday 08:00 CET
}
# Monday 22:20 Rome; ordinary Mondays are intentionally read-only NO_UPDATE.
MONDAY_SLOTS = {
    "20 20 * * 1": 2,  # Monday 22:20 CEST
    "20 21 * * 1": 1,  # Monday 22:20 CET
}
MANUAL_EVENTS = frozenset({"workflow_dispatch", "push", "pull_request"})


def plan(now: datetime, event: str, cron: str = "") -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware clock required")
    local = now.astimezone(ROME)
    iso_week = local.strftime("%G-W%V")
    base = {
        "should_run": False,
        "local_time": local.isoformat(timespec="seconds"),
        "retry_key": f"cot-new-release-green-{iso_week}",
        "reason": "CLOSED",
    }
    if event in MANUAL_EVENTS:
        return base | {"should_run": True, "reason": "EXPLICIT_VALIDATION_OR_RECOVERY"}
    if event != "schedule":
        return base | {"reason": "UNRECOGNIZED_EVENT"}

    offset_hours = int(local.utcoffset().total_seconds() // 3600)
    if cron in SATURDAY_SLOTS:
        # GitHub's scheduler may delay an event by hours. Do not require the
        # actual local hour to equal the intended slot; keep a bounded weekend.
        on_time_or_late = (local.weekday() == 5 or
                           (local.weekday() == 6 and local.time() < time(9)))
        if offset_hours == SATURDAY_SLOTS[cron] and on_time_or_late:
            return base | {"should_run": True, "reason": "SATURDAY_DST_RETRY"}
        return base | {"reason": "SATURDAY_TWIN_OR_OUT_OF_WINDOW"}

    if cron in MONDAY_SLOTS:
        # At 15:30 Eastern the published release is 21:30 in Rome (both
        # summer/winter), and the recovery polling slot is 22:20 Rome.
        # Also admit a delayed GitHub Monday event that starts early Tuesday.
        released_or_later = ((local.weekday() == 0 and local.time() >= time(21, 30))
                             or (local.weekday() == 1 and local.time() < time(12)))
        if offset_hours == MONDAY_SLOTS[cron] and released_or_later:
            return base | {"should_run": True, "reason": "MONDAY_CFTC_DELAY_RECOVERY"}
        return base | {"reason": "MONDAY_TWIN_OR_PRE_RELEASE"}
    return base | {"reason": "UNKNOWN_SCHEDULE"}


def main() -> None:
    result = plan(datetime.now(ROME), os.getenv("GITHUB_EVENT_NAME", ""),
                  os.getenv("CRON_SLOT", ""))
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fp:
        for key in ("should_run", "local_time", "retry_key", "reason"):
            value = result[key]
            fp.write(f"{key}={str(value).lower() if isinstance(value, bool) else value}\n")
    print("COT_RELEASE_RETRY_GATE", json.dumps({
        **result, "trigger": os.getenv("GITHUB_EVENT_NAME", ""),
        "scheduled_cron": os.getenv("CRON_SLOT", ""),
        "source_data_certified": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
