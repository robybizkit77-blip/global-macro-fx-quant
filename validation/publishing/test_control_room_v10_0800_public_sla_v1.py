#!/usr/bin/env python3
"""Fail-closed v10 combined public-file proof, deterministic local fixtures."""
from __future__ import annotations

import datetime as dt
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from check_control_room_v10_0800_public_sla_v1 import (
    V10_FILES, DASHBOARD_FILES, MARKET_FILES, PREVIEW_FILES, run,
)
from check_pages_0800_delivery_sla_v1 import evaluate

ROME = ZoneInfo("Europe/Rome")
SHA = "a" * 64


class ControlRoomV10SlaTests(unittest.TestCase):
    def test_manifest_covers_all_producers_and_preview(self):
        self.assertEqual(len(V10_FILES), len(set(V10_FILES)))
        self.assertTrue(set(DASHBOARD_FILES).issubset(V10_FILES))
        self.assertTrue(set(MARKET_FILES).issubset(V10_FILES))
        self.assertTrue(set(PREVIEW_FILES).issubset(V10_FILES))
        self.assertGreater(len(V10_FILES), len(DASHBOARD_FILES))

    def make_receipts(self):
        source = {
            "schema": "GMFQ_PAGES_MORNING_SOURCE_GATE_V1",
            "morning_gate_required": True,
            "checked_at_rome": "2026-10-27T07:25:00+01:00",
            "status": "PASS_MORNING_SOURCES_VERIFIED",
            "critical_daily_problems": [],
        }
        public = {
            "status": "PASS", "basis": "PUBLIC_HTTP_200_EXACT_SHA256",
            "conclusion": "ALL_PUBLIC_FILES_MATCH",
            "verified_at_utc": "2026-10-27T06:55:00Z",
            "checks": [
                {"path": p, "http_status": 200,
                 "http_200_and_sha256_match": True,
                 "expected_sha256": SHA, "public_sha256": SHA}
                for p in V10_FILES
            ],
        }
        return source, public

    def test_complete_v10_public_receipt_passes(self):
        source, public = self.make_receipts()
        at = dt.datetime(2026, 10, 27, 7, 58, tzinfo=ROME)
        self.assertEqual(evaluate(source, public, at, expected_files=V10_FILES)["status"], "PASS_PUBLIC_HTTP_BY_0800")

    def test_only_dashboard_files_is_not_v10_success(self):
        source, public = self.make_receipts()
        public["checks"] = [r for r in public["checks"] if r["path"] in DASHBOARD_FILES]
        at = dt.datetime(2026, 10, 27, 7, 58, tzinfo=ROME)
        self.assertEqual(evaluate(source, public, at, expected_files=V10_FILES)["status"], "FAIL_PUBLIC_HTTP_UNVERIFIED")

    def test_market_stale_blocks_v10_completeness(self):
        source, public = self.make_receipts()
        row = next(r for r in public["checks"] if r["path"] == MARKET_FILES[0])
        row["public_sha256"] = "b" * 64
        at = dt.datetime(2026, 10, 27, 7, 58, tzinfo=ROME)
        self.assertEqual(evaluate(source, public, at, expected_files=V10_FILES)["status"], "FAIL_PUBLIC_HTTP_UNVERIFIED")

    def test_preview_loader_missing_blocks_v10_completeness(self):
        source, public = self.make_receipts()
        public["checks"] = [r for r in public["checks"] if r["path"] != PREVIEW_FILES[0]]
        at = dt.datetime(2026, 10, 27, 7, 58, tzinfo=ROME)
        self.assertEqual(evaluate(source, public, at, expected_files=V10_FILES)["status"], "FAIL_PUBLIC_HTTP_UNVERIFIED")

    def test_late_observation_does_not_assume_v10_delivery_was_late(self):
        source, public = self.make_receipts()
        public["verified_at_utc"] = "2026-10-27T07:10:00Z"
        at = dt.datetime(2026, 10, 27, 8, 13, tzinfo=ROME)
        self.assertEqual(evaluate(source, public, at, expected_files=V10_FILES)["status"], "VERIFIED_AFTER_0800_DELIVERY_TIME_UNPROVEN")

    def test_off_window_never_makes_network_request(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("No network check outside morning window")
        report = run(dt.datetime(2026, 10, 27, 16, 0, tzinfo=ROME),
                     Path("."), "https://example.invalid/", auditor=forbidden)
        self.assertEqual(report["status"], "NOT_APPLICABLE_NO_MORNING_SOURCE_GATE")


if __name__ == "__main__":
    unittest.main()
