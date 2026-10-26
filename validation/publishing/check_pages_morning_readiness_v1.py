#!/usr/bin/env python3
"""Fail-closed 04:00–10:00 Rome publisher gate, regardless of workflow trigger.

Outside the weekday study window the existing Pages structural and source
checks retain authority; this module does not reclassify historical Macro or
non-daily official observations as current.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "validation" / "orchestration"))
from check_morning_readiness_v1 import inspect, read_feeds  # noqa: E402

ROME = ZoneInfo("Europe/Rome")
START = dt.time(4, 0)
END = dt.time(10, 0)


def in_morning_window(instant: dt.datetime) -> bool:
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("Timezone-aware instant is required")
    local = instant.astimezone(ROME)
    return local.weekday() < 5 and START <= local.time().replace(tzinfo=None) < END


def evaluate(instant: dt.datetime, feeds: dict | None = None) -> dict:
    """Evaluate the immutable checkout being considered for Pages publication."""
    active = in_morning_window(instant)
    local = instant.astimezone(ROME)
    receipt = {
        "schema": "GMFQ_PAGES_MORNING_SOURCE_GATE_V1",
        "checked_at_rome": local.isoformat(timespec="seconds"),
        "window": "WEEKDAYS_04_00_TO_10_00_EUROPE_ROME",
        "morning_gate_required": active,
        "status": "PASS_OUTSIDE_MORNING_WINDOW",
        "critical_daily_problems": [],
        "documented_nonblocking_gaps": [],
        "news_content_vintage": None,
        "authority": "MORNING_SOURCE_READINESS" if active else "STANDARD_PAGES_PREFLIGHT",
    }
    if not active:
        return receipt
    try:
        report = inspect(read_feeds() if feeds is None else feeds, local, pipeline_outcome="success")
    except Exception as exc:
        receipt["status"] = "BLOCK_SOURCE_AUDIT_EXCEPTION"
        receipt["critical_daily_problems"] = [type(exc).__name__]
        receipt["error"] = str(exc)[:240]
        return receipt
    receipt["critical_daily_problems"] = report["critical_daily_problems"]
    receipt["documented_nonblocking_gaps"] = report.get("documented_nonblocking_gaps", [])
    receipt["news_content_vintage"] = report["evidence"].get("NEWS_CONTENT_VINTAGE")
    receipt["operational_state"] = report["operational_state"]
    receipt["expected_previous_weekday"] = report["expected_previous_weekday"]
    receipt["evidence_as_of"] = {
        key: report["evidence"][key]["as_of"]
        for key in ("FX_OFFICIAL_FIXING", "PAIR_PRICE", "VIX_OFFICIAL_CLOSE")
    }
    receipt["status"] = (
        "PASS_MORNING_SOURCES_VERIFIED"
        if report["operational_state"] == "DAILY_READY_WITH_DOCUMENTED_GAPS"
        and not report["critical_daily_problems"]
        else "BLOCK_MORNING_INPUTS_INCOMPLETE"
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", help="Timezone-aware ISO instant (test only)")
    parser.add_argument("--output", help="JSON audit evidence path")
    args = parser.parse_args()
    try:
        instant = (dt.datetime.fromisoformat(args.as_of)
                   if args.as_of else dt.datetime.now(dt.timezone.utc))
        result = evaluate(instant)
    except (ValueError, TypeError) as exc:
        parser.error(str(exc))
    if args.output:
        Path(args.output).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
