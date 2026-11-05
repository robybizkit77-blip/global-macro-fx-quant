#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt

from ois_g8_schedule_gate_v1 import CEST_CRON, CET_CRON, gate


def at(year, month, day, hour, minute):
    return dt.datetime(year, month, day, hour, minute, tzinfo=dt.timezone.utc)


def main():
    # October 19 was DST. A scheduled 06:15Z that starts 07:53Z (09:53
    # Rome) MUST perform the refresh, rather than reporting success but skipping.
    assert gate("schedule", CEST_CRON, at(2026, 10, 19, 7, 53))[0] is True
    assert gate("schedule", CET_CRON, at(2026, 10, 19, 7, 53)) == (False, "DUPLICATE_DST_UTC_SLOT")
    assert gate("schedule", CEST_CRON, at(2026, 10, 19, 6, 10)) == (False, "BEFORE_SCHEDULED_LOCAL_TIME")
    # November 2 is standard time: only 07:15Z is accepted.
    assert gate("schedule", CET_CRON, at(2026, 11, 2, 8, 55))[0] is True
    assert gate("schedule", CEST_CRON, at(2026, 11, 2, 8, 55)) == (False, "DUPLICATE_DST_UTC_SLOT")
    # Never authorize a weekend or wrong slot, but manual runs must be allowed.
    assert gate("schedule", CEST_CRON, at(2026, 10, 24, 6, 30)) == (False, "NOT_WORKDAY")
    assert gate("workflow_dispatch", "", at(2026, 10, 19, 5, 30))[0] is True
    assert gate("push", "", at(2026, 10, 19, 12, 0))[0] is True
    # Missed 08:15 OIS cron can be recovered by a separate successful
    # Rates Persistent main run completed that day, never by PR or stale job.
    parent = {
        "upstream_name": "Rates Persistent Daily V1",
        "upstream_branch": "main",
        "upstream_conclusion": "success",
        "upstream_event": "workflow_run",
        "upstream_started_at": "2026-11-05T07:10:21Z",
    }
    assert gate("workflow_run", "", at(2026, 11, 5, 8, 32), **parent) == (
        True, "INDEPENDENT_SUCCESSFUL_MAIN_RATES_RECOVERY")
    assert gate("workflow_run", "", at(2026, 11, 5, 6, 55), **parent) == (
        False, "BEFORE_OIS_0815_ROME_TARGET")
    for field, value in [
        ("upstream_branch", "fix/check"),
        ("upstream_conclusion", "failure"),
        ("upstream_name", "Wrong workflow"),
        ("upstream_event", "pull_request"),
    ]:
        bad = dict(parent, **{field: value})
        assert gate("workflow_run", "", at(2026, 11, 5, 8, 32), **bad) == (
            False, "UNTRUSTED_OR_FAILED_RATES_PARENT"), (field, bad)
    assert gate("workflow_run", "", at(2026, 11, 5, 8, 32),
                **dict(parent, upstream_started_at="2026-11-04T07:10:21Z")) == (
        False, "PARENT_OUTSIDE_CURRENT_ROME_DAY")
    assert gate("workflow_run", "", at(2026, 11, 5, 8, 32),
                **dict(parent, upstream_started_at="invalid")) == (
        False, "UNVERIFIED_PARENT_START_TIME")
    assert gate("workflow_run", "", at(2026, 11, 7, 8, 32),
                **dict(parent, upstream_started_at="2026-11-07T07:10:21Z")) == (
        False, "NOT_WORKDAY")
    # Summer 08:15 means 06:15Z; a 07:10Z parent is still same Rome day.
    assert gate("workflow_run", "", at(2026, 7, 2, 6, 24),
                **dict(parent, upstream_started_at="2026-07-02T05:01:00Z")) == (
        True, "INDEPENDENT_SUCCESSFUL_MAIN_RATES_RECOVERY")
    # Contract wiring: the independent fallback must be actually connected
    # and must not enable any untrusted upstream.
    from pathlib import Path
    workflow = (Path(__file__).resolve().parents[2] /
                ".github/workflows/ois-g8-history-persistent-daily-v1.yml").read_text()
    assert "workflows: ['Rates Persistent Daily V1']" in workflow
    for val in ("--upstream-name", "--upstream-conclusion",
                "--upstream-branch", "--upstream-event", "--upstream-started-at",
                "--output \"$GITHUB_OUTPUT\""):
        assert val in workflow, val
    assert "ref: ${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha || 'main' }}" in workflow
    assert "sha256sum -c /tmp/OIS_DATA.before.sha256" in workflow
    print("OIS_G8_RATES_MAIN_WORKFLOW_RECOVERY_GATE_V1: PASS")
    print("OIS_G8_DST_DELAYED_SCHEDULE_GATE_V1: PASS")


if __name__ == "__main__":
    main()
