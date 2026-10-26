#!/usr/bin/env python3
"""Selective 07:45 Rome recovery for missed Calendar/News same-day recheck.

This is NOT a market-content freshness claim. Already rechecked files are
not reacquired; missing/stale/invalid/future timestamps require one fresh
source workflow attempt. No data is written or backfilled by this planner.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
REQUIRED = {
    "CALENDAR": "CALENDAR_OPERATIONAL_VIEW.json",
    "NEWS_PULSE": "NEWS_PULSE_OPERATIONAL.json",
}
SCHEMA = "GMFQ_PREMORNING_CALENDAR_NEWS_RECOVERY_V1"

def parse_clock(stamp):
    if not isinstance(stamp, str):
        return None
    try:
        instant = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return instant if instant.tzinfo is not None and instant.utcoffset() is not None else None

def assess(now, sources):
    if not isinstance(now, dt.datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware real evaluation time required")
    local = now.astimezone(ROME)
    evidence = {}
    retry = []
    for name in REQUIRED:
        row = sources.get(name)
        if not isinstance(row, dict):
            evidence[name] = {"state":"MISSING_OR_INVALID_SOURCE","checked_date_rome":None}
            retry.append(name)
            continue
        created = parse_clock(row.get("generated_at_utc"))
        checked = parse_clock(row.get("last_checked_at_utc"))
        if (created is None or checked is None or
            created > now or checked > now or checked < created):
            state="INVALID_OR_MISSING_SOURCE_CLOCK"
        elif checked.astimezone(ROME).date() != local.date():
            state="NOT_RECHECKED_TODAY"
        else:
            state="ALREADY_RECHECKED_TODAY"
        evidence[name] = {
            "state":state,
            "checked_date_rome":checked.astimezone(ROME).date().isoformat() if checked else None,
            "generated_at_utc":row.get("generated_at_utc"),
            "last_checked_at_utc":row.get("last_checked_at_utc"),
        }
        if state!="ALREADY_RECHECKED_TODAY":
            retry.append(name)
    return {
        "schema":SCHEMA,
        "rome_date":local.date().isoformat(),
        "status":"RETRY_REQUIRED" if retry else "SKIP_ALREADY_RECHECKED_TODAY",
        "source_rechecks_needed":retry,
        "evidence":evidence,
        "content_as_of_is_not_a_recheck_receipt":True,
        "no_publication_or_core_effect":True,
    }

def read_sources(root):
    result={}
    for name,filename in REQUIRED.items():
        try:
            result[name]=json.loads((root/filename).read_text(encoding="utf-8"))
        except (OSError,UnicodeError,json.JSONDecodeError):
            result[name]=None
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-dir",type=Path,required=True)
    p.add_argument("--as-of",help="Aware synthetic clock ONLY for deterministic QA")
    args=p.parse_args()
    now=parse_clock(args.as_of) if args.as_of else dt.datetime.now(dt.timezone.utc)
    if now is None:
        p.error("aware --as-of required")
    report=assess(now,read_sources(args.source_dir))
    print("PREMORNING_CALENDAR_NEWS_RECOVERY",json.dumps(report,sort_keys=True))
    return 0 if report["status"]=="SKIP_ALREADY_RECHECKED_TODAY" else 1

if __name__=="__main__":
    raise SystemExit(main())
