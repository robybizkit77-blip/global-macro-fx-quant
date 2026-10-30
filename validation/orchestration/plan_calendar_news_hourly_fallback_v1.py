#!/usr/bin/env python3
"""Fail-closed morning Calendar/News fallback using an EXISTING hourly workflow.

This planner does not schedule anything, publish anything or infer a CB decision.
It admits one bounded follow-up dispatch after a *successful scheduled* hourly
source-readiness workflow, only if the live Calendar/News receipts show a reason
to recheck. The unchanged 07:45 Rome orchestrator remains the primary path.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.orchestration.plan_premorning_calendar_news_recovery_v1 import (
    ROME, assess, parse_clock, read_sources, read_cb
)

SCHEMA = "GMFQ_CALENDAR_NEWS_EXISTING_HOURLY_FALLBACK_V1"
START = dt.time(5, 0)
END = dt.time(7, 50)
MEETING_FIRST_CHECK = dt.time(5, 0)
MAX_PARENT_AGE = dt.timedelta(minutes=45)


def plan(now: dt.datetime, parent: dict, sources: dict, cb: dict) -> dict:
    if not isinstance(now, dt.datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware clock required")
    local = now.astimezone(ROME)
    result = {
        "schema": SCHEMA, "evaluated_at_rome": local.isoformat(),
        "status": "SKIP", "should_dispatch": False, "reasons": [],
        "new_cron_added": False, "issuer_release_inferred": False,
        "production_data_changed": False
    }
    # A PR / push / manual run of the hourly alert workflow never triggers
    # a privileged downstream dispatch.
    if not (parent.get("name") == "Hourly Certified Alert Readiness V1"
            and parent.get("event") == "schedule"
            and parent.get("conclusion") == "success"
            and parent.get("head_branch") == "main"):
        result["reasons"] = ["UNTRUSTED_OR_NON_SCHEDULED_PARENT"]
        return result
    # workflow_run webhook objects have updated_at, not job.completed_at.
    # On a completed/success event, updated_at is the terminal receipt.
    completed = parse_clock(parent.get("updated_at"))
    if completed is None or not dt.timedelta() <= now-completed <= MAX_PARENT_AGE:
        result["reasons"] = ["STALE_OR_FUTURE_PARENT_COMPLETION"]
        return result
    if (local.weekday() >= 5 or
            not START <= local.time().replace(tzinfo=None) <= END):
        result["reasons"] = ["OUTSIDE_WEEKDAY_MORNING_WINDOW"]
        return result

    ordinary = assess(now, sources, cb)
    reasons = list(ordinary["source_rechecks_needed"])
    due = ordinary["issuer_meetings_due_for_source_watch"]
    source = sources.get("NEWS_PULSE")
    checked = parse_clock(source.get("last_checked_at_utc")) if isinstance(source,dict) else None
    if due and checked and checked <= now:
        local_checked = checked.astimezone(ROME)
        # At 06:34, BoJ's 04:02 release had already happened, but a
        # 04:01 same-day source receipt was falsely treated as sufficient.
        # Schedule is only a WATCH CUE. Never invent any policy facts.
        if (local_checked.date() == local.date() and
                local_checked.time() < MEETING_FIRST_CHECK and
                "NEWS_PULSE" not in reasons):
            reasons.append("NEWS_PULSE")
            result["reasons"].append("CB_MEETING_DAY_PRIOR_TO_0500_NEWS_CHECK")
    if not reasons:
        result["reasons"].append("SOURCES_ALREADY_CHECKED_NO_NEW_RECOVERY")
        return result
    if not result["reasons"]:
        result["reasons"].append("INCOMPLETE_OR_EARLY_SOURCE_RECEIPT")
    result.update(status="DISPATCH_REQUIRED",should_dispatch=True,
                  source_rechecks_needed=sorted(set(reasons)),
                  issuer_meetings_due_for_source_watch=due)
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-dir",type=Path,required=True)
    ap.add_argument("--parent-json",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--summary",type=Path,required=True)
    args=ap.parse_args()
    now=dt.datetime.now(dt.timezone.utc)
    parent=json.loads(args.parent_json.read_text(encoding="utf-8"))
    result=plan(now,parent,read_sources(args.source_dir),read_cb(args.source_dir))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("a",encoding="utf-8") as f:
        f.write("should_dispatch="+str(result["should_dispatch"]).lower()+"\n")
        f.write("reason="+",".join(result["reasons"])+"\n")
    with args.summary.open("a",encoding="utf-8") as f:
        f.write("### Existing hourly Calendar/News morning fallback\n")
        f.write("- Decision: **"+result["status"]+"**; "+", ".join(result["reasons"])+"\n")
        f.write("- This is an admission decision, not evidence of a delivered child run or fresh market data.\n")
    print("CALENDAR_NEWS_EXISTING_HOURLY_FALLBACK",json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
