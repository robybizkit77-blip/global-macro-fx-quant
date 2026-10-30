#!/usr/bin/env python3
"""Cheap UTC-aware gate for the EXISTING hourly-alert -> Forward recovery.

No new cron, no retrospective capture, no fresh Core scoring. Other triggers
retain their previous behavior. Hourly recovery runs only on weekday evenings
in Rome if an eligible immutable prospective ledger is missing for that date.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
ROME = ZoneInfo("Europe/Rome")
V1 = ROOT / "validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl"
V2 = ROOT / "validation/forward/candidate_shadow_snapshots/V2_MACRO_EVIDENCE_SNAPSHOTS_V1.jsonl"
HOURLY = "Hourly Certified Alert Readiness V1"
QA = ROOT / "validation/forward/candidate_shadow_snapshots/V2_QUALITY_AWARE_PROSPECTIVE_SNAPSHOTS_V1.jsonl"
QUALITY_FIRST_DAY = dt.date(2026, 11, 2)


def completed_v1(path: Path, day: str) -> bool:
    if not path.is_file():
        return False
    pairs = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if (row.get("capture_class") == "FROZEN_CORE_BASELINE_OBSERVATION"
                    and str(row.get("decision_cutoff") or "")[:10] == day):
                pairs.append(row)
    return (len(pairs) == 28
            and len({r.get("pair") for r in pairs}) == 28
            and all(r.get("t0_fx_reference", {}).get("state") ==
                    "OBSERVED_AT_CAPTURE" for r in pairs))


def completed_v2(path: Path, day: str) -> bool:
    if not path.is_file():
        return False
    with path.open(encoding="utf-8") as stream:
        entries = [json.loads(line) for line in stream if line.strip()]
    today = [r for r in entries if r.get("local_date_rome") == day]
    return (len(today) == 1
            and today[0].get("official_ecb_t0_date") == day
            and len(today[0].get("domestic_v2_features", {})) == 8
            and len(today[0].get("observed_t0_ref", {})) == 28
            and today[0].get("snapshot_sha256") is not None)


def completed_quality(path: Path, day: str) -> bool:
    """The quality-aware cohort is independent and starts on 2026-11-02."""
    if not path.is_file():
        return False
    from validation.forward.capture_v2_quality_aware_prospective_v1 import (
        read_journal, verify_journal,
    )
    try:
        rows=read_journal(path)
        return day in verify_journal(rows)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False


def evaluate(now: dt.datetime, event: str, upstream: str,
             upstream_event: str, v1_complete: bool, v2_complete: bool,
             quality_complete: bool = False) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("actual timezone-aware clock required")
    local = now.astimezone(ROME)
    result = {"local_date": local.date().isoformat(),
              "local_time": local.isoformat(), "eligible": True,
              "reason": "EXISTING_FORWARD_TRIGGER_UNCHANGED"}
    if event != "workflow_run" or upstream != HOURLY:
        return result
    if upstream_event != "schedule":
        return {**result, "eligible": False,
                "reason": "HOURLY_NON_SCHEDULE_EVENT"}
    if local.weekday() >= 5:
        return {**result, "eligible": False,
                "reason": "HOURLY_NOT_BUSINESS_WEEKDAY"}
    if not 19 <= local.hour <= 23:
        return {**result, "eligible": False,
                "reason": "HOURLY_OUTSIDE_REAL_EVENING_WINDOW"}
    if v1_complete and v2_complete:
        if local.date() < QUALITY_FIRST_DAY:
            return {**result, "eligible": False,
                    "reason": "BOTH_PROSPECTIVE_LEDGERS_ALREADY_CAPTURED_TODAY"}
        if quality_complete:
            return {**result, "eligible": False,
                    "reason": "ALL_FUTURE_PROSPECTIVE_LEDGER_CLASSES_CAPTURED_TODAY"}
    return {**result, "reason": "HOURLY_SAME_DAY_FORWARD_RECOVERY"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", required=True)
    ap.add_argument("--upstream", default="")
    ap.add_argument("--upstream-event", default="")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    day = now.astimezone(ROME).date().isoformat()
    is_hourly = args.event == "workflow_run" and args.upstream == HOURLY
    eligible_clock = (now.astimezone(ROME).weekday() < 5
                      and 19 <= now.astimezone(ROME).hour <= 23)
    check_files = is_hourly and args.upstream_event == "schedule" and eligible_clock
    v1_ok = completed_v1(V1, day) if check_files else False
    v2_ok = completed_v2(V2, day) if check_files else False
    quality_ok = completed_quality(QA, day) if (
        check_files and now.astimezone(ROME).date() >= QUALITY_FIRST_DAY
    ) else False
    result = evaluate(now, args.event, args.upstream, args.upstream_event,
                      v1_ok, v2_ok, quality_ok)
    result["v1_already_complete"] = v1_ok
    result["v2_already_complete"] = v2_ok
    result["quality_aware_already_complete"] = quality_ok
    if args.output:
        with args.output.open("a", encoding="utf-8") as stream:
            stream.write("eligible=" + str(result["eligible"]).lower() + "\n")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write("## Forward hourly recovery gate\n")
            stream.write("- Status: " + result["reason"] + "\n")
            stream.write("- Rome actual time: " + result["local_time"] + "\n")
            stream.write("- Capture permitted: " + str(result["eligible"]) + "\n")
    print("FORWARD_HOURLY_RECOVERY_GATE " + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
