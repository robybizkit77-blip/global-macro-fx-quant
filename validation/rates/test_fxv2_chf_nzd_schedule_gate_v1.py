#!/usr/bin/env python3
"""Prove DST slot, delay tolerance and one daily vendor eligibility."""
from __future__ import annotations
import datetime as dt
import unittest
from fxv2_chf_nzd_schedule_gate_v1 import gate, MORNING_CEST, MORNING_CET, LATER_SOURCE_SLOTS

def utc(y, m, d, hh, mm):
    return dt.datetime(y,m,d,hh,mm,tzinfo=dt.timezone.utc)

class SourceScheduleGate(unittest.TestCase):
    def test_summer_valid_0630_only(self):
        self.assertEqual(gate("schedule",MORNING_CEST,utc(2026,10,19,4,30)),
                         (True,True,"ROME_0630_PREOPEN_SOURCE_REFRESH"))
        self.assertEqual(gate("schedule",MORNING_CET,utc(2026,10,19,5,30)),
                         (False,False,"DUPLICATE_DST_SLOT"))

    def test_winter_valid_0630_only(self):
        self.assertEqual(gate("schedule",MORNING_CET,utc(2026,11,5,5,30)),
                         (True,True,"ROME_0630_PREOPEN_SOURCE_REFRESH"))
        self.assertEqual(gate("schedule",MORNING_CEST,utc(2026,11,5,4,30)),
                         (False,False,"DUPLICATE_DST_SLOT"))

    def test_dst_transition_first_business_days(self):
        self.assertTrue(gate("schedule",MORNING_CEST,utc(2027,3,29,4,31))[0])
        self.assertTrue(gate("schedule",MORNING_CET,utc(2026,10,26,5,31))[0])
        self.assertFalse(gate("schedule",MORNING_CET,utc(2027,3,29,5,31))[0])

    def test_delayed_cron_still_captures_and_only_one_vendor_attempt(self):
        self.assertEqual(gate("schedule",MORNING_CET,utc(2026,11,5,8,47)),
                         (True,True,"ROME_0630_PREOPEN_SOURCE_REFRESH"))
        for cron in LATER_SOURCE_SLOTS:
            accepted, vendor, reason = gate("schedule",cron,utc(2026,11,5,19,0))
            self.assertTrue(accepted)
            self.assertFalse(vendor)
            self.assertEqual(reason,"LATER_OFFICIAL_SOURCE_RETRY")

    def test_weekends_invalid_schedule_and_explicit_dispatch_allowed(self):
        self.assertEqual(gate("schedule",MORNING_CET,utc(2026,11,7,5,30)),
                         (False,False,"NOT_A_ROMAN_WORKDAY"))
        self.assertEqual(gate("workflow_dispatch","",utc(2026,11,7,5,30)),
                         (True,True,"EVENT_OR_MANUAL_SOURCE_REFRESH"))
        self.assertEqual(gate("pull_request","",utc(2026,11,7,5,30)),
                         (True,False,"EVENT_OR_MANUAL_SOURCE_REFRESH"))
        self.assertEqual(gate("push","",utc(2026,11,7,5,30)),
                         (True,False,"EVENT_OR_MANUAL_SOURCE_REFRESH"))
        self.assertEqual(gate("schedule","0 0 * * 1-5",utc(2026,11,5,7,30)),
                         (False,False,"UNKNOWN_SCHEDULE_SLOT"))

    def test_reject_naive_clock_and_early_run(self):
        with self.assertRaisesRegex(ValueError, "aware"):
            gate("schedule",MORNING_CET,dt.datetime(2026,11,5,5,30))
        self.assertEqual(gate("schedule",MORNING_CET,utc(2026,11,5,4,20)),
                         (False,False,"BEFORE_MORNING_LOCAL_SLOT"))

if __name__=="__main__":
    unittest.main()
