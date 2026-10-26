#!/usr/bin/env python3
"""Regression cases for both DST seasons and delayed GitHub Actions."""
from __future__ import annotations

import datetime as dt
from cb_pricing_schedule_gate_v1 import gate
from pathlib import Path

# 06:00, 06:30 and 07:00 independent retries must never replace each other
# while an earlier source acquisition is in progress.
ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/cb-pricing-persistent-daily-v1.yml").read_text()
QUEUE = WORKFLOW.split("concurrency:", 1)[1].split("jobs:", 1)[0]
assert "github.event_name == 'pull_request'" in QUEUE
assert "format('cb-pricing-validation-pr-{0}', github.event.pull_request.number)" in QUEUE
assert "|| 'cb-pricing-persistent-daily-v1'" in QUEUE
assert "queue: max" in QUEUE
assert "cancel-in-progress: false" in QUEUE


def at(year, month, day, hour, minute):
    return dt.datetime(year, month, day, hour, minute, tzinfo=dt.timezone.utc)


def main():
    # CEST on Monday Oct 19: UTC 04:00/04:30/05:00 map to Rome morning.
    for cron in ("0 4 * * 1-5", "30 4 * * 1-5", "0 5 * * 1-5"):
        assert gate("schedule", cron, at(2026, 10, 19, 7, 53)) == (
            True, "VALID_ROME_SLOT_DELAY_TOLERANT"
        ), cron
    assert gate("schedule", "0 4 * * 1-5", at(2026, 10, 19, 3, 59)) == (
        False, "BEFORE_SCHEDULED_LOCAL_SLOT"
    )
    for cron in ("30 5 * * 1-5", "0 6 * * 1-5"):
        assert gate("schedule", cron, at(2026, 10, 19, 7, 53)) == (
            False, "WRONG_CET_CEST_UTC_SLOT"
        )
    # CET on Monday Nov 2: UTC 05:00/05:30/06:00 map to Rome morning.
    for cron in ("0 5 * * 1-5", "30 5 * * 1-5", "0 6 * * 1-5"):
        assert gate("schedule", cron, at(2026, 11, 2, 8, 41))[0] is True, cron
    for cron in ("0 4 * * 1-5", "30 4 * * 1-5"):
        assert gate("schedule", cron, at(2026, 11, 2, 8, 41)) == (
            False, "WRONG_CET_CEST_UTC_SLOT"
        ), cron
    assert gate("schedule", "0 6 * * 1-5", at(2026, 11, 2, 5, 59)) == (
        False, "BEFORE_SCHEDULED_LOCAL_SLOT"
    )
    assert gate("schedule", "0 4 * * 1-5", at(2026, 10, 24, 5, 0)) == (
        False, "NOT_ROME_WORKDAY"
    )
    assert gate("schedule", "0 8 * * 1-5", at(2026, 10, 19, 7, 53)) == (
        False, "WRONG_CET_CEST_UTC_SLOT"
    )
    assert gate("workflow_dispatch", "", at(2026, 10, 24, 5, 0))[0] is True
    assert gate("push", "", at(2026, 10, 19, 12, 2))[0] is True
    assert gate("pull_request", "", at(2026, 10, 19, 2, 50))[0] is True
    print("CB_PRICING_ROME_DST_DELAYED_SCHEDULE_GATE_V1: PASS")


if __name__ == "__main__":
    main()
