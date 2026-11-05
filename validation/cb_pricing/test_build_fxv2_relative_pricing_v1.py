#!/usr/bin/env python3
"""Adversarial research-only tests: 28 pairs, 84 date-aware comparisons."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from validation.cb_pricing.build_fxv2_relative_pricing_v1 import (
    ROOT, G8, SCHEMA, TENORS, build,
)

P = ROOT / "site/fx-quant-v2/ois-pricing-snapshot.json"
M = ROOT / "site/fx-quant-v2/macro-baseline-candidate-v1.json"


class RelativePricingResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = P.read_bytes()
        cls.pricing = json.loads(cls.source)
        cls.macro = json.loads(M.read_text())
        cls.report = build(cls.pricing, cls.macro, cls.source)

    def test_exact_28pair_macro_universe_and_84_comparisons(self):
        r = self.report
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["summary"]["pairs"], 28)
        self.assertEqual(r["summary"]["currencies"], 8)
        self.assertEqual(r["summary"]["horizon_comparisons"], 84)
        self.assertEqual(list(r["pairs"]), list(self.macro["pairs"]))
        for name, row in r["pairs"].items():
            self.assertEqual(set(row["horizons"]), set(TENORS))
            self.assertEqual(name, row["base"] + "/" + row["quote"])
            self.assertIsNone(row["fx_signal"])
            self.assertIsNone(row["expected_return"])
            self.assertIsNone(row["carry_estimate"])

    def test_arithmetic_orientation_and_published_real_inputs(self):
        r = self.report["pairs"]
        eurusd = r["EUR/USD"]["horizons"]["6m"]
        self.assertAlmostEqual(eurusd["spread_bp"], -145.25)
        self.assertEqual(eurusd["base_as_of"], "2026-11-03")
        self.assertEqual(eurusd["quote_as_of"], "2026-11-04")
        self.assertFalse(eurusd["same_date"])
        self.assertEqual(eurusd["date_gap_days"], 1)
        self.assertTrue(eurusd["estimate_involved"])
        self.assertFalse(eurusd["proxy_involved"])
        self.assertAlmostEqual(r["GBP/JPY"]["horizons"]["6m"]["spread_bp"], 280.84)
        audnzd = r["AUD/NZD"]["horizons"]["6m"]
        self.assertAlmostEqual(audnzd["spread_bp"], 122.5)
        self.assertTrue(audnzd["proxy_involved"])
        self.assertTrue(audnzd["same_date"])
        self.assertEqual(audnzd["quote_contract"], "Jun 2027")

    def test_all_observations_dated_and_only_arithmetic(self):
        r = self.report
        self.assertEqual(r["pricing_source_content_sha256"], hashlib.sha256(self.source).hexdigest())
        for key in ("not_ois_equivalent", "not_policy_repricing", "not_fx_carry",
                    "no_cross_date_market_move_inferred",
                    "source_dates_are_independent",
                    "same_bucket_does_not_guarantee_same_expiry_or_index"):
            self.assertTrue(r[key], key)
        for key in ("eligible_for_fx_engine", "eligible_for_backtests",
                    "eligible_for_automatic_core_rebase"):
            self.assertFalse(r[key], key)
        self.assertTrue(r["canonical_fx_core_untouched"])
        summary = r["summary"]
        self.assertEqual(summary["same_date_comparisons"] + summary["mixed_date_comparisons"], 84)
        self.assertGreater(summary["mixed_date_comparisons"], 0)
        self.assertGreater(summary["estimated_comparisons"], 0)
        self.assertGreater(summary["proxy_comparisons"], 0)
        self.assertEqual(summary["generated_fx_signals"], 0)
        self.assertEqual(summary["generated_policy_repricing_signals"], 0)
        for pair in r["pairs"].values():
            for tenor in pair["horizons"].values():
                self.assertIsNone(tenor["fx_signal"])
                self.assertIsNone(tenor["policy_repricing_bp"])
                self.assertEqual(
                    round(100 * (tenor["base_rate_pct"] - tenor["quote_rate_pct"]), 3),
                    tenor["spread_bp"])

    def test_refuse_incomplete_rates_or_future_date(self):
        p = copy.deepcopy(self.pricing)
        del p["currencies"]["NZD"]["horizons"]["12m"]
        with self.assertRaisesRegex(ValueError, "missing tenor"):
            build(p, self.macro, self.source)
        p = copy.deepcopy(self.pricing)
        p["currencies"]["EUR"]["horizons"]["6m"]["as_of"] = "2027-03-05"
        with self.assertRaisesRegex(ValueError, "newer than snapshot"):
            build(p, self.macro, self.source)
        p = copy.deepcopy(self.pricing)
        p["currencies"]["CHF"]["horizons"]["3m"]["rate"] = 100
        with self.assertRaisesRegex(ValueError, "invalid rate"):
            build(p, self.macro, self.source)

    def test_refuse_relabeling_as_operational_and_pair_coverage_drift(self):
        p = copy.deepcopy(self.pricing)
        p["eligible_for_fx_engine"] = True
        with self.assertRaisesRegex(ValueError, "informational"):
            build(p, self.macro, self.source)
        m = copy.deepcopy(self.macro)
        m["eligible_for_live_fx_signals"] = True
        with self.assertRaisesRegex(ValueError, "non-operational"):
            build(self.pricing, m, self.source)
        m = copy.deepcopy(self.macro)
        del m["pairs"]["EUR/USD"]
        with self.assertRaisesRegex(ValueError, "28-pair universe"):
            build(self.pricing, m, self.source)


if __name__ == "__main__":
    unittest.main()
