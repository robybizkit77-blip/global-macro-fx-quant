#!/usr/bin/env python3
"""Rates cron regression: 3 Rome slots across CET/CEST, delay and quarantine."""
from __future__ import annotations

import datetime as dt

from rates_schedule_gate_v2 import MAX_QUEUE_DELAY_MINUTES, SLOTS, resolve


def iso(t: str) -> dt.datetime:
    return dt.datetime.fromisoformat(t.replace("Z", "+00:00"))


def check(event, cron, stamp, expected, why, slot=None):
    a = resolve(event, cron, iso(stamp))
    assert a["should_run"] is expected and a["reason"] == why, a
    if slot:
        assert a["slot_rome"] == slot, a
    return a


def run():
    assert len(SLOTS) == 5
    assert MAX_QUEUE_DELAY_MINUTES == 240
    ok = "VALID_RATES_SLOT_DELAY_TOLERANT"
    # CEST: Mon 19 Oct UTC 05:20 / 06:00 / 07:00 = 07:20 / 08:00 / 09:00 Rome.
    for cron, time, slot in (
        ("20 5 * * 1-5", "2026-10-19T05:20:00Z", "07:20"),
        ("0 6 * * 1-5", "2026-10-19T06:00:00Z", "08:00"),
        ("0 7 * * 1-5", "2026-10-19T07:00:00Z", "09:00"),
    ):
        check("schedule", cron, time, True, ok, slot)
    # Queue starts more than 20min after scheduled: still runs.
    check("schedule", "20 5 * * 1-5", "2026-10-19T06:25:00Z", True, ok, "07:20")
    check("schedule", "0 6 * * 1-5", "2026-10-19T07:05:00Z", True, ok, "08:00")
    check("schedule", "0 7 * * 1-5", "2026-10-19T08:05:00Z", True, ok, "09:00")
    # 4-hour upper bound: prevents yesterday's refresh running on a new day.
    check("schedule", "0 7 * * 1-5", "2026-10-19T11:00:00Z", True, ok)
    check("schedule", "0 7 * * 1-5", "2026-10-19T11:01:00Z", False, "STALE_DELAYED_RUN")
    check("schedule", "0 7 * * 1-5", "2026-10-19T06:59:00Z", False, "BEFORE_SCHEDULED_SLOT")
    check("schedule", "20 6 * * 1-5", "2026-10-19T06:20:00Z", False, "DUPLICATE_CET_CEST_UTC_SLOT")
    check("schedule", "0 8 * * 1-5", "2026-10-19T08:00:00Z", False, "DUPLICATE_CET_CEST_UTC_SLOT")
    # CET: Mon 26 Oct UTC 06:20 / 07:00 / 08:00 = 07:20 / 08:00 / 09:00 Rome.
    for cron, time, slot in (
        ("20 6 * * 1-5", "2026-10-26T06:20:00Z", "07:20"),
        ("0 7 * * 1-5", "2026-10-26T07:00:00Z", "08:00"),
        ("0 8 * * 1-5", "2026-10-26T08:00:00Z", "09:00"),
    ):
        check("schedule", cron, time, True, ok, slot)
    check("schedule", "20 5 * * 1-5", "2026-10-26T05:20:00Z", False, "DUPLICATE_CET_CEST_UTC_SLOT")
    check("schedule", "0 6 * * 1-5", "2026-10-26T06:00:00Z", False, "DUPLICATE_CET_CEST_UTC_SLOT")
    check("schedule", "0 7 * * 1-5", "2026-10-26T08:14:00Z", True, ok, "08:00")
    check("schedule", "0 8 * * 1-5", "2026-10-26T09:01:00Z", True, ok, "09:00")
    check("schedule", "0 7 * * 1-5", "2026-10-24T07:00:00Z", False, "NOT_BUSINESS_DAY")
    check("schedule", "20 9 * * 1-5", "2026-10-19T09:20:00Z", False, "UNKNOWN_CRON_FAIL_CLOSED")
    for event in ("workflow_dispatch", "push", "pull_request"):
        check(event, "", "2026-10-19T09:25:00Z", True, "EXPLICIT_EVENT")
    # Evening official-source recovery, launched ONLY by the existing hourly
    # schedule. CET/CEST gate uses wall-clock Europe/Rome, not hardcoded UTC.
    trusted={"upstream_name":"Hourly Certified Alert Readiness V1",
             "upstream_event":"schedule", "upstream_conclusion":"success",
             "upstream_head_branch":"main"}
    def recover(stamp, **changes):
        args={**trusted,**changes}
        return resolve("workflow_run","",iso(stamp),**args)
    assert recover("2026-10-28T18:00:00Z")["should_run"] # 19:00 CET
    assert recover("2026-10-21T17:00:00Z")["should_run"] # 19:00 CEST
    assert recover("2026-10-28T22:59:00Z")["should_run"] # 23:59 CET
    for stamp, reason in [
        ("2026-10-28T17:59:00Z","OUTSIDE_EVENING_SOURCE_PUBLICATION_WINDOW"),
        ("2026-10-28T23:01:00Z","OUTSIDE_EVENING_SOURCE_PUBLICATION_WINDOW"),
        ("2026-10-31T19:01:00Z","EVENING_RECOVERY_WEEKEND"),
    ]:
        got=recover(stamp)
        assert got["should_run"] is False and got["reason"]==reason,got
    for changes in [
        {"upstream_name":"Forward Frozen Core Prospective Daily V1"},
        {"upstream_event":"pull_request"},
        {"upstream_event":"workflow_dispatch"},
        {"upstream_event":"push"},
        {"upstream_conclusion":"failure"},
        {"upstream_conclusion":"cancelled"},
        {"upstream_head_branch":"feature/source-data"},
        {"upstream_head_branch":""},
    ]:
        got=recover("2026-10-28T18:30:00Z",**changes)
        assert got["should_run"] is False and got["reason"]=="UNTRUSTED_OR_NON_SCHEDULED_UPSTREAM",got
    assert resolve("unrecognized_event","",iso("2026-10-28T18:30:00Z"))["reason"]=="UNKNOWN_EVENT_FAIL_CLOSED"
    try:
        resolve("schedule", "0 7 * * 1-5", dt.datetime(2026, 10, 19, 7))
    except ValueError:
        pass
    else:
        raise AssertionError("naive clock accepted")
    print("RATES_SCHEDULE_GATE_V2_CET_CEST_DELAY_FAILCLOSED_PASS")


if __name__ == "__main__":
    run()
