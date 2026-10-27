"""GDP 2021-26 initial publisher statements: deterministic as-of research tests."""
import copy
import math
import unittest
from datetime import datetime, timezone

from validation.macro.v2_g8_gdp_first_web_growth_features_v1 import (
    FX, nonannualized, qidx, receipt, run
)
from validation.macro.v2_g8_gdp_unified_web_research_v1 import unified_research_rows


class FirstWebGrowthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = unified_research_rows()

    def test_actual_g8_12_prior_quarters_and_8_descriptive_not_live_scores(self):
        r = run(as_of="2026-10-27T00:00:00Z")
        self.assertEqual(set(r["features"]), set(FX))
        self.assertEqual(r["summary"]["g8_currencies"], 8)
        self.assertEqual(r["summary"]["growth_observational_features_computed"], 8)
        self.assertEqual(r["summary"]["model_growth_scores_computed"], 0)
        self.assertTrue(all(v["latest_initial_period"] == "2026Q2" for v in r["features"].values()))
        self.assertTrue(all(v["training_prior_quarters_required"] == 12 for v in r["features"].values()))
        self.assertTrue(all(v["training_window_end"] == "2026Q1" for v in r["features"].values()))
        self.assertTrue(all(v["training_window_start"] == "2023Q2" for v in r["features"].values()))
        for v in r["features"].values():
            self.assertIsNone(v["numeric_model_growth_score"])
            self.assertFalse(v["safe_to_promote_growth_score"])
            self.assertFalse(v["actual_PIT_backtest_eligible"])
            self.assertTrue(math.isfinite(v["research_robust_growth_z"]))
            self.assertTrue(-3 <= v["research_robust_growth_z"] <= 3)
        for field in ("can_publish_D_json", "can_use_for_beta",
                      "can_use_for_forward", "can_recalculate_28_pairs", "writes_live_data"):
            self.assertFalse(r[field])

    def test_us_annualized_not_confused_with_qoq_and_latest_revision_excluded(self):
        r = run(as_of="2026-10-27T00:00:00Z")
        us = r["features"]["USD"]
        self.assertEqual(us["latest_reported_unit"], "PERCENT_SAAR_ANNUALIZED")
        self.assertAlmostEqual(us["latest_nonannualized_qoq_pct"],
                               100 * (1.015 ** 0.25 - 1), places=11)
        self.assertAlmostEqual(us["latest_visible_revision"]["reported_value"], 2.2)
        self.assertAlmostEqual(us["latest_reported_value"], 1.5)
        self.assertTrue(us["latest_visible_revision"]["NOT_used_to_train_initial_web_z"])
        eur = r["features"]["EUR"]
        self.assertAlmostEqual(eur["latest_reported_value"], 0.4)
        self.assertAlmostEqual(eur["latest_visible_revision"]["reported_value"], 0.6)

    def test_swiss_adjustment_and_euro_area_population_break_not_hidden(self):
        r = run(as_of="2026-10-27T00:00:00Z")
        chf = r["features"]["CHF"]
        self.assertIn("SWISS_INITIAL_GDP_SPORTS_FLASH_DEFINITION_MIXED",
                      chf["growth_definition_caveats"])
        self.assertIn("PERCENT_QOQ_FLASH_ADJUSTMENT_UNSPECIFIED",
                      chf["training_first_web_unit_variants"])
        eur = r["features"]["EUR"]
        self.assertIn("EURO_AREA_POPULATION_DEFINITION_NOT_UNIFORM_OR_UNPINNED",
                      eur["growth_definition_caveats"])
        self.assertGreaterEqual(
            r["summary"]["growth_observational_features_with_definition_caveats"], 2)
        self.assertTrue(r["no_cross_country_rank"] if "no_cross_country_rank" in r
                        else not r["macro_model_score_authorized"])

    def test_cutoff_does_not_leak_first_releases_or_later_revisions(self):
        r = receipt(self.rows, as_of="2026-08-10T00:00:00Z")
        self.assertEqual(r["features"]["USD"]["latest_initial_period"], "2026Q2")
        self.assertEqual(r["features"]["GBP"]["latest_initial_period"], "2026Q1")
        self.assertEqual(r["features"]["JPY"]["latest_initial_period"], "2026Q1")
        us = receipt(self.rows, as_of="2026-07-30T23:59:59Z")["features"]["USD"]
        self.assertEqual(us["latest_initial_period"], "2026Q1")
        # Even long after revised data, the normalized current input stays first.
        after = receipt(self.rows, as_of="2026-10-27T00:00:00Z")["features"]["USD"]
        self.assertEqual(after["latest_reported_value"], 1.5)

    def test_missing_quarter_blocks_math_no_interpolation(self):
        rows = [r for r in self.rows if not
                (r["currency"] == "CAD" and r["reference_quarter"] == "2025Q3")]
        out = receipt(rows, as_of="2026-10-27T00:00:00Z")["features"]["CAD"]
        self.assertEqual(out["status"], "INSUFFICIENT_CONSECUTIVE_INITIAL_WEB_QUARTERS")
        self.assertIn("2025Q3", out["missing_required_reference_quarters"])
        self.assertIsNone(out["research_robust_growth_z"])

    def test_wrong_unit_or_faked_publisher_rejected(self):
        first = next(x for x in self.rows if
                     x["currency"] == "USD" and x["reference_quarter"] == "2026Q2"
                     and x["stage_order"] == 0)
        altered = [dict(x) if x is first else x for x in self.rows]
        fake = next(x for x in altered if
                    x["currency"] == "USD" and x["reference_quarter"] == "2026Q2"
                    and x["stage_order"] == 0)
        fake["reported_unit"] = "PERCENT_QOQ_SA"
        with self.assertRaisesRegex(ValueError, "unit definition|GDP metric/horizon"):
            receipt(altered, as_of="2026-10-27T00:00:00Z")
        bad = [dict(x) if x is first else x for x in self.rows]
        fake = next(x for x in bad if
                    x["currency"] == "USD" and x["reference_quarter"] == "2026Q2"
                    and x["stage_order"] == 0)
        fake["source_url"] = "https://malicious.example/fake"
        with self.assertRaisesRegex(ValueError, "publisher"):
            receipt(bad, as_of="2026-10-27T00:00:00Z")

    def test_no_earlier_same_day_news_admission(self):
        r = receipt(self.rows, as_of="2026-08-13T23:59:59Z")
        self.assertEqual(r["features"]["GBP"]["latest_initial_period"], "2026Q1")
        self.assertFalse(r["historical_first_day_archival_bytes_certified"])


if __name__ == "__main__":
    unittest.main()
