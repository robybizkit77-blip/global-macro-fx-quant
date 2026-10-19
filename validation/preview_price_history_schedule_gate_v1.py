#!/usr/bin/env python3
"""ECB G8 price-history scheduler for the active site/control-room-preview.

GitHub scheduled workflows can start many minutes after their UTC cron. Decide
whether this is the intended Europe/Rome 17:25, 17:55 or 18:25 slot by the
*scheduled cron*, not the runner's exact minute. The overlapping UTC 16:25
represents 18:25 CEST or 17:25 CET, never both.

Price-history data, pair scores and FX signals are NOT modified by this gate.
Only the existing, official-source ECB candidate workflow may run.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
UTC = dt.timezone.utc
MAX_DELAY_MINUTES = 180
CRON_TO_LOCAL = {
    "25 15 * * 1-5": {2: "17:25"},
    "25 16 * * 1-5": {1: "17:25", 2: "18:25"},
    "25 17 * * 1-5": {1: "18:25"},
    "55 15 * * 1-5": {2: "17:55"},
    "55 16 * * 1-5": {1: "17:55"},
}


def resolve(event: str, cron: str, now: dt.datetime) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    local = now.astimezone(ROME)
    result = {
        "schema": "GMFQ_PREVIEW_PRICE_HISTORY_SCHEDULE_GATE_V1",
        "event": event,
        "cron": cron,
        "runner_started_at_rome": local.isoformat(),
        "local_slot": None,
        "should_run": False,
        "reason": "",
    }
    if event != "schedule":
        result.update(should_run=True, reason="EXPLICIT_MANUAL_OR_CI_EVENT")
        return result
    offsets = CRON_TO_LOCAL.get(cron)
    if not offsets:
        result["reason"] = "UNRECOGNIZED_CRON"
        return result
    if local.weekday() > 4:
        result["reason"] = "NOT_ROME_BUSINESS_DAY"
        return result
    offset = int(local.utcoffset().total_seconds() // 3600)
    clock = offsets.get(offset)
    if clock is None:
        result["reason"] = "CET_CEST_DUPLICATE_CRON"
        return result
    result["local_slot"] = clock
    hour, minute = map(int, clock.split(":"))
    due_local = dt.datetime.combine(local.date(), dt.time(hour, minute), tzinfo=ROME)
    late_minutes = int((now.astimezone(UTC) - due_local.astimezone(UTC)).total_seconds() // 60)
    result["queue_delay_minutes"] = late_minutes
    if late_minutes < 0:
        result["reason"] = "BEFORE_SLOT"
    elif late_minutes > MAX_DELAY_MINUTES:
        result["reason"] = "EXPIRED_QUEUE_WINDOW"
    else:
        result.update(should_run=True, reason="VALID_DELAY_TOLERANT_ROME_PRICE_HISTORY_SLOT")
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", required=True)
    ap.add_argument("--cron", default="")
    ap.add_argument("--output")
    ap.add_argument("--summary")
    args = ap.parse_args()
    out = resolve(args.event, args.cron, dt.datetime.now(UTC))
    print("PREVIEW_PRICE_HISTORY_SCHEDULE_GATE_V1 " + json.dumps(out, sort_keys=True), flush=True)
    if args.output:
        with Path(args.output).open("a", encoding="utf-8") as stream:
            stream.write("should_run=" + ("true" if out["should_run"] else "false") + "\n")
            stream.write("schedule_reason=" + out["reason"] + "\n")
    if args.summary:
        with Path(args.summary).open("a", encoding="utf-8") as stream:
            stream.write("### Active Control Room Preview · ECB G8 history scheduler\n\n")
            stream.write(f"- {'RUN' if out['should_run'] else 'SKIPPED_INTENTIONALLY'}: {out['reason']}\n")
            stream.write(f"- Rome runner time: {out['runner_started_at_rome']}\n")
            stream.write(f"- Scheduled Rome slot: {out['local_slot']}\n")
            if "queue_delay_minutes" in out:
                stream.write(f"- GitHub Actions queue delay: {out['queue_delay_minutes']} min\n")


if __name__ == "__main__":
    main()
