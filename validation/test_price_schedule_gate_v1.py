#!/usr/bin/env python3
"""ECB Price scheduled timezones: correct UTC cron, delay tolerance, no DST doubles."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

from price_schedule_gate_v1 import SLOTS, gate

UTC = dt.timezone.utc
ROME = ZoneInfo("Europe/Rome")


def t(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def assert_gate(event: str, cron: str, instant: str, allowed: bool, reason: str):
    result = gate(event, cron, t(instant))
    assert result["should_run"] is allowed, result
    assert result["reason"] == reason, result
    return result


def main():
    assert len(SLOTS) == 6
    ok = "VALID_ROME_PRICE_SLOT_DELAY_TOLERANT"
    wrong_offset = "DUPLICATE_DST_UTC_SLOT"

    # Monday 19 October is CEST (+2); these are the three valid UTC crons.
    for cron, instant, slot in (
        ("10 15 * * 1-5", "2026-10-19T15:10:00Z", "17:10"),
        ("40 15 * * 1-5", "2026-10-19T15:40:00Z", "17:40"),
        ("10 17 * * 1-5", "2026-10-19T16:10:00Z", "18:10"),
    ):
        r = assert_gate("schedule", cron, instant, True, ok)
        assert r["slot_local_time"] == slot, r

    # GitHub has already been seen running 80+ minutes late. A correct cron
    # must still attempt the refresh, instead of silently doing no work.
    assert_gate("schedule", "10 15 * * 1-5", "2026-10-19T16:31:00Z", True, ok)
    assert_gate("schedule", "40 15 * * 1-5", "2026-10-19T16:31:00Z", True, ok)
    assert_gate("schedule", "10 17 * * 1-5", "2026-10-19T17:55:00Z", True, ok)
    assert_gate("schedule", "10 16 * * 1-5", "2026-10-19T16:10:00Z", False, wrong_offset)
    assert_gate("schedule", "40 16 * * 1-5", "2026-10-19T16:45:00Z", False, wrong_offset)
    assert_gate("schedule", "10 18 * * 1-5", "2026-10-19T18:12:00Z", False, wrong_offset)

    # First Monday after DST ends 26 Oct: offset switches to CET (+1).
    for cron, instant in (
        ("10 16 * * 1-5", "2026-10-26T16:14:00Z"),
        ("40 16 * * 1-5", "2026-10-26T16:44:00Z"),
        ("10 18 * * 1-5", "2026-10-26T18:15:00Z"),
    ):
        assert_gate("schedule", cron, instant, True, ok)
    for cron, instant in (
        ("10 15 * * 1-5", "2026-10-26T16:12:00Z"),
        ("40 15 * * 1-5", "2026-10-26T16:42:00Z"),
        ("10 17 * * 1-5", "2026-10-26T17:30:00Z"),
    ):
        assert_gate("schedule", cron, instant, False, wrong_offset)

    assert_gate("schedule", "10 15 * * 1-5", "2026-10-19T15:09:00Z", False, "BEFORE_LOCAL_SCHEDULED_SLOT")
    assert_gate("schedule", "20 15 * * 1-5", "2026-10-19T15:20:00Z", False, "UNKNOWN_CRON_FAIL_CLOSED")
    assert_gate("schedule", "10 15 * * 1-5", "2026-10-24T15:12:00Z", False, "NOT_LOCAL_BUSINESS_DAY")
    for event in ("workflow_dispatch", "push", "pull_request", "workflow_run"):
        assert_gate(event, "", "2026-10-19T12:00:00Z", True, "MANUAL_OR_PUSH_OR_PR")

    # Existing official ECB history workflow provides an independent after-
    # publication trigger. No new crons, no duplicate writes, no PR/failed
    # parent, and no replacement of queued production retries.
    workflow = (Path(__file__).resolve().parents[1] /
                ".github/workflows/price-persistent-daily-v1.yml").read_text(encoding="utf-8")
    assert "workflow_run:" in workflow
    trigger = workflow.split("  workflow_run:", 1)[1].split("  workflow_dispatch:", 1)[0]
    assert "workflows: ['Price History Persistent Daily V1']" in trigger
    assert "types: [completed]" in trigger
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "github.event.workflow_run.head_branch == 'main'" in workflow
    assert "github.event.workflow_run.event != 'pull_request'" in workflow
    assert "queue: max" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "price-validation-pr-{0}" in workflow
    assert workflow.count("    - cron:") == 6

    try:
        gate("schedule", "10 15 * * 1-5", dt.datetime(2026, 10, 19))
        raise AssertionError("naive time unexpectedly accepted")
    except ValueError:
        pass

    print("PRICE_DAILY_GATE_DELAY_DST_V1_PASS")


if __name__ == "__main__":
    main()
