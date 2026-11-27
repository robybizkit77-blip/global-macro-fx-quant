#!/usr/bin/env python3
"""Rates cron regression: Rome slots across CET/CEST, delay and quarantine."""
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
    assert len(SLOTS) == 7
    assert MAX_QUEUE_DELAY_MINUTES == 240
    ok = "VALID_RATES_SLOT_DELAY_TOLERANT"
    # CEST: Mon 19 Oct UTC 05:20 / 06:00 / 07:00 = 07:20 / 08:00 / 09:00 Rome.
    for cron, time, slot in (
        ("20 5 * * 1-5", "2026-10-19T05:20:00Z", "07:20"),
        ("0 6 * * 1-5", "2026-10-19T06:00:00Z", "08:00"),
        ("0 7 * * 1-5", "2026-10-19T07:00:00Z", "09:00"),
    ):
        check("schedule", cron, time, True, ok, slot)
    # Native Rome afternoon trigger is valid in both seasons.
    check("schedule", "17 18 * * 1-5", "2026-10-19T16:17:00Z", True, ok, "18:17")
    check("schedule", "17 18 * * 1-5", "2026-10-26T17:35:00Z", True, ok, "18:17")
    check("schedule", "17 18 * * 1-5", "2026-10-26T17:16:00Z", False, "BEFORE_SCHEDULED_SLOT")
    # The US-close slot follows the Treasury fixing both in the ordinary
    # winter offset and during an EU/US daylight-saving difference.
    check("schedule", "17 22 * * 1-5", "2026-11-17T21:17:00Z", True, ok, "22:17")
    check("schedule", "17 22 * * 1-5", "2026-10-26T21:17:00Z", True, ok, "22:17")
    check("schedule", "17 22 * * 1-5", "2026-10-19T20:17:00Z", True, ok, "22:17")
    check("schedule", "17 22 * * 1-5", "2026-11-17T21:16:59Z", False, "BEFORE_SCHEDULED_SLOT")
    # Queue starts more than 20min after scheduled: still runs.
    check("schedule", "20 5 * * 1-5", "2026-10-19T06:25:00Z", True, ok, "07:20")
    check("schedule", "0 6 * * 1-5", "2026-10-19T07:05:00Z", True, ok, "08:00")
    check("schedule", "0 7 * * 1-5", "2026-10-19T08:05:00Z", True, ok, "09:00")
    # Morning jobs have four hours of tolerance before the evening recovery window.
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
    # Reproduce the recorded 17 November 09:00 job at 18:29 Rome.
    recovery = "LATE_CRON_EVENING_RATES_RECOVERY"
    actual = check("schedule", "0 8 * * 1-5", "2026-11-17T17:29:18Z", True, recovery, "09:00")
    assert actual["queue_delay_minutes"] == 569
    check("schedule", "0 8 * * 1-5", "2026-11-17T17:16:59Z", False, "STALE_DELAYED_RUN")
    check("schedule", "0 7 * * 1-5", "2026-10-19T16:17:00Z", True, recovery, "09:00")
    check("schedule", "0 8 * * 1-5", "2026-10-19T16:29:00Z", False, "DUPLICATE_CET_CEST_UTC_SLOT")
    check("schedule", "17 18 * * 1-5", "2026-11-17T22:00:00Z", True, recovery, "18:17")
    # Replay both real evening cron events that GitHub delivered after midnight.
    overnight = "OVERNIGHT_EVENING_RATES_RECOVERY"
    for cron, observed, slot, delay in (
        ("17 18 * * 1-5", "2026-11-17T23:51:09Z", "18:17", 394),
        ("17 22 * * 1-5", "2026-11-18T02:55:35Z", "22:17", 338),
    ):
        actual = check("schedule", cron, observed, True, overnight, slot)
        assert actual["scheduled_at_rome"] == f"2026-11-17T{slot}:00+01:00", actual
        assert actual["queue_delay_minutes"] == delay, actual
    check("schedule", "17 22 * * 1-5", "2026-10-20T01:55:00Z", True, overnight)
    check("schedule", "17 22 * * 1-5", "2026-11-21T00:15:00Z", True, overnight)
    check("schedule", "17 22 * * 1-5", "2026-11-22T01:15:00Z", False, "NOT_BUSINESS_DAY")
    check("schedule", "17 22 * * 1-5", "2026-11-23T01:15:00Z", False, "NOT_BUSINESS_DAY")
    check("schedule", "17 22 * * 1-5", "2026-11-18T03:59:59Z", True, overnight)
    check("schedule", "17 22 * * 1-5", "2026-11-18T04:00:00Z", False, "BEFORE_SCHEDULED_SLOT")
    check("schedule", "0 8 * * 1-5", "2026-11-18T02:55:35Z", False, "BEFORE_SCHEDULED_SLOT")
    check("schedule", "0 8 * * 1-5", "2026-11-21T17:29:00Z", False, "NOT_BUSINESS_DAY")
    check("schedule", "0 7 * * 1-5", "2026-10-24T07:00:00Z", False, "NOT_BUSINESS_DAY")
    check("schedule", "20 9 * * 1-5", "2026-10-19T09:20:00Z", False, "UNKNOWN_CRON_FAIL_CLOSED")
    for event in ("workflow_dispatch", "push"):
        check(event, "", "2026-10-19T09:25:00Z", True, "EXPLICIT_EVENT")
    check("pull_request", "", "2026-10-19T09:25:00Z",
          False, "PULL_REQUEST_CONTRACT_ONLY")
    # Evening official-source recovery, launched ONLY by the existing hourly
    # schedule. CET/CEST gate uses wall-clock Europe/Rome, not hardcoded UTC.
    trusted={"upstream_name":"Hourly Certified Alert Readiness V1",
             "upstream_event":"schedule", "upstream_conclusion":"success",
             "upstream_head_branch":"main"}
    def recover(stamp, **changes):
        args={**trusted,**changes}
        return resolve("workflow_run","",iso(stamp),**args)
    for stamp in ("2026-11-27T08:09:26Z","2026-11-27T06:20:00Z","2026-10-21T05:20:00Z"):
        got=recover(stamp)
        assert got["should_run"] and got["reason"]=="TRUSTED_SCHEDULED_HOURLY_MORNING_RATES_RECOVERY",got
    for stamp in ("2026-11-27T06:19:59Z","2026-11-27T09:00:00Z","2026-11-28T08:09:26Z"):
        assert not recover(stamp)["should_run"]
    for overrides in ({"upstream_event":"push"},{"upstream_conclusion":"failure"},{"upstream_head_branch":"feature"}):
        assert not recover("2026-11-27T08:09:26Z",**overrides)["should_run"]
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
    # The independent FREE hourly desk is a second, separately scheduled
    # evening trigger. Do not confuse its successful 21:37 Rome edition with
    # a Treasury-close Rates read; only 22:00+ Rome is admissible.
    free_hourly = {**trusted, "upstream_name": "FX Quant Next Independent FREE Hourly Desk"}
    def free_recovery(stamp, **changes):
        return resolve("workflow_run", "", iso(stamp), **{**free_hourly, **changes})
    for stamp in ("2026-11-18T21:00:00Z", "2026-11-18T21:37:45Z",
                  "2026-10-21T20:30:00Z"):
        got = free_recovery(stamp)
        assert got["should_run"] and got["reason"] == "TRUSTED_SCHEDULED_HOURLY_EVENING_RATES_RECOVERY", got
    for stamp, reason in (
        ("2026-11-18T20:37:45Z", "FREE_HOURLY_BACKUP_BEFORE_TREASURY_WINDOW"),
        ("2026-11-18T18:00:00Z", "FREE_HOURLY_BACKUP_BEFORE_TREASURY_WINDOW"),
        ("2026-11-18T23:01:00Z", "OUTSIDE_EVENING_SOURCE_PUBLICATION_WINDOW"),
        ("2026-11-21T21:30:00Z", "EVENING_RECOVERY_WEEKEND"),
    ):
        got = free_recovery(stamp)
        assert not got["should_run"] and got["reason"] == reason, got
    for changes in (
        {"upstream_event": "workflow_dispatch"}, {"upstream_event": "push"},
        {"upstream_event": "pull_request"}, {"upstream_conclusion": "failure"},
        {"upstream_head_branch": "staging"},
    ):
        got = free_recovery("2026-11-18T21:37:45Z", **changes)
        assert not got["should_run"] and got["reason"] == "UNTRUSTED_OR_NON_SCHEDULED_UPSTREAM", got
    # Morning independent path follows Source Watch -> News -> Macro.
    macro={"upstream_name":"Macro Persistent Daily V1",
           "upstream_event":"workflow_run", "upstream_conclusion":"success",
           "upstream_head_branch":"main"}
    for stamp in ("2026-11-02T04:00:00Z","2026-11-02T06:45:00Z",
                  "2026-11-02T08:59:00Z"):
        r=resolve("workflow_run","",iso(stamp),**macro)
        assert r["should_run"] and r["reason"]=="TRUSTED_SERIAL_MACRO_MORNING_RATES_RECOVERY",r
    for stamp,reason in [
        ("2026-11-02T03:59:00Z","OUTSIDE_MORNING_MACRO_RECOVERY_WINDOW"),
        ("2026-11-02T09:00:00Z","OUTSIDE_MORNING_MACRO_RECOVERY_WINDOW"),
        ("2026-11-01T07:00:00Z","MORNING_RECOVERY_WEEKEND"),
    ]:
        r=resolve("workflow_run","",iso(stamp),**macro)
        assert not r["should_run"] and r["reason"]==reason,r
    # Scheduled main-branch Macro completion is independently trusted:
    # this fills morning Rates gaps when GitHub misses one of its own crons.
    scheduled={**macro,"upstream_event":"schedule"}
    for stamp in ("2026-11-02T04:00:00Z","2026-11-02T06:45:00Z",
                  "2026-11-02T08:59:00Z"):
        r=resolve("workflow_run","",iso(stamp),**scheduled)
        assert r["should_run"] and r["reason"]=="TRUSTED_SERIAL_MACRO_MORNING_RATES_RECOVERY",r
    for stamp, reason in [
        ("2026-11-02T03:59:00Z","OUTSIDE_MORNING_MACRO_RECOVERY_WINDOW"),
        ("2026-11-02T09:00:00Z","OUTSIDE_MORNING_MACRO_RECOVERY_WINDOW"),
        ("2026-11-01T07:00:00Z","MORNING_RECOVERY_WEEKEND"),
    ]:
        r=resolve("workflow_run","",iso(stamp),**scheduled)
        assert r["should_run"] is False and r["reason"]==reason,r
    for change in (
        {"upstream_name":"Calendar News Operational Refresh V1"},
        {"upstream_event":"push"},
        {"upstream_event":"workflow_dispatch"},{"upstream_event":"pull_request"},
        {"upstream_conclusion":"failure"},{"upstream_head_branch":"feature/test"},
    ):
        r=resolve("workflow_run","",iso("2026-11-02T06:30:00Z"),
                  **{**macro,**change})
        assert not r["should_run"] and r["reason"]=="UNTRUSTED_OR_NON_SCHEDULED_UPSTREAM",r
    r=resolve("workflow_run","",iso("2026-11-02T19:30:00Z"),**macro)
    assert not r["should_run"] and r["reason"]=="OUTSIDE_MORNING_MACRO_RECOVERY_WINDOW",r
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
