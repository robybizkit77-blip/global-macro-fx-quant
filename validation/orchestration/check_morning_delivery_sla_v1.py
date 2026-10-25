#!/usr/bin/env python3
"""Read-only 08:00 Rome delivery-time receipt for the morning orchestrator.

Only a successful *completed* source-and-publication pipeline may meet the
deadline. Late but otherwise good deliveries remain useful, and are reported
as LATE, never as on-time. This step does not publish or mutate market data.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
PHASES = {"prebrief", "premorning"}
TARGET = dt.time(hour=8, minute=0)


def evaluate(phase: str, report: dict | None, now: dt.datetime) -> dict:
    if phase not in PHASES:
        raise ValueError(f"unsupported morning phase: {phase}")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(ROME)
    deadline = dt.datetime.combine(local.date(), TARGET, tzinfo=ROME)
    weekday_delivery = local.weekday() < 5
    time_met = local <= deadline
    checked_at = report.get("checked_at_rome") if isinstance(report, dict) else None
    try:
        checked = dt.datetime.fromisoformat(checked_at) if isinstance(checked_at, str) else None
        if checked is not None and (checked.tzinfo is None or checked.utcoffset() is None):
            checked = None
    except ValueError:
        checked = None
    checked_local = checked.astimezone(ROME) if checked is not None else None
    same_date_and_not_future = bool(
        checked_local is not None
        and checked_local.date() == local.date()
        and checked_local <= local
    )
    source_ok = bool(
        isinstance(report, dict)
        and report.get("schema") == "GMFQ_MORNING_READINESS_V1"
        and report.get("operational_state") == "DAILY_READY_WITH_DOCUMENTED_GAPS"
        and report.get("refresh_pipeline_outcome") == "success"
        and report.get("critical_daily_problems") == []
        and same_date_and_not_future
    )
    documented_gaps = (
        report.get("documented_nonblocking_gaps", [])
        if isinstance(report, dict) and isinstance(report.get("documented_nonblocking_gaps"), list)
        else []
    )
    if not weekday_delivery:
        status = "FAIL_OUTSIDE_WEEKDAY_DELIVERY_WINDOW"
    elif not source_ok:
        status = "FAIL_INCOMPLETE_OR_UNVERIFIED"
    elif not time_met:
        status = "LATE_SOURCES_READY_AFTER_DEADLINE"
    else:
        status = "PASS_DELIVERED_BY_0800"
    return {
        "schema": "GMFQ_MORNING_0800_DELIVERY_SLA_V1",
        "phase": phase,
        "target_timezone": "Europe/Rome",
        "target_rome": deadline.isoformat(timespec="seconds"),
        "evaluated_at_rome": local.isoformat(timespec="seconds"),
        "morning_source_checked_at_rome": checked_local.isoformat(timespec="seconds") if checked_local else None,
        "source_evidence_current_day": same_date_and_not_future,
        "source_and_publication_sequence_successful": source_ok,
        "weekday_delivery_window": weekday_delivery,
        "on_time": bool(source_ok and time_met and weekday_delivery),
        "documented_nonblocking_gaps": documented_gaps,
        "seconds_from_deadline": int((local - deadline).total_seconds()),
        "status": status,
        "data_policy": "READ_ONLY_NO_SOURCE_MUTATION",
        "note": "Success means the orchestrator finished its publisher and source checks; it does not certify historical Macro scores, withheld official OIS curves, or predictive models.",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=sorted(PHASES), required=True)
    p.add_argument("--readiness", required=True)
    p.add_argument("--output")
    p.add_argument("--as-of", help="ISO-8601 aware evaluation instant, deterministic testing only")
    args = p.parse_args()
    try:
        if args.as_of:
            now = dt.datetime.fromisoformat(args.as_of)
        else:
            now = dt.datetime.now(dt.timezone.utc)
        path = Path(args.readiness)
        report = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (ValueError, OSError, json.JSONDecodeError):
        report = None
        now = dt.datetime.now(dt.timezone.utc)
    result = evaluate(args.phase, report, now)
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("MORNING_0800_SLA", json.dumps(result, sort_keys=True))
    return int(result["status"] != "PASS_DELIVERED_BY_0800")


if __name__ == "__main__":
    raise SystemExit(main())
