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
    print("OIS_G8_DST_DELAYED_SCHEDULE_GATE_V1: PASS")


if __name__ == "__main__":
    main()
