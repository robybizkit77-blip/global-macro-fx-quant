#!/usr/bin/env python3
"""Offline DST and GitHub queue regression, no rates network or writes."""
import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from validation.rates_daily_operational_schedule_gate_v1 import decide
ROME=ZoneInfo("Europe/Rome")

def check(day,clock,cron):
    when=dt.datetime.fromisoformat(day+"T"+clock).replace(tzinfo=ROME)
    return decide("schedule",cron,when)

class ScheduleTest(unittest.TestCase):
    def test_three_cet_slots(self):
        for time,cron in [("06:10","10 5 * * 1-5"),("06:40","40 5 * * 1-5"),("07:10","10 6 * * 1-5")]:
            with self.subTest(time=time):
                x=check("2026-11-05",time,cron)
                self.assertTrue(x["should_run"])
                self.assertEqual(x["slot_rome"],time)
                self.assertFalse(x["proves_delivery_at_0800"])
    def test_three_cest_slots(self):
        for time,cron in [("06:10","10 4 * * 1-5"),("06:40","40 4 * * 1-5"),("07:10","10 5 * * 1-5")]:
            with self.subTest(time=time):
                x=check("2026-07-02",time,cron)
                self.assertTrue(x["should_run"])
                self.assertEqual(x["slot_rome"],time)
    def test_inactive_duplicate_cron_no_audit(self):
        for day,cron in [("2026-11-05","10 4 * * 1-5"),("2026-11-05","40 4 * * 1-5"),
                         ("2026-07-02","40 5 * * 1-5"),("2026-07-02","10 6 * * 1-5")]:
            with self.subTest(day=day,cron=cron):
                x=check(day,"14:30",cron)
                self.assertFalse(x["should_run"])
                self.assertEqual(x["reason"],"INACTIVE_CET_CEST_DUPLICATE_SLOT")
    def test_late_scheduled_run_must_not_be_skipped(self):
        r=check("2026-11-05","14:28","10 5 * * 1-5")
        self.assertTrue(r["should_run"])
        self.assertEqual(r["execution_delay_minutes"],498)
        self.assertEqual(r["reason"],"VALID_SLOT_QUEUED_LATE")
        r=check("2026-07-02","09:20","40 4 * * 1-5")
        self.assertEqual(r["execution_delay_minutes"],160)
        self.assertTrue(r["should_run"])
    def test_unexpected_cron_and_pr_rejected_manual_allowed(self):
        self.assertFalse(check("2026-11-05","07:10","10 7 * * 1-5")["should_run"])
        now=dt.datetime.now(dt.timezone.utc)
        self.assertFalse(decide("pull_request","",now)["should_run"])
        self.assertFalse(decide("unexpected","",now)["should_run"])
        self.assertTrue(decide("workflow_dispatch","",now)["should_run"])
        self.assertTrue(decide("push","",now)["should_run"])
    def test_naive_clock_rejected(self):
        with self.assertRaises(ValueError):
            decide("schedule","10 5 * * 1-5",dt.datetime(2026,11,5,6,10))

if __name__=="__main__":
    unittest.main()
