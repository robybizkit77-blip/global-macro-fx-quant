#!/usr/bin/env python3
"""Read-only coverage audit contract: success is not the same as fresh data."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from validation.orchestration.audit_g8_source_coverage_v1 import (
    FX, ROOT, age_days, age_months, compare, coverage, latest_periods,
)

class G8CoverageReceiptTests(unittest.TestCase):
    def test_real_canonical_sources_are_readable(self):
        report = coverage(asof="2026-11-12")
        self.assertEqual(report["schema"], "GMFQ_G8_SOURCE_COVERAGE_RECEIPT_V1")
        self.assertEqual(set(report["rows"]), set(FX))
        self.assertEqual(set(report["fingerprints"]["rates"]), set(FX))
        self.assertTrue(report["policy"].startswith("Read-only"))
        self.assertEqual(report["rows"]["CHF"]["rates_2y"]["status"], "STALE_OR_UNALIGNED")
        self.assertEqual(report["rows"]["NZD"]["rates_2y"]["status"], "STALE_OR_UNALIGNED")
        self.assertIn(report["rows"]["USD"]["pricing_6m"]["status"], {"INDICATIVE_PROXY", "WITHHELD"})
        self.assertEqual(report["rows"]["EUR"]["pricing_6m"]["status"], "INDICATIVE_PROXY")
        self.assertEqual(report["rows"]["CHF"]["pricing_6m"]["status"], "INDICATIVE_PROXY")
        self.assertEqual(report["rows"]["NZD"]["pricing_6m"]["status"], "WITHHELD")
        self.assertIsNone(report["rows"]["USD"]["pricing_6m"]["weekly_change_bp"])
        self.assertGreater(report["rows"]["USD"]["macro_series"]["observed_with_value"], 10)
        self.assertGreater(report["rows"]["USD"]["macro_series"]["within_5_months"], 10)
        self.assertGreater(report["rows"]["EUR"]["macro_series"]["within_5_months"], 5)
        self.assertGreater(report["rows"]["CAD"]["macro_series"]["within_5_months"], 5)

    def test_cli_readonly_exact_main_root_matches_default_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/"receipt.json"
            subprocess.run([sys.executable,
                str(ROOT/"validation/orchestration/audit_g8_source_coverage_v1.py"),
                "--root",str(ROOT),"--as-of","2026-11-12",
                "--output",str(output)],check=True,capture_output=True,text=True)
            receipt=json.loads(output.read_text(encoding="utf-8"))
        standard=coverage(root=ROOT,asof="2026-11-12")
        self.assertEqual(receipt["schema"],standard["schema"])
        self.assertEqual(receipt["fingerprints"],standard["fingerprints"])
        self.assertEqual(receipt["rows"],standard["rows"])
        self.assertNotIn("since_before_phase",receipt)

    def test_content_change_must_be_detected_separately_from_success(self):
        old = {"fingerprints": {"rates": {"USD": "digest-a"}, "macro_series": {"USD": "digest-m"}}}
        same = {"fingerprints": {"rates": {"USD": "digest-a"}, "macro_series": {"USD": "digest-m"}}}
        changed = {"fingerprints": {"rates": {"USD": "digest-b"}, "macro_series": {"USD": "digest-m"}}}
        self.assertEqual(compare(old, same)["rates"]["USD"], "UNCHANGED")
        self.assertEqual(compare(old, changed)["rates"]["USD"], "CHANGED")
        self.assertEqual(compare(old, changed)["macro_series"]["USD"], "UNCHANGED")

    def test_future_and_bad_observations_must_not_be_promoted(self):
        test = [
            {"id": "test", "category": "Crescita",
             "dates": ["2026-09", "2027-01", "2026-10", "2026-11"],
             "values": [1.0, 900.0, None, 2.0]},
        ]
        row = latest_periods(test, "2026-11-12")
        self.assertEqual(row[0]["period"], "2026-11")
        self.assertEqual(row[0]["value"], 2.0)
        self.assertIsNone(age_days("2026-11-13", "not-a-date"))
        self.assertLess(age_days("2026-11-13", "2026-11-12"), 0)
        self.assertEqual(age_months("2026-11-01", "2026-11-12"), 0)
        self.assertEqual(age_months("2026-10", "2026-11-12"), 1)
        self.assertEqual(age_months("2026-09-01", "2026-11-12"), 2)
        self.assertEqual(age_months("2025-11-01", "2026-11-12"), 12)
        self.assertEqual(age_months("2026-12", "2026-11-12"), -1)

if __name__ == "__main__":
    unittest.main()
