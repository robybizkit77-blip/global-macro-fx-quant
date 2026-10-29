#!/usr/bin/env python3
"""Deterministic fallback cases: missed, failed, already green, DST, safety."""
from __future__ import annotations

import datetime as dt
from check_cb_pricing_recovery_v1 import decide

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
    assert decide(at(2026,10,29,10,31), [], lambda _: jobs(), 99)["status"] == "SKIP"
    assert decide(at(2026,10,31,6,30), [], lambda _: jobs(), 99)["reason"] == "ROME_WEEKEND"
    # Next Monday in CET, 07:30 local = 06:30 UTC; summer CEST = 05:30 UTC.
    assert decide(at(2026,11,2,6,30), [], lambda _: jobs(), 99)["status"] == "RUN"
    assert decide(at(2026,10,19,5,30), [], lambda _: jobs(), 99)["status"] == "RUN"
    # A time stamped prior day cannot suppress recovery.
    yesterday = run(21, "schedule", "2026-10-28T05:16:00Z")
    assert decide(now, [yesterday], lambda _: jobs(), 99)["status"] == "RUN"
    print("CB_PRICING_MISSED_CRON_RECOVERY_GATE_V1: PASS")


if __name__ == "__main__":
    check()
