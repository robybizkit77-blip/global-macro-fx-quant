#!/usr/bin/env python3
"""Deterministic Rome summer/winter duplicate-cron and delayed-run tests."""
from __future__ import annotations
import datetime as dt
from preview_price_history_schedule_gate_v1 import CRON_TO_LOCAL, resolve, MAX_DELAY_MINUTES


def instant(raw: str) -> dt.datetime:
    return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))


def check(event, cron, time, allowed, reason, slot=None):
    r = resolve(event, cron, instant(time))
    assert r["should_run"] is allowed, (event, cron, time, r)
    assert r["reason"] == reason, (event, cron, time, r)
    if slot is not None:
        assert r["local_slot"] == slot, (cron, time, r)
    return r


def main():
    assert len(CRON_TO_LOCAL) == 5
    assert MAX_DELAY_MINUTES == 180
    good = "VALID_DELAY_TOLERANT_ROME_PRICE_HISTORY_SLOT"
    catchup = "VALID_LATE_DUPLICATE_CATCHUP_SLOT"
    # October 19 is CEST (+02:00); UTC 16:25 is its 18:25 slot.
    for cron, utc, local in (
        ("25 15 * * 1-5", "2026-10-19T15:25:00Z", "17:25"),
        ("55 15 * * 1-5", "2026-10-19T15:55:00Z", "17:55"),
        ("25 16 * * 1-5", "2026-10-19T16:25:00Z", "18:25"),
    ):
        check("schedule", cron, utc, True, good, local)
    # 50 / 100 minute Github delays used to result in green-but-skipped jobs.
    check("schedule", "25 15 * * 1-5", "2026-10-19T16:15:00Z", True, good, "17:25")
    check("schedule", "55 15 * * 1-5", "2026-10-19T17:35:00Z", True, good, "17:55")
    check("schedule", "25 16 * * 1-5", "2026-10-19T17:25:00Z", True, good, "18:25")
    # CET October 26 UTC 16:25 corresponds to 17:25, not 18:25.
    for cron, utc, local in (
        ("25 16 * * 1-5", "2026-10-26T16:25:00Z", "17:25"),
        ("55 16 * * 1-5", "2026-10-26T16:55:00Z", "17:55"),
        ("25 17 * * 1-5", "2026-10-26T17:25:00Z", "18:25"),
    ):
        check("schedule", cron, utc, True, good, local)
    check("schedule", "25 15 * * 1-5", "2026-10-26T15:25:00Z", False, "CET_CEST_DUPLICATE_CRON")
    check("schedule", "55 15 * * 1-5", "2026-10-26T15:55:00Z", False, "CET_CEST_DUPLICATE_CRON")
    # Out-of-season slots normally skip BEFORE the valid Rome window. If
    # delayed past it, reuse the existing cron as an idempotent recovery.
    check("schedule", "25 15 * * 1-5", "2026-10-28T16:09:31Z", False, "CET_CEST_DUPLICATE_CRON", "17:25")
    check("schedule", "55 15 * * 1-5", "2026-10-28T16:35:17Z", True, catchup, "17:25")
    check("schedule", "25 17 * * 1-5", "2026-10-19T17:25:00Z", True, catchup, "18:25")
    check("schedule", "55 16 * * 1-5", "2026-10-19T16:55:00Z", True, catchup, "18:25")
    check("schedule", "55 15 * * 1-5", "2026-10-28T19:26:00Z", False, "EXPIRED_QUEUE_WINDOW", "17:25")
    check("schedule", "25 16 * * 1-5", "2026-10-19T16:24:00Z", False, "BEFORE_SLOT")
    check("schedule", "25 16 * * 1-5", "2026-10-19T19:25:00Z", True, good, "18:25")
    check("schedule", "25 16 * * 1-5", "2026-10-19T19:26:00Z", False, "EXPIRED_QUEUE_WINDOW")
    check("schedule", "25 16 * * 1-5", "2026-10-24T16:25:00Z", False, "NOT_ROME_BUSINESS_DAY")
    check("schedule", "30 16 * * 1-5", "2026-10-19T16:30:00Z", False, "UNRECOGNIZED_CRON")
    for event in ("workflow_dispatch", "pull_request", "push"):
        check(event, "", "2026-10-19T11:20:00Z", True, "EXPLICIT_MANUAL_OR_CI_EVENT")
    try:
        resolve("schedule", "25 15 * * 1-5", dt.datetime(2026, 10, 19, 15, 25))
        raise AssertionError("naive datetime unexpectedly accepted")
    except ValueError:
        pass
    print("PREVIEW_ECB_HISTORY_SLOT_CEST_CET_DELAY_V1_PASS")


if __name__ == "__main__":
    main()
