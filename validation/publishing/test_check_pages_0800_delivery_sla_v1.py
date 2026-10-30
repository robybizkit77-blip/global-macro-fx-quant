#!/usr/bin/env python3
"""Deterministic regression cases for public delivery vs GitHub Actions timing."""
from __future__ import annotations

import datetime as dt
import unittest
from zoneinfo import ZoneInfo

from check_pages_0800_delivery_sla_v1 import evaluate, FILES

ROME = ZoneInfo("Europe/Rome")
SHA = "a" * 64


class Pages0800DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 10, 27, 7, 55, tzinfo=ROME)
        self.source = {
            "schema": "GMFQ_PAGES_MORNING_SOURCE_GATE_V1",
            "checked_at_rome": "2026-10-27T07:20:00+01:00",
            "morning_gate_required": True,
            "status": "PASS_MORNING_SOURCES_VERIFIED",
            "critical_daily_problems": [],
        }
        self.public = {
            "status": "PASS",
            "basis": "PUBLIC_HTTP_200_EXACT_SHA256",
            "conclusion": "ALL_PUBLIC_FILES_MATCH",
            "verified_at_utc": "2026-10-27T06:50:00Z",
            "checks": [
                {"path": p, "http_200_and_sha256_match": True,
                 "http_status": 200, "expected_sha256": SHA, "public_sha256": SHA}
                for p in FILES
            ],
        }

    def result(self, now=None):
        return evaluate(self.source, self.public, now or self.now)

    def test_true_public_success_before_deadline(self):
        d = self.result()
        self.assertEqual(d["status"], "PASS_PUBLIC_HTTP_BY_0800")
        self.assertTrue(d["independent_of_parent_orchestrator"])
        self.assertEqual(d["verified_file_count"], len(FILES))
        self.assertTrue(d["on_time_delivery_proven"])
        self.assertFalse(d["verified_after_deadline"])

    def test_http_on_time_can_coexist_with_unresolved_cb_policy(self):
        self.source["issuer_policy_watch"] = {
            "status": "PENDING_SAME_DAY_CB_DECISION", "currencies": ["JPY"]}
        d = self.result()
        self.assertEqual(d["status"], "PASS_PUBLIC_HTTP_BY_0800")
        self.assertTrue(d["on_time_delivery_proven"])
        self.assertEqual(d["cb_policy_pending_currencies"], ["JPY"])
        self.assertFalse(d["cb_policy_no_pending_same_day_decision_proven"])
        self.assertTrue(d["http_delivery_does_not_certify_cb_release"])

    def test_resolved_policy_watch_is_separately_certified(self):
        self.source["issuer_policy_watch"] = {
            "status": "NO_PENDING_SAME_DAY_CB_DECISION", "currencies": []}
        d = self.result()
        self.assertTrue(d["on_time_delivery_proven"])
        self.assertTrue(d["cb_policy_no_pending_same_day_decision_proven"])

    def test_missing_policy_watch_never_falsely_certifies_complete(self):
        d = self.result()
        self.assertEqual(d["cb_policy_watch_status"], "NOT_CERTIFIED")
        self.assertFalse(d["cb_policy_no_pending_same_day_decision_proven"])

    def test_late_success_is_never_on_time(self):
        self.public["verified_at_utc"] = "2026-10-27T07:03:00Z"
        d = self.result(dt.datetime(2026, 10, 27, 8, 15, tzinfo=ROME))
        self.assertEqual(d["status"], "VERIFIED_AFTER_0800_DELIVERY_TIME_UNPROVEN")
        self.assertTrue(d["public_exact_bytes_pass"])
        self.assertTrue(d["verified_after_deadline"])
        self.assertFalse(d["on_time_delivery_proven"])

    def test_after_deadline_observation_cannot_prove_actual_delivery_late(self):
        # The site may have been live at 07:30; an HTTP read at 08:20
        # cannot retroactively establish the actual release time.
        self.public["verified_at_utc"] = "2026-10-27T07:20:00Z"
        d = self.result(dt.datetime(2026, 10, 27, 8, 21, tzinfo=ROME))
        self.assertEqual(d["status"], "VERIFIED_AFTER_0800_DELIVERY_TIME_UNPROVEN")
        self.assertTrue(d["public_exact_bytes_pass"])
        self.assertFalse(d["on_time_delivery_proven"])

    def test_public_missing_is_not_success(self):
        self.assertEqual(evaluate(self.source, None, self.now)["status"], "FAIL_PUBLIC_HTTP_UNVERIFIED")

    def test_missing_file_fails_closed(self):
        self.public["checks"].pop()
        self.assertEqual(self.result()["status"], "FAIL_PUBLIC_HTTP_UNVERIFIED")

    def test_duplicate_path_fails_closed(self):
        self.public["checks"][-1] = self.public["checks"][0].copy()
        self.assertEqual(self.result()["status"], "FAIL_PUBLIC_HTTP_UNVERIFIED")

    def test_corrupt_public_digest_fails_closed(self):
        self.public["checks"][0]["public_sha256"] = "b" * 64
        self.assertEqual(self.result()["status"], "FAIL_PUBLIC_HTTP_UNVERIFIED")

    def test_stale_morning_gate_fails_closed(self):
        self.source["checked_at_rome"] = "2026-10-26T07:20:00+01:00"
        self.assertEqual(self.result()["status"], "FAIL_MORNING_SOURCE_GATE")

    def test_source_warning_fails_closed(self):
        self.source["status"] = "BLOCK_MORNING_INPUTS_INCOMPLETE"
        self.assertEqual(self.result()["status"], "FAIL_MORNING_SOURCE_GATE")

    def test_source_missing_fails_closed(self):
        self.assertEqual(evaluate(None, self.public, self.now)["status"], "NOT_APPLICABLE_NO_MORNING_SOURCE_GATE")

    def test_outside_morning_not_certified(self):
        self.source["morning_gate_required"] = False
        self.assertEqual(self.result()["status"], "NOT_APPLICABLE_NO_MORNING_SOURCE_GATE")

    def test_public_future_timestamp_fails_closed(self):
        self.public["verified_at_utc"] = "2026-10-27T08:30:00Z"
        self.assertEqual(self.result()["status"], "FAIL_PUBLIC_HTTP_UNVERIFIED")

    def test_public_before_morning_source_gate_fails_closed(self):
        self.public["verified_at_utc"] = "2026-10-27T05:50:00Z"
        self.assertEqual(self.result()["status"], "FAIL_PUBLIC_HTTP_UNVERIFIED")

    def test_naive_timestamp_does_not_pass(self):
        self.public["verified_at_utc"] = "2026-10-27T07:45:00"
        self.assertEqual(self.result()["status"], "FAIL_PUBLIC_HTTP_UNVERIFIED")

    def test_0800_exact_is_on_time(self):
        self.public["verified_at_utc"] = "2026-10-27T07:00:00Z"
        d = self.result(dt.datetime(2026, 10, 27, 8, 1, tzinfo=ROME))
        self.assertEqual(d["status"], "PASS_PUBLIC_HTTP_BY_0800")


if __name__ == "__main__":
    unittest.main()
