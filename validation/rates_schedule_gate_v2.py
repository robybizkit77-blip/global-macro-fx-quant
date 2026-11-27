#!/usr/bin/env python3
"""Fail-closed Rome-local GitHub Actions scheduler gate for official G8 Rates.

An event's exact UTC cron expresses the scheduled 07:20 / 08:00 / 09:00
Rome slot. GitHub can start a run late; use the cron identity and the
Europe/Rome offset rather than the runner's current minute. Do not conflate
the CET/CEST duplicate cron expressions. The normal four-hour window
protects morning receipts. An admitted cron that starts after the local
afternoon refresh can still read official sources as evening recovery.

Morning recovery accepts successful MAIN-branch Macro scheduled runs as
well as the existing serialized Source-Watch -> News -> Macro workflow_run.
This covers a dropped independent Rates cron without trusting Macro push/PR
or manual dispatch. Evening recovery reuses completed, successful MAIN-branch *scheduled* runs
of the existing Hourly Certified Alert Readiness workflow. The independent
FREE hourly market desk is an additional after-22:00 fallback: it is a
separate real schedule, so a dropped Rates cron need not suppress source reads.
An 18:17 Rome slot checks the afternoon feeds; a 22:17 slot checks again
after the US Treasury fixing. Both evening slots can start after midnight
before morning recovery opens at 05:00, using their original business day.
Reject mismatched upstream identities and non-business-day schedule slots.
This gives late official North American rates a second real read before the
next day's morning pipeline; it NEVER advances unavailable source observations.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
UTC = dt.timezone.utc
MAX_QUEUE_DELAY_MINUTES = 240
EVENING_REFRESH_TIME = dt.time(18, 17)
MORNING_RECOVERY_START = dt.time(5)
OVERNIGHT_RECOVERY_CRONS = {"17 18 * * 1-5", "17 22 * * 1-5"}
SLOTS = {
    "20 5 * * 1-5": {2: "07:20"},
    "20 6 * * 1-5": {1: "07:20"},
    "0 6 * * 1-5": {2: "08:00"},
    # UTC 07:00 means 09:00 CEST or 08:00 CET.
    "0 7 * * 1-5": {2: "09:00", 1: "08:00"},
    "0 8 * * 1-5": {1: "09:00"},
    # Each of these entries is a single native Europe/Rome cron.
    "17 18 * * 1-5": {1: "18:17", 2: "18:17"},
    "17 22 * * 1-5": {1: "22:17", 2: "22:17"},
}


def resolve(event: str, cron: str, now: dt.datetime, *,
            upstream_name: str = "", upstream_event: str = "",
            upstream_conclusion: str = "", upstream_head_branch: str = "") -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("offset-aware timestamp required")
    local = now.astimezone(ROME)
    out = {
        "schema": "GMFQ_RATES_SCHEDULE_GATE_V2",
        "event": event,
        "cron": cron,
        "runner_started_at_rome": local.isoformat(),
        "slot_rome": None,
        "should_run": False,
        "reason": "",
    }
    if event == "workflow_run":
        out["upstream_name"] = upstream_name
        out["upstream_event"] = upstream_event
        out["upstream_conclusion"] = upstream_conclusion
        out["upstream_head_branch"] = upstream_head_branch
        # Accept only trusted scheduled Macro or serialized Source-Watch
        # recovery. A scheduled Macro completion supplies a safety-net when
        # the independent Rates cron is delayed or dropped by GitHub.
        # Never respond to Macro push/PR/manual jobs as market-source evidence.
        morning = (upstream_name == "Macro Persistent Daily V1"
                   and upstream_event in ("workflow_run", "schedule"))
        evening_primary = (upstream_name == "Hourly Certified Alert Readiness V1"
                           and upstream_event == "schedule")
        evening_backup = (upstream_name == "FX Quant Next Independent FREE Hourly Desk"
                          and upstream_event == "schedule")
        evening = evening_primary or evening_backup
        if (not (morning or evening)
                or upstream_conclusion != "success"
                or upstream_head_branch != "main"):
            out["reason"] = "UNTRUSTED_OR_NON_SCHEDULED_UPSTREAM"
            return out
        if local.weekday() >= 5:
            out["reason"] = ("MORNING_RECOVERY_WEEKEND" if morning
                             else "EVENING_RECOVERY_WEEKEND")
            return out
        if morning:
            if not (MORNING_RECOVERY_START <= local.time() < dt.time(10)):
                out["reason"] = "OUTSIDE_MORNING_MACRO_RECOVERY_WINDOW"
                return out
            out.update(should_run=True,
                       reason="TRUSTED_SERIAL_MACRO_MORNING_RATES_RECOVERY")
            return out
        # The primary hourly schedule can also recover missing morning Rates
        # crons. This is permission to READ sources, never proof of a close
        # or timely publication. Keep the backup desk evening-only.
        if evening_primary and dt.time(7,20) <= local.time() < dt.time(10):
            out.update(should_run=True,
                       reason="TRUSTED_SCHEDULED_HOURLY_MORNING_RATES_RECOVERY")
            return out
        if not (19 <= local.hour <= 23):
            out["reason"] = "OUTSIDE_EVENING_SOURCE_PUBLICATION_WINDOW"
            return out
        # The independent desk is a backup only after the US Treasury fixing.
        # Never trust its earlier hourly editions to certify the US close.
        if evening_backup and local.hour < 22:
            out["reason"] = "FREE_HOURLY_BACKUP_BEFORE_TREASURY_WINDOW"
            return out
        out.update(should_run=True,
                   reason="TRUSTED_SCHEDULED_HOURLY_EVENING_RATES_RECOVERY")
        return out
    if event not in ("schedule", "workflow_dispatch", "push", "pull_request"):
        out["reason"] = "UNKNOWN_EVENT_FAIL_CLOSED"
        return out
    # PR contract CI must not fetch/promote official market data or try to
    # write the operational main branch. Production push/dispatch still run.
    if event == "pull_request":
        out["reason"] = "PULL_REQUEST_CONTRACT_ONLY"
        return out
    if event != "schedule":
        out.update(should_run=True, reason="EXPLICIT_EVENT")
        return out
    slot = SLOTS.get(cron)
    if slot is None:
        out["reason"] = "UNKNOWN_CRON_FAIL_CLOSED"
        return out
    scheduled_date = local.date()
    overnight = cron in OVERNIGHT_RECOVERY_CRONS and local.time() < MORNING_RECOVERY_START
    if overnight:
        scheduled_date -= dt.timedelta(days=1)
    if scheduled_date.weekday() >= 5:
        out["reason"] = "NOT_BUSINESS_DAY"
        return out
    actual_offset = int(local.utcoffset().total_seconds() // 3600)
    clock = slot.get(actual_offset)
    if clock is None:
        out["reason"] = "DUPLICATE_CET_CEST_UTC_SLOT"
        return out
    out["slot_rome"] = clock
    hh, mm = (int(part) for part in clock.split(":"))
    scheduled = dt.datetime.combine(scheduled_date, dt.time(hh, mm), tzinfo=ROME)
    elapsed = int((now.astimezone(UTC) - scheduled.astimezone(UTC)).total_seconds() // 60)
    out["scheduled_at_rome"] = scheduled.isoformat()
    out["queue_delay_minutes"] = elapsed
    if elapsed < 0:
        out["reason"] = "BEFORE_SCHEDULED_SLOT"
        return out
    if overnight:
        out.update(should_run=True, reason="OVERNIGHT_EVENING_RATES_RECOVERY")
        return out
    if elapsed > MAX_QUEUE_DELAY_MINUTES:
        if local.time() >= EVENING_REFRESH_TIME:
            out.update(should_run=True, reason="LATE_CRON_EVENING_RATES_RECOVERY")
            return out
        out["reason"] = "STALE_DELAYED_RUN"
        return out
    out.update(should_run=True, reason="VALID_RATES_SLOT_DELAY_TOLERANT")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", required=True)
    ap.add_argument("--cron", default="")
    ap.add_argument("--upstream-name", default="")
    ap.add_argument("--upstream-event", default="")
    ap.add_argument("--upstream-conclusion", default="")
    ap.add_argument("--upstream-head-branch", default="")
    ap.add_argument("--output")
    ap.add_argument("--summary")
    args = ap.parse_args()
    result = resolve(args.event, args.cron, dt.datetime.now(UTC),
                     upstream_name=args.upstream_name,
                     upstream_event=args.upstream_event,
                     upstream_conclusion=args.upstream_conclusion,
                     upstream_head_branch=args.upstream_head_branch)
    print("RATES_SCHEDULE_GATE_V2 " + json.dumps(result, sort_keys=True), flush=True)
    if args.output:
        with Path(args.output).open("a", encoding="utf-8") as file:
            file.write("should_run=" + ("true" if result["should_run"] else "false") + "\n")
            file.write("schedule_reason=" + result["reason"] + "\n")
    if args.summary:
        with Path(args.summary).open("a", encoding="utf-8") as file:
            file.write("### G8 Official Rates UTC/Rome schedule gate\n\n")
            file.write(f"- Result: **{'RUN' if result['should_run'] else 'SKIPPED_INTENTIONALLY'}**\n")
            file.write(f"- Reason: {result['reason']}\n")
            file.write(f"- Runner: {result['runner_started_at_rome']}\n")
            if result["slot_rome"]:
                file.write(f"- Scheduled Rome slot: {result['scheduled_at_rome']}\n")
                file.write(f"- Queue delay (min): {result.get('queue_delay_minutes', 'n/a')}\n")


if __name__ == "__main__":
    main()
