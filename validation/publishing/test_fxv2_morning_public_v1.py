#!/usr/bin/env python3
"""Deterministic tests of the FXV2 08:00 public delivery evidence policy."""
import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from check_fxv2_morning_public_v1 import FILES, evaluate

ROME = ZoneInfo("Europe/Rome")
SHA = "a" * 64


def rows():
    return [{"path": name, "http": 200, "status": "MATCH",
             "expected_sha256": SHA, "public_sha256": SHA} for name in FILES]


class MorningProofTest(unittest.TestCase):
    def test_complete_before_deadline(self):
        result = evaluate(dt.datetime(2026, 11, 4, 7, 51, tzinfo=ROME), rows())
        self.assertEqual(result["status"], "PASS_12_PAGES_PUBLIC_BY_0800")
        self.assertTrue(result["on_time_proven"])
        self.assertEqual(result["public_files_verified"], len(FILES))
        self.assertFalse(result["economic_data_freshness_certified"])

    def test_observed_after_deadline_is_not_proof_of_lateness_or_on_time(self):
        result = evaluate(dt.datetime(2026, 11, 4, 12, 35, tzinfo=ROME), rows())
        self.assertEqual(result["status"], "VERIFIED_AFTER_0800_ON_TIME_UNPROVEN")
        self.assertFalse(result["on_time_proven"])

    def test_missing_page_fails(self):
        result = evaluate(dt.datetime(2026, 11, 4, 7, 50, tzinfo=ROME), rows()[:-1])
        self.assertEqual(result["status"], "FAIL_PUBLIC_FILES_NOT_MATCHED")

    def test_duplicate_page_fails(self):
        rs = rows()
        rs[-1] = rs[0].copy()
        self.assertFalse(evaluate(dt.datetime(2026, 11, 4, 7, 50, tzinfo=ROME), rs)["on_time_proven"])

    def test_http_hash_drift_fails(self):
        rs = rows()
        rs[0]["public_sha256"] = "b" * 64
        self.assertEqual(evaluate(dt.datetime(2026, 11, 4, 7, 50, tzinfo=ROME), rs)["status"],
                         "FAIL_PUBLIC_FILES_NOT_MATCHED")

    def test_http_404_fails(self):
        rs = rows()
        rs[2]["http"] = 404
        rs[2]["status"] = "MISMATCH_OR_UNAVAILABLE"
        self.assertFalse(evaluate(dt.datetime(2026, 11, 4, 7, 50, tzinfo=ROME), rs)["on_time_proven"])

    def test_weekend_not_certified(self):
        result = evaluate(dt.datetime(2026, 11, 7, 7, 50, tzinfo=ROME), rows())
        self.assertEqual(result["status"], "NOT_WEEKDAY")

    def test_dst_summer(self):
        result = evaluate(dt.datetime(2026, 7, 1, 7, 55, tzinfo=ROME), rows())
        self.assertTrue(result["on_time_proven"])

    def test_exact_0800(self):
        result = evaluate(dt.datetime(2026, 11, 4, 8, 0, tzinfo=ROME), rows())
        self.assertTrue(result["on_time_proven"])


if __name__ == "__main__":
    unittest.main()
