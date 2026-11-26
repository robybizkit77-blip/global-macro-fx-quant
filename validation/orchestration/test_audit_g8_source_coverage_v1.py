#!/usr/bin/env python3
"""Read-only coverage audit contract: success is not the same as fresh data."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from validation.orchestration.audit_g8_source_coverage_v1 import (
    FILES, FX, ROOT, age_days, age_months, compare, coverage, latest_periods, observation_date,
)

class G8CoverageReceiptTests(unittest.TestCase):
    def test_real_canonical_sources_are_readable(self):
        report = coverage()
        self.assertEqual(report["schema"], "GMFQ_G8_SOURCE_COVERAGE_RECEIPT_V1")
        self.assertEqual(set(report["rows"]), set(FX))
        self.assertEqual(set(report["fingerprints"]["rates"]), set(FX))
        self.assertTrue(report["policy"].startswith("Read-only"))
        for currency, row in report["rows"].items():
            with self.subTest(currency=currency):
                rates, pricing, macro = (row[k] for k in ("rates_2y", "pricing_6m", "macro_series"))
                self.assertIn(rates["status"], {"RECENT_OFFICIAL", "STALE_OR_UNALIGNED"})
                self.assertIn(pricing["status"], {"OFFICIAL_1W", "INDICATIVE_PROXY", "WITHHELD"})
                if rates["status"] == "STALE_OR_UNALIGNED":
                    self.assertIsNone(rates["weekly_change_bp"])
                if pricing["status"] != "OFFICIAL_1W":
                    self.assertIsNone(pricing["weekly_change_bp"])
                if pricing["status"] == "WITHHELD":
                    self.assertIsNone(pricing["observation_date"])
                else:
                    self.assertIn(age_days(pricing["observation_date"], report["as_of"]), range(8))
                self.assertLessEqual(macro["within_5_months"], macro["observed_with_value"])
                self.assertLessEqual(macro["observed_with_value"], macro["catalogue"])

    def test_proxy_classification_tracks_observation_date_and_provenance(self):
        def indicative(asof, *, timestamp_verified=True):
            return {
                "as_of": asof, "status": "ESTIMATED_ACTIVE",
                "input_mode": "LIVE_SECONDARY_OVERLAY", "source_quality": "SECONDARY_PUBLIC_LIVE_PROXY",
                "policy_repricing_inference_allowed": False, "governance": {"informational_only": True},
                "horizons": {"6m": {"quote_as_of": asof, "quote_timestamp_verified": timestamp_verified,
                                    "raw_level_gap_not_policy_repricing": True, "contract": "EURH2027",
                                    "rate": 2.4, "change_1w_bp": 15}},
            }

        inputs = {key: {} for key in FILES}
        inputs["cb_estimated"] = {"currencies": {
            "EUR": indicative("2026-11-13"), "CHF": indicative("2026-11-08"),
            "USD": indicative("2026-11-18"), "NZD": indicative("2026-11-17", timestamp_verified=False),
        }}
        inputs["ois"] = {"currencies": {"GBP": {
            "as_of": "2026-11-16", "quality": "FONTE UFFICIALE", "kind": "OIS",
            "horizons": {"6m": {"as_of": "2026-11-16", "rate": 3.2, "change_1w_bp": 5}},
        }}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for key, file in FILES.items():
                path = root / file
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(inputs[key]), encoding="utf-8")
            historical = coverage(root=root, asof="2026-11-12")
            current = coverage(root=root, asof="2026-11-17")

        self.assertEqual(historical["rows"]["EUR"]["pricing_6m"]["status"], "WITHHELD")
        pricing = {ccy: row["pricing_6m"] for ccy, row in current["rows"].items()}
        self.assertEqual(pricing["EUR"], {"status": "INDICATIVE_PROXY", "observation_date": "2026-11-13",
                                         "weekly_change_bp": None, "secondary_contract": "EURH2027"})
        self.assertEqual(pricing["GBP"]["status"], "OFFICIAL_1W")
        self.assertEqual(pricing["GBP"]["weekly_change_bp"], 5)
        for currency in ("CHF", "USD", "NZD"):
            with self.subTest(currency=currency):
                self.assertEqual(pricing[currency]["status"], "WITHHELD")
                self.assertIsNone(pricing[currency]["weekly_change_bp"])
        self.assertEqual(current["state"], "OBSERVED_WITH_GAPS")

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

    def test_catalogue_period_formats(self):
        expected = {
            "2026-10-01T00:00:00Z": "2026-10-01",
            "2026-11-25 00:00:00+00:00": "2026-11-25",
            "2026-Q2": "2026-04-01", "2026Q2": "2026-04-01",
            "2026-W38": "2026-09-14", "30 Sep 2026": "2026-09-30",
            "Jul-26": "2026-07-01", "2026/8/7": "2026-08-07",
            "2026/09": "2026-09-01", "30/09/2026": "2026-09-30",
            "31-Aug-2026": "2026-08-31",
        }
        for raw, iso in expected.items():
            with self.subTest(raw=raw):
                self.assertEqual(observation_date(raw).isoformat(), iso)
        for raw in ("2026-Q5", "2026-W54", "31/02/2026", "2026-02-30",
                    "2026-10-01T99:00:00Z", "nonsense"):
            self.assertIsNone(observation_date(raw))
        self.assertEqual(age_months("2026-Q2", "2026-11-26"), 7)

    def test_mixed_period_order_and_future_days(self):
        rows = [{"id": "mix", "dates": ["30 Sep 2026", "2026-10-01T00:00:00Z",
                 "2026/8/7", "2026-11-27", "2026-11-25 00:00:00+00:00"],
                 "values": [1, 2, 3, 999, 4]}]
        self.assertEqual(latest_periods(rows, "2026-11-26")[0]["value"], 4)

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
