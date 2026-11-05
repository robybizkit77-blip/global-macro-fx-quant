#!/usr/bin/env python3
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import unittest

from validation.quant.fxv2_6m_schedule_gate_v1 import (
    admission, SUMMER, WINTER, PARENT,
)

ROME=ZoneInfo("Europe/Rome")
def now(stamp):
    return datetime.fromisoformat(stamp).astimezone(timezone.utc)

class RomeAdmissionTests(unittest.TestCase):
    def test_dst_pair_never_admits_both_slots(self):
        for timestamp,good,bad in [
            ("2026-11-06T20:45:00+01:00",WINTER,SUMMER),
            ("2027-06-02T20:45:00+02:00",SUMMER,WINTER),
            ("2027-01-04T20:45:00+01:00",WINTER,SUMMER),
        ]:
            yes,msg=admission("schedule",good,now(timestamp))
            self.assertTrue(yes,msg)
            self.assertFalse(admission("schedule",bad,now(timestamp))[0])

    def test_pre_registration_and_weekends_rejected(self):
        self.assertFalse(admission("schedule",WINTER,now("2026-11-05T20:45:00+01:00"))[0])
        self.assertFalse(admission("schedule",WINTER,now("2026-11-07T20:45:00+01:00"))[0])
        self.assertFalse(admission("schedule",WINTER,now("2026-11-06T18:59:00+01:00"))[0])
        self.assertFalse(admission("push","",now("2026-11-06T21:00:00+01:00"))[0])
        self.assertFalse(admission("pull_request","",now("2026-11-06T21:00:00+01:00"))[0])

    def test_recovery_only_successful_trusted_same_day_parent(self):
        args={
            "upstream_name":PARENT,"upstream_branch":"main",
            "upstream_conclusion":"success","upstream_event":"schedule",
            "upstream_started_at":"2026-11-06T18:35:00Z",
        }
        today=now("2026-11-06T21:00:00+01:00")
        self.assertTrue(admission("workflow_run","",today,**args)[0])
        for key,value in [
            ("upstream_name","Untrusted Job"),
            ("upstream_branch","dev"),
            ("upstream_conclusion","failure"),
            ("upstream_event","pull_request"),
            ("upstream_started_at","2026-11-05T20:35:00Z"),
            ("upstream_started_at","2026-11-07T00:00:00Z"),
            ("upstream_started_at","not a date"),
        ]:
            bad={**args,key:value}
            self.assertFalse(admission("workflow_run","",today,**bad)[0],(key,value))

    def test_dispatch_is_live_and_not_historical(self):
        self.assertTrue(admission("workflow_dispatch","",now("2026-11-06T21:00:00+01:00"))[0])
        self.assertFalse(admission("workflow_dispatch","",now("2026-11-06T12:00:00+01:00"))[0])

if __name__=="__main__":unittest.main()
