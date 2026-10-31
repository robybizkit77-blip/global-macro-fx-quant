#!/usr/bin/env python3
"""Fail-closed v10 combined public-file proof, deterministic local fixtures."""
from __future__ import annotations

import datetime as dt
import unittest
from unittest.mock import patch
from pathlib import Path
from zoneinfo import ZoneInfo

from check_control_room_v10_0800_public_sla_v1 import (
    V10_FILES, V10_MAIN_FILES, PREVIEW_PART_FILES, DASHBOARD_FILES, MARKET_FILES, PREVIEW_FILES, run,
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
        self.assertTrue(set(PREVIEW_PART_FILES).issubset(V10_FILES))
        self.assertEqual(len(PREVIEW_PART_FILES), 32)
        self.assertEqual(len(V10_MAIN_FILES) + 32, len(V10_FILES))
        self.assertTrue(all(path.startswith("site/control-room-preview/parts/") for path in PREVIEW_PART_FILES))
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

    def test_missing_one_of_32_design_parts_disqualifies_0800(self):
        source, public = self.make_receipts()
        public["checks"] = [r for r in public["checks"]
                            if r["path"] != PREVIEW_PART_FILES[17]]
        at = dt.datetime(2026, 10, 27, 7, 58, tzinfo=ROME)
        self.assertEqual(evaluate(source, public, at, expected_files=V10_FILES)["status"],
                         "FAIL_PUBLIC_HTTP_UNVERIFIED")

    def test_live_combined_32_part_audit_blocks_false_green_receipt(self):
        source, ready = self.make_receipts()
        now = dt.datetime(2026, 10, 27, 7, 58, tzinfo=ROME)

        def primary(root, base, names, **kwargs):
            assert tuple(names) == V10_MAIN_FILES
            return {**ready, "checks": [x for x in ready["checks"]
                                       if x["path"] in V10_MAIN_FILES]}

        def parts_good(root, base):
            return {"status": "PASS", "verified_count": 32,
                    "verified_at_utc": "2026-10-27T06:57:00Z",
                    "checks": [x for x in ready["checks"]
                               if x["path"] in PREVIEW_PART_FILES]}

        with patch("check_control_room_v10_0800_public_sla_v1.source_evaluate",
                   return_value=source):
            ok=run(now, Path("."), "https://example.invalid/",
                   auditor=primary, part_auditor=parts_good, clock=lambda: now)
            self.assertEqual(ok["status"], "PASS_PUBLIC_HTTP_BY_0800")
            self.assertEqual(ok["verified_file_count"], len(V10_FILES))
            self.assertTrue(ok["preview_parts_delivery_verified"])
            self.assertEqual(ok["preview_parts_verified"], 32)
            # No viewer-visible launch if just one of 32 original parts is stale.
            def parts_bad(root, base):
                bad = parts_good(root, base)
                bad["status"] = "FAIL"
                bad["verified_count"] = 31
                bad["checks"] = bad["checks"][:-1]
                return bad
            blocked=run(now, Path("."), "https://example.invalid/",
                        auditor=primary, part_auditor=parts_bad, clock=lambda: now)
            self.assertEqual(blocked["status"], "FAIL_PUBLIC_HTTP_UNVERIFIED")
            self.assertFalse(blocked["on_time_delivery_proven"])
            self.assertFalse(blocked["preview_parts_delivery_verified"])

    def test_parts_http_observed_after_0800_cannot_prove_on_time(self):
        source, ready = self.make_receipts()
        now = dt.datetime(2026, 10, 27, 8, 6, tzinfo=ROME)
        def primary(root, base, names, **kwargs):
            return {**ready, "checks": [x for x in ready["checks"]
                                       if x["path"] in V10_MAIN_FILES]}
        def parts_late(root, base):
            return {"status": "PASS", "verified_count": 32,
                    "verified_at_utc": "2026-10-27T07:02:00Z",
                    "checks": [x for x in ready["checks"]
                               if x["path"] in PREVIEW_PART_FILES]}
        with patch("check_control_room_v10_0800_public_sla_v1.source_evaluate",
                   return_value=source):
            result = run(now, Path("."), "https://example.invalid/",
                         auditor=primary, part_auditor=parts_late, clock=lambda: now)
        self.assertEqual(result["status"], "VERIFIED_AFTER_0800_DELIVERY_TIME_UNPROVEN")
        self.assertFalse(result["on_time_delivery_proven"])
        self.assertTrue(result["preview_parts_delivery_verified"])

    def test_off_window_never_makes_network_request(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("No network check outside morning window")
        report = run(dt.datetime(2026, 10, 27, 16, 0, tzinfo=ROME),
                     Path("."), "https://example.invalid/", auditor=forbidden)
        self.assertEqual(report["status"], "NOT_APPLICABLE_NO_MORNING_SOURCE_GATE")


if __name__ == "__main__":
    unittest.main()
