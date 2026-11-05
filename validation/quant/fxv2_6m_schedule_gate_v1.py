#!/usr/bin/env python3
"""Admission guard for the preregistered FXV2 6M observation lane.

The two UTC cron slots cover CET/CEST; only the slot matching the
real Europe/Rome UTC offset may collect observations.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone, date
from pathlib import Path
from zoneinfo import ZoneInfo

ROME=ZoneInfo("Europe/Rome")
WINTER="45 19 * * 1-5"
SUMMER="45 18 * * 1-5"
PARENT="Forward Frozen Core Prospective Daily V1"


def admission(event, cron, now, *, upstream_name="", upstream_branch="",
              upstream_conclusion="", upstream_event="", upstream_started_at=""):
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        return False, "NO_AWARE_REAL_UTC_CLOCK"
    now=now.astimezone(timezone.utc)
    rome=now.astimezone(ROME)
    if rome.date()<date(2026,11,6):
        return False, "PRE_REGISTRATION_DATE"
    if rome.weekday()>=5 or rome.hour<19:
        return False, "NOT_ROME_BUSINESS_EVENING"
    if event=="pull_request" or event=="push":
        return False, "TEST_ONLY_CODE_EVENT"
    if event=="schedule":
        expected=SUMMER if rome.utcoffset().total_seconds()==7200 else WINTER
        if cron!=expected:
            return False, "CET_CEST_WRONG_DUPLICATE_CRON"
        return True, "CORRECT_ROME_CRON_SLOT"
    if event=="workflow_dispatch":
        return True, "EXPLICIT_LIVE_DISPATCH"
    if event!="workflow_run":
        return False, "UNRECOGNIZED_EVENT"
    if (upstream_name!=PARENT or upstream_branch!="main" or
        upstream_conclusion!="success" or
        upstream_event not in ("schedule","workflow_dispatch","workflow_run")):
        return False, "UNTRUSTED_PARENT"
    if not upstream_started_at or not upstream_started_at.endswith("Z"):
        return False, "PARENT_TIMESTAMP_MISSING"
    try:
        started=datetime.fromisoformat(upstream_started_at.replace("Z","+00:00"))
    except ValueError:
        return False, "PARENT_TIMESTAMP_INVALID"
    if started.tzinfo is None or started.utcoffset().total_seconds()!=0:
        return False, "PARENT_TIMESTAMP_NOT_UTC"
    if not started<=now or started.astimezone(ROME).date()!=rome.date():
        return False, "PARENT_FROM_DIFFERENT_DAY_OR_FUTURE"
    return True, "SAME_ROME_DAY_SUCCESSFUL_FORWARD_PARENT"


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--event",required=True)
    ap.add_argument("--cron",default="")
    ap.add_argument("--upstream-name",default="")
    ap.add_argument("--upstream-branch",default="")
    ap.add_argument("--upstream-conclusion",default="")
    ap.add_argument("--upstream-event",default="")
    ap.add_argument("--upstream-started-at",default="")
    ap.add_argument("--output",required=True)
    ap.add_argument("--summary",required=True)
    a=ap.parse_args()
    allowed,reason=admission(a.event,a.cron,datetime.now(timezone.utc),
       upstream_name=a.upstream_name,
       upstream_branch=a.upstream_branch,
       upstream_conclusion=a.upstream_conclusion,
       upstream_event=a.upstream_event,
       upstream_started_at=a.upstream_started_at)
    with Path(a.output).open("a",encoding="utf-8") as out:
        out.write("allowed="+str(allowed).lower()+"\n")
        out.write("reason="+reason+"\n")
    with Path(a.summary).open("a",encoding="utf-8") as out:
        out.write("- FXV2 preregistered 6M experiment gate: **"+
                  ("ADMITTED" if allowed else "SKIPPED")+"** ("+reason+")\n")
    print("FXV2_6M_REAL_ROME_GATE",{"allowed":allowed,"reason":reason})


if __name__=="__main__":
    main()
