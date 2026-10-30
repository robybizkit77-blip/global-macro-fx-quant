"""Deterministic fail-closed backup gate tests; no real GitHub dispatch."""
from __future__ import annotations
import copy
import datetime as dt
import unittest

from validation.orchestration.plan_calendar_news_hourly_fallback_v1 import plan

UTC=dt.timezone.utc
def instant(value):
    return dt.datetime.fromisoformat(value.replace("Z","+00:00"))
def source(created, checked=None):
    return {"generated_at_utc":created,"last_checked_at_utc":checked or created}
def cb_meeting():
    return {"JPY":{"next_meeting":"2026-10-30","last_date":"2026-09-18"}}
def parent(completed="2026-10-30T05:34:00Z"):
    return {"name":"Hourly Certified Alert Readiness V1","event":"schedule",
            "conclusion":"success","head_branch":"main","completed_at":completed}
def receipts(checked="2026-10-30T03:01:58Z"):
    return {"CALENDAR":source(checked),"NEWS_PULSE":source(checked)}

class MorningFallbackTests(unittest.TestCase):
    def test_actual_boj_oct30_0635_cet_recovers_early_check(self):
        a=plan(instant("2026-10-30T05:35:00Z"),parent(),receipts(),cb_meeting())
        self.assertTrue(a["should_dispatch"])
        self.assertIn("NEWS_PULSE",a["source_rechecks_needed"])
        self.assertIn("CB_MEETING_DAY_PRIOR_TO_0500_NEWS_CHECK",a["reasons"])
        self.assertFalse(a["issuer_release_inferred"])
        self.assertFalse(a["new_cron_added"])

    def test_already_rechecked_after_0500_skips_duplicate(self):
        r=receipts("2026-10-30T05:31:00Z")
        a=plan(instant("2026-10-30T05:35:00Z"),parent(),r,cb_meeting())
        self.assertFalse(a["should_dispatch"])

    def test_missing_source_triggers_even_without_meeting(self):
        r=receipts()
        r.pop("NEWS_PULSE")
        a=plan(instant("2026-10-30T05:35:00Z"),parent(),r,{})
        self.assertTrue(a["should_dispatch"])

    def test_no_meeting_already_checked_today_skips(self):
        self.assertFalse(plan(instant("2026-10-30T05:35:00Z"),
                              parent(),receipts(),{})["should_dispatch"])

    def test_at_or_after_0730_rechecks_early_meeting_source(self):
        # Existing 07:30 cutoff remains the canonical late recheck rule.
        a=plan(instant("2026-10-30T06:42:00Z"),
               parent("2026-10-30T06:40:00Z"),
               receipts("2026-10-30T05:45:00Z"),cb_meeting())
        self.assertTrue(a["should_dispatch"])
        self.assertIn("NEWS_PULSE",a["source_rechecks_needed"])

    def test_no_replay_or_privilege_escalation_from_parent(self):
        now=instant("2026-10-30T05:35:00Z")
        for key,val in (("event","pull_request"),("head_branch","feature"),
                        ("conclusion","failure"),("name","Malicious workflow")):
            with self.subTest(key=key):
                p=parent();p[key]=val
                self.assertFalse(plan(now,p,receipts(),cb_meeting())["should_dispatch"])
        self.assertFalse(plan(now,parent("2026-10-30T03:00:00Z"),
                              receipts(),cb_meeting())["should_dispatch"])
        self.assertFalse(plan(now,parent("2026-10-30T06:00:00Z"),
                              receipts(),cb_meeting())["should_dispatch"])

    def test_no_weekend_or_after_deadline(self):
        self.assertFalse(plan(instant("2026-10-31T05:35:00Z"),
                              parent("2026-10-31T05:34:00Z"),
                              receipts(),cb_meeting())["should_dispatch"])
        self.assertFalse(plan(instant("2026-10-30T07:00:00Z"),
                              parent("2026-10-30T06:59:00Z"),
                              receipts(),cb_meeting())["should_dispatch"])

    def test_bad_clock_fails_closed(self):
        with self.assertRaises(ValueError):
            plan(dt.datetime(2026,10,30,5,35),parent(),receipts(),cb_meeting())

if __name__=="__main__":
    unittest.main()
