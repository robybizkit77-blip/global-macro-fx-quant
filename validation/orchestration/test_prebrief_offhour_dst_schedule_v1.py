#!/usr/bin/env python3
"""Fail-closed off-hour 04:43 Rome DST prebrief schedule regression.

The same 04:43 local time must select exactly one scheduled UTC entry on
each side of Europe/Rome DST. The complementary entry must be skipped.
This does not assert that GitHub guarantees cron start-time punctuality.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/daily-data-orchestrator-v2.yml"
ROME = ZoneInfo("Europe/Rome")
UTC = dt.timezone.utc

CRON_SUMMER = "43 2 * * 1-5"
CRON_WINTER = "43 3 * * 1-5"


def check():
    text = WORKFLOW.read_text(encoding="utf-8")
    before_guard = text.split("  schedule:", 1)[1].split("\npermissions:", 1)[0]
    for expression in (CRON_SUMMER, CRON_WINTER):
        assert before_guard.count("- cron: '" + expression + "'") == 1, expression
    assert "0 3 * * 1-5" not in before_guard
    assert "0 4 * * 1-5" not in before_guard
    assert ("'43 2 * * 1-5|2'|'43 3 * * 1-5|1') phase=prebrief ;;"
            in text)
    assert "phase=skip" in text
    # Only schedule/manual dispatch belong to the serialized production queue.
    # PR and push run contract checks alone and must not delay the 07:45 phase.
    queue = text.split("\nconcurrency:\n", 1)[1].split("\nenv:\n", 1)[0]
    assert "github.event_name == 'pull_request'" in queue
    assert "github.event.pull_request.number" in queue
    assert "github.event_name == 'push'" in queue
    assert "daily-data-orchestrator-v2-ci-pr-{0}" in queue
    assert "daily-data-orchestrator-v2-ci-push" in queue
    assert "|| 'daily-data-orchestrator-v2' }}" in queue
    assert "queue: max" in queue
    assert "cancel-in-progress: false" in queue
    assert ("if: ${{ github.event_name == 'schedule' || github.event_name == 'workflow_dispatch' }}"
            in text)
    assert text.count("    - cron:") == 10
    # Two Tuesday/Friday weekdays on either side of CET/CEST 2026 cutover.
    fixtures = (
        (dt.date(2026, 10, 23), 2, CRON_SUMMER),
        (dt.date(2026, 10, 27), 1, CRON_WINTER),
        (dt.date(2026, 3, 27), 1, CRON_WINTER),
        (dt.date(2026, 3, 30), 2, CRON_SUMMER),
    )
    for day, expected_offset, expected_cron in fixtures:
        local = dt.datetime.combine(day, dt.time(4, 43), ROME)
        assert local.weekday() < 5
        utc = local.astimezone(UTC)
        actual_offset = int(local.utcoffset().total_seconds() / 3600)
        assert actual_offset == expected_offset, (day, actual_offset)
        actual_cron = f"{utc.minute} {utc.hour} * * 1-5"
        assert actual_cron == expected_cron, (day, actual_cron, expected_cron)
        # The UTC companion entry is explicitly ignored by the offset gate.
        companion = CRON_WINTER if expected_cron == CRON_SUMMER else CRON_SUMMER
        assert companion != actual_cron
    print("PREBRIEF_OFFHOUR_ROME_DST_AND_UTC_GATE_PASS")


if __name__ == "__main__":
    check()
