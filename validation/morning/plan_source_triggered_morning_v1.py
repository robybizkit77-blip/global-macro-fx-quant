"""Select genuine Rome morning edition triggers, including source-event fallback.

A completed producer is only an independent *wake-up clock*. It is NOT
evidence that market data are fresh, and does not certify on-time HTTP delivery.
This planner does not alter source data or overwrite immutable daily editions.
"""
from __future__ import annotations

from datetime import datetime, time
import json
import os
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
TRUSTED_PARENTS = frozenset({
    "Calendar News Operational Refresh V1",
    "Macro Persistent Daily V1",
})
PARENT_EVENTS = frozenset({"schedule", "workflow_dispatch", "workflow_run"})


def decide(now: datetime, event: str, cron: str = "",
           parent: dict | None = None) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must carry timezone")
    local = now.astimezone(ROME)
    response = {"active": False, "edition": local.date().isoformat(),
                "reason": "REJECTED"}
    if local.weekday() > 4 or local.hour >= 11:
        return response | {"reason": "OUTSIDE_WEEKDAY_MORNING"}

    if event == "schedule":
        fields = cron.split()
        if len(fields) != 5:
            return response | {"reason": "MISSING_SCHEDULE_CLOCK"}
        correct_utc = 5 if local.utcoffset().total_seconds() == 7200 else 6
        # Preserve existing DST twin and 08:13 post-deadline exclusion.
        if fields[1] == str(correct_utc) and fields[0] in {"11", "41", "53"}:
            return response | {"active": True, "reason": "ADMITTED_DATED_CRON"}
        return response | {"reason": "DUPLICATE_DST_OR_POSTDEADLINE_SLOT"}

    if event == "workflow_dispatch":
        return response | {"active": True, "reason": "MANUAL_BOUNDED_RECOVERY"}

    if event != "workflow_run" or not isinstance(parent, dict):
        return response | {"reason": "UNSUPPORTED_EVENT"}
    # The success badge is just a trusted wake-up signal; the morning builder
    # still reads the latest main, uses strict point-in-time rules, and the
    # independent audit separately verifies HTTP bytes and timing.
    if (parent.get("name") not in TRUSTED_PARENTS or
            parent.get("head_branch") != "main" or
            parent.get("conclusion") != "success" or
            parent.get("event") not in PARENT_EVENTS):
        return response | {"reason": "UNTRUSTED_OR_FAILED_PARENT"}
    try:
        stamp = datetime.fromisoformat(
            str(parent["updated_at"]).replace("Z", "+00:00"))
        if stamp.utcoffset() is None:
            raise ValueError("missing offset")
    except (KeyError, TypeError, ValueError):
        return response | {"reason": "INVALID_PARENT_TIMESTAMP"}
    parent_local = stamp.astimezone(ROME)
    if (parent_local.date() != local.date() or
            stamp > now or
            not time(5, 0) <= parent_local.time() < time(8, 0) or
            not time(5, 0) <= local.time() < time(8, 0)):
        return response | {"reason": "SOURCE_EVENT_OUTSIDE_PRE_0800_WINDOW"}
    return response | {"active": True, "reason": "ADMITTED_SOURCE_EVENT_WAKEUP"}


def main() -> None:
    now = datetime.now(ROME)
    parent = {
        "name": os.environ.get("PARENT_WORKFLOW", ""),
        "event": os.environ.get("PARENT_EVENT", ""),
        "head_branch": os.environ.get("PARENT_BRANCH", ""),
        "conclusion": os.environ.get("PARENT_CONCLUSION", ""),
        "updated_at": os.environ.get("PARENT_UPDATED_AT", ""),
    }
    choice = decide(now, os.environ.get("GITHUB_EVENT_NAME", ""),
                    os.environ.get("CRON_SLOT", ""), parent)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
        out.write("active=" + str(choice["active"]).lower() + "\n")
        out.write("edition=" + choice["edition"] + "\n")
        out.write("reason=" + choice["reason"] + "\n")
    print("MORNING_MACRO_EDITORIAL_SLOT", json.dumps({
        **choice, "observed_at_rome": now.isoformat(timespec="seconds"),
        "trigger": os.environ.get("GITHUB_EVENT_NAME", "")
    }, sort_keys=True))


if __name__ == "__main__":
    main()
