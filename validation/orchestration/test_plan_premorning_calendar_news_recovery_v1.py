#!/usr/bin/env python3
"""2026 Europe/Rome DST-safe 07:45 Calendar/News selective fallback."""
import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from validation.orchestration.plan_premorning_calendar_news_recovery_v1 import assess
ROME=ZoneInfo("Europe/Rome")

def feeds(checked):
    return {name:{"generated_at_utc":"2026-10-25T15:35:18Z",
                  "last_checked_at_utc":checked}
            for name in ("CALENDAR","NEWS_PULSE")}

class PlannerTests(unittest.TestCase):
    def at(self,date):
        return dt.datetime.fromisoformat(date)
    def test_same_rome_day_no_duplicate_collector(self):
        now=self.at("2026-10-26T07:45:00+01:00")
        d=assess(now,feeds("2026-10-26T05:56:07Z"))
        self.assertEqual(d["status"],"SKIP_ALREADY_RECHECKED_TODAY")
        self.assertEqual(d["source_rechecks_needed"],[])
    def test_one_stale_source_recovers_both_with_one_child(self):
        now=self.at("2026-10-26T07:45:00+01:00")
        f=feeds("2026-10-26T05:56:07Z")
        f["NEWS_PULSE"]["last_checked_at_utc"]="2026-10-23T05:00:00Z"
        self.assertEqual(assess(now,f)["source_rechecks_needed"],["NEWS_PULSE"])
    def test_missing_clock_not_a_green_content_build(self):
        now=self.at("2026-10-26T07:45:00+01:00")
        f=feeds("2026-10-26T05:56:07Z")
        del f["CALENDAR"]["last_checked_at_utc"]
        self.assertEqual(assess(now,f)["status"],"RETRY_REQUIRED")
    def test_no_future_recheck_or_old_generate_after_checked(self):
        now=self.at("2026-10-26T07:45:00+01:00")
        self.assertEqual(assess(now,feeds("2026-10-26T09:56:07Z"))["status"],"RETRY_REQUIRED")
        f=feeds("2026-10-26T05:56:07Z")
        f["NEWS_PULSE"]["generated_at_utc"]="2026-10-26T05:56:08Z"
        self.assertEqual(assess(now,f)["status"],"RETRY_REQUIRED")
    def test_oct30_boj_decision_day_after_early_check_rechecks_news(self):
        # Official BoJ publication time is unspecified: 05:17 check is too
        # early to prove the decision's 07:45 availability.
        now=self.at("2026-10-30T07:45:00+01:00")
        f=feeds("2026-10-30T04:17:00Z")
        cb={"JPY":{"last_date":"2026-09-18","next_meeting":"2026-10-30"}}
        result=assess(now,f,cb)
        self.assertEqual(result["status"],"RETRY_REQUIRED")
        self.assertEqual(result["source_rechecks_needed"],["NEWS_PULSE"])
        self.assertEqual(result["evidence"]["NEWS_PULSE"]["state"],
                         "CB_MEETING_DAY_EARLY_NEWS_CHECK")
        self.assertEqual(result["issuer_meetings_due_for_source_watch"],["JPY"])
        self.assertIs(result["meeting_schedule_never_certifies_a_decision"],True)

    def test_meeting_day_late_check_does_not_duplicate(self):
        now=self.at("2026-10-30T07:45:00+01:00")
        cb={"JPY":{"last_date":"2026-09-18","next_meeting":"2026-10-30"}}
        late=feeds("2026-10-30T06:35:00Z")  # 07:35 Rome
        self.assertEqual(assess(now,late,cb)["status"],
                         "SKIP_ALREADY_RECHECKED_TODAY")

    def test_no_meeting_and_already_certified_decision_skip(self):
        now=self.at("2026-10-30T07:45:00+01:00")
        early=feeds("2026-10-30T04:17:00Z")
        self.assertEqual(assess(now,early,{})["status"],"SKIP_ALREADY_RECHECKED_TODAY")
        cb={"JPY":{"last_date":"2026-10-30","next_meeting":"2026-12-18"}}
        self.assertEqual(assess(now,early,cb)["status"],"SKIP_ALREADY_RECHECKED_TODAY")
        bad={"JPY":{"last_date":"bad","next_meeting":"2026-10-30"}}
        self.assertEqual(assess(now,early,bad)["status"],"SKIP_ALREADY_RECHECKED_TODAY")

    def test_cb_meeting_recheck_preserves_clock_and_invalid_source_gate(self):
        now=self.at("2026-10-30T07:45:00+01:00")
        cb={"JPY":{"last_date":"2026-09-18","next_meeting":"2026-10-30"}}
        f=feeds("2026-10-30T04:17:00Z")
        f["NEWS_PULSE"]["last_checked_at_utc"]="2026-10-30T09:45:00Z"
        self.assertEqual(assess(now,f,cb)["evidence"]["NEWS_PULSE"]["state"],
                         "INVALID_OR_MISSING_SOURCE_CLOCK")
        self.assertEqual(assess(now,f,cb)["source_rechecks_needed"],["NEWS_PULSE"])

    def test_dst_oct25_cross_midnight(self):
        # 2026-10-25 switched +02 to +01. No UTC date heuristic allowed.
        now=self.at("2026-10-26T07:45:00+01:00")
        self.assertEqual(assess(now,feeds("2026-10-25T23:20:00Z"))["status"],"SKIP_ALREADY_RECHECKED_TODAY")
        self.assertEqual(assess(now,feeds("2026-10-25T22:20:00Z"))["status"],"RETRY_REQUIRED")
    def test_weekend_or_invalid_do_not_fake(self):
        now=self.at("2026-10-26T07:45:00+01:00")
        self.assertEqual(assess(now,{"CALENDAR":{},"NEWS_PULSE":None})["status"],"RETRY_REQUIRED")
        f=feeds("2026-10-26T05:56:07")
        self.assertEqual(assess(now,f)["status"],"RETRY_REQUIRED")
        with self.assertRaisesRegex(ValueError,"aware"):
            assess(dt.datetime(2026,10,26,7,45),f)

if __name__=="__main__":
    unittest.main()
