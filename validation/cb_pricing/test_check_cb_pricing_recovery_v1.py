#!/usr/bin/env python3
"""Deterministic fallback cases: missed, failed, already green, DST, safety."""
from __future__ import annotations

import datetime as dt
from check_cb_pricing_recovery_v1 import decide, build_receipt

UTC = dt.timezone.utc


def at(y,m,d,h,mi):
    return dt.datetime(y,m,d,h,mi,tzinfo=UTC)


def run(id, event, started, conclusion="success", status="completed", head_branch="main"):
    return {
        "id": id, "event": event, "run_started_at": started,
        "conclusion": conclusion, "status": status, "head_branch": head_branch,
    }


def jobs(green=True):
    return [{"name":"persist-cb-pricing", "conclusion":"success" if green else "failure",
             "steps":[
                 {"name":"Run per-currency certified dry-run preflight", "conclusion":"success" if green else "failure"},
                 {"name":"Apply independently certified source candidates only", "conclusion":"success" if green else "skipped"},
             ]}]


def check():
    # CET Oct 29 07:30, after the third planned 07:13 slot.
    now = at(2026,10,29,6,30)
    missing = decide(now, [], lambda _: jobs(), 99)
    assert missing["status"] == "RUN" and missing["reason"] == "NO_SCHEDULE_DELIVERED_RECOVER", missing
    bad = run(10, "schedule", "2026-10-29T05:15:00Z", "failure")
    x = decide(now, [bad], lambda _: jobs(False), 99)
    assert x["status"] == "RUN" and x["reason"] == "NO_SUCCESSFUL_PRODUCER_RECOVER", x
    good = run(11, "workflow_dispatch", "2026-10-29T05:15:00Z")
    y = decide(now, [good], lambda _: jobs(), 99)
    assert y["status"] == "SKIP" and y["reason"] == "ALREADY_PRODUCED_TODAY", y
    # A successful GitHub *run* whose substantive producer steps were skipped is not proof.
    skipped = run(12, "workflow_run", "2026-10-29T05:16:00Z")
    z = decide(now, [skipped], lambda _: jobs(False), 99)
    assert z["status"] == "RUN", z
    assert decide(now, [bad, good], lambda _: jobs(), 99)["status"] == "SKIP"
    # Only main and correct day qualify. PR and own in-flight run never qualify.
    wrong_branch = run(14, "workflow_dispatch", "2026-10-29T06:00:00Z", head_branch="test")
    assert decide(now, [wrong_branch], lambda _: jobs(), 99)["status"] == "RUN"
    assert decide(now, [run(99, "workflow_run", "2026-10-29T06:29:00Z")], lambda _: jobs(), 99)["status"] == "RUN"
    assert decide(at(2026,10,29,5,30), [], lambda _: jobs(), 99)["status"] == "SKIP"
    assert decide(at(2026,10,29,16,31), [], lambda _: jobs(), 99)["status"] == "SKIP"
    assert decide(at(2026,10,31,6,30), [], lambda _: jobs(), 99)["reason"] == "ROME_WEEKEND"
    # Next Monday in CET, 07:30 local = 06:30 UTC; summer CEST = 05:30 UTC.
    assert decide(at(2026,11,2,6,30), [], lambda _: jobs(), 99)["status"] == "RUN"
    assert decide(at(2026,10,19,5,30), [], lambda _: jobs(), 99)["status"] == "RUN"
    # Late parent completion still recovers (never claims 08:00 compliance).
    late = decide(at(2026,10,29,12,30), [bad], lambda _: jobs(False), 99)
    assert late["status"] == "RUN" and late["late_recovery"] is True, late
    assert missing["late_recovery"] is False, missing

    # Weekends/out-of-window skip entirely without calling GitHub API.
    def should_not_call_api(_):
        raise AssertionError("OUT_OF_WINDOW_API_READ_NOT_ALLOWED")

    early = build_receipt(at(2026,10,29,5,0), 99, should_not_call_api)
    assert early["status"] == "SKIP" and early["api_read_performed"] is False
    weekend = build_receipt(at(2026,10,31,12,30), 99, should_not_call_api)
    assert weekend["status"] == "SKIP" and weekend["api_read_performed"] is False
    night = build_receipt(at(2026,10,29,18,0), 99, should_not_call_api)
    assert night["status"] == "SKIP" and night["api_read_performed"] is False

    # API response demonstrates same-day substantive success: do not retry.
    paths = []
    def fake_api(path):
        paths.append(path)
        if "/jobs?" in path:
            return {"jobs": jobs()}
        return {"workflow_runs": [good]}

    already_done = build_receipt(now, 99, fake_api)
    assert already_done["status"] == "SKIP" and already_done["api_read_performed"] is True
    assert len(paths) == 2, paths

    # Incomplete API history must NEVER manufacture 'no earlier success'.
    truncated = [
        {**run(1000 + i, "workflow_run", "2026-10-29T06:00:00Z"),
         "created_at": "2026-10-29T06:00:00Z"} for i in range(100)
    ]
    try:
        build_receipt(now, 99, lambda _: {"workflow_runs": truncated})
    except ValueError as exc:
        assert str(exc) == "GITHUB_RUN_HISTORY_PAGE_TRUNCATED_FAIL_CLOSED"
    else:
        raise AssertionError("TRUNCATED_RUN_HISTORY_NOT_REJECTED")

    # A time stamped prior day cannot suppress recovery.
    yesterday = run(21, "schedule", "2026-10-28T05:16:00Z")
    assert decide(now, [yesterday], lambda _: jobs(), 99)["status"] == "RUN"
    print("CB_PRICING_MISSED_CRON_RECOVERY_GATE_V1: PASS")


if __name__ == "__main__":
    check()
