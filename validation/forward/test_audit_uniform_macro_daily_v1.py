import unittest
from datetime import datetime
from unittest.mock import patch
from validation.forward import audit_uniform_macro_daily_v1 as m
class UniformDailyAuditTests(unittest.TestCase):
    def test_pre_cohort_and_missing(self):
        before=datetime.fromisoformat("2026-11-26T22:00:00+01:00")
        self.assertFalse(m.audit(before,{},{},{},[])["blocks_workflow"])
        now=datetime.fromisoformat("2026-11-27T22:00:00+01:00")
        with patch.object(m,"assess",return_value={"checks":[]}):
            self.assertTrue(m.audit(now,{},{},{},[])["blocks_workflow"])
        with patch.object(m,"assess",return_value={"checks":["NO_T0"]}):
            self.assertFalse(m.audit(now,{},{},{},[])["durable_uniform_capture"])
    def test_verified_date_and_integrity(self):
        now=datetime.fromisoformat("2026-11-27T22:00:00+01:00")
        row={"local_date_rome":"2026-11-27","snapshot_sha256":"test"}
        with patch.object(m,"verify",return_value={"2026-11-27"}):
            r=m.audit(now,{},{},{},[row])
            self.assertTrue(r["durable_uniform_capture"])
            self.assertFalse(r["predictive_skill_certified"])
        with patch.object(m,"verify",side_effect=ValueError("invalid")):
            self.assertTrue(m.audit(now,{},{},{},[row])["blocks_workflow"])
