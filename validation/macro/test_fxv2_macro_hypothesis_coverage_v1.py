#!/usr/bin/env python3
"""Safety and coverage tests for the isolated FXV2 Macro hypothesis protocol."""
from __future__ import annotations
import copy
import json
import unittest
from pathlib import Path

from validation.macro.fxv2_macro_hypothesis_coverage_v1 import ROOT, inspect

CANDIDATE = ROOT / "site/fx-quant-v2/macro-baseline-candidate-v1.json"


class TestHypotheses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads(CANDIDATE.read_text(encoding="utf-8"))

    def test_canonical_20261104_coverage_without_forecast(self):
        report = inspect(self.original)
        self.assertEqual(report["total_pairs"], 28)
        coverage = report["individual_axis_coverage"]
        if report["source_as_of"] == "2026-11-04":
            self.assertEqual(coverage, {
                "growth_acceleration_pp": 1,
                "unemployment_change_pp": 15,
                "inflation_change_pp": 11,
            })
            self.assertEqual(
                report["experiments"]["H0_LABOUR_CHANGE"]["descriptive_coverage_pairs"], 15)
            self.assertEqual(
                report["experiments"]["H1_ACTIVITY_CHANGE"]["descriptively_comparable_pairs"],
                ["EUR/USD"])
            self.assertEqual(
                report["experiments"]["H2_ACTIVITY_INFLATION_CONTEXT"]["descriptive_coverage_pairs"], 0)
        for experiment in report["experiments"].values():
            self.assertIsNone(experiment["macro_score"])
            self.assertIsNone(experiment["fx_forecast"])
            self.assertIsNone(experiment["out_of_sample_skill"])
            self.assertFalse(experiment["eligible_for_pit_estimation"])
            self.assertFalse(experiment["eligible_for_fx_forecast_test"])
        self.assertEqual(
            report["experiments"]["H3_MACRO_OIS6M_INTERACTION"]["descriptive_coverage_pairs"], 0)
        self.assertFalse(report["released_to_fx_core"])
        self.assertFalse(report["backtest_executed"])
        self.assertIsNone(report["prediction_accuracy"])

    def test_deterministic_and_read_only(self):
        raw = CANDIDATE.read_bytes()
        report1 = inspect(self.original)
        report2 = inspect(copy.deepcopy(self.original))
        self.assertEqual(report1, report2)
        self.assertEqual(raw, CANDIDATE.read_bytes())

    def test_rejects_fake_comparability_and_signal_spoofing(self):
        def change_1(s):
            s["eligible_for_backtests"] = True
        def change_2(s):
            s["pairs"]["EUR/GBP"]["macro_fx_signal"] = "LONG"
        def change_3(s):
            s["pairs"]["EUR/GBP"]["contrasts"]["inflation_change_pp"]["same_period"] = True
        def change_4(s):
            s["pairs"]["EUR/GBP"]["contrasts"]["inflation_change_pp"]["delta_base_minus_quote_pp"] = 0.0
        def change_5(s):
            s["pairs"]["EUR/USD"]["contrasts"]["growth_acceleration_pp"]["delta_base_minus_quote_pp"] = 9.0
        def change_6(s):
            s["features"]["NZD"]["growth_qoq_pct"]["gdp_acceleration_pp"] = float("nan")
        def change_7(s):
            s["published_source_lineage"] = "PIT_CERTIFIED"
        for mutation in (change_1, change_2, change_3, change_4,
                         change_5, change_6, change_7):
            with self.subTest(mutation=mutation.__name__):
                source = copy.deepcopy(self.original)
                mutation(source)
                with self.assertRaises(ValueError):
                    inspect(source)

    def test_policy_missing_never_recoded_as_zero_repricing(self):
        report = inspect(self.original)
        row = report["experiments"]["H3_MACRO_OIS6M_INTERACTION"]
        self.assertEqual(row["descriptive_coverage_pairs"], 0)
        self.assertEqual(set(row["blocked_pairs"]), set(self.original["pairs"]))
        self.assertTrue(all("FROZEN_COMPARABLE_OIS6M_REPRICING" in blockers
                            for blockers in row["blocked_pairs"].values()))


if __name__ == "__main__":
    unittest.main()
