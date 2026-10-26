"""The G8 Growth source choice is research-only and GDP horizons do not mix."""
from __future__ import annotations

import copy
import unittest

from validation.macro.v2_g8_quarterly_gdp_research_target_v1 import (
    audit, CURRENCIES, QUARTERLY_GOAL, SOURCES, TRUSTED_DOMAINS,
    NZ_2026Q2_PUBLICATION_REFERENCE, research_qoq_from_same_vintage_levels,
)


class GDPResearchTargetTests(unittest.TestCase):
    def test_eight_official_quarterly_broad_growth_targets_without_model_promotion(self):
        r = audit()
        self.assertEqual([x["currency"] for x in r["rows"]], list(CURRENCIES))
        self.assertEqual(r["primary_economic_dimension"], QUARTERLY_GOAL)
        self.assertEqual(r["summary"]["quarterly_GDP_research_targets_documented"], 8)
        self.assertEqual(r["summary"]["old_activity_proxies_retained_separately"], 8)
        self.assertEqual(r["summary"]["official_primary_GDP_PIT_source_series_admitted"], 0)
        self.assertFalse(r["summary"]["cross_currency_GDP_comparability_certified"])
        for key in ("can_replace_2026_09_25_D_macro", "can_publish_new_growth_scores",
                    "can_change_28_pair_theses", "can_use_for_beta",
                    "can_use_for_forward_restarts", "writes_live_data"):
            self.assertIs(r[key], False, key)
        self.assertTrue(all(x["primary_quarterly_GDP_live_adapter_selected"] is False
                            and x["primary_quarterly_GDP_release_vintage_certified"] is False
                            and x["pair_ranking_use_permitted"] is False
                            for x in r["rows"]))
        self.assertEqual(set(SOURCES), set(TRUSTED_DOMAINS))

    def test_nz_three_official_quarterly_measures_have_different_definitions(self):
        nz = NZ_2026Q2_PUBLICATION_REFERENCE
        self.assertEqual(nz["publisher_release_day"], "2026-09-17")
        self.assertEqual(nz["quarterly_qoq_pct"], 0.2)
        self.assertEqual(nz["same_quarter_prior_year_yoy_pct"], 2.6)
        self.assertEqual(nz["year_ended_average_annual_growth_pct"], 1.7)
        self.assertEqual(len({nz["quarterly_qoq_pct"], nz["same_quarter_prior_year_yoy_pct"],
                              nz["year_ended_average_annual_growth_pct"]}), 3)
        self.assertIn("QOQ_VS_SAME_QUARTER_YOY_VS_ANNUAL_AVERAGE_MUST_NOT_MIX",
                      SOURCES["NZD"][3])

    def test_primary_national_accounts_source_is_not_old_industrial_proxy(self):
        r = audit()
        by = {x["currency"]: x for x in r["rows"]}
        for c in ("USD", "EUR", "GBP", "JPY", "CHF"):
            self.assertEqual(by[c]["preexisting_activity_candidate_economic_family"],
                             "INDUSTRIAL_PRODUCTION")
        self.assertEqual(by["CAD"]["preexisting_activity_candidate_economic_family"],
                         "REAL_GDP_INDUSTRY")
        self.assertEqual(by["AUD"]["preexisting_activity_candidate_transform"],
                         "REPORTED_QOQ_RATE")
        self.assertEqual(by["NZD"]["preexisting_activity_candidate_transform"],
                         "REPORTED_YOY_RATE")

    @staticmethod
    def valid_quarters():
        a = {"quarter": "2026Q1", "real_gdp_sa_level": 100.0,
             "measure": "REAL_GDP_TOTAL_SA_LEVEL", "publication_stage": "REVISION",
             "visible_at_utc": "2026-09-15T00:00:00Z",
             "source_snapshot_sha256": "a" * 64, "publisher_dataset": "GDP_CHAINED_CVM"}
        b = {**a, "quarter": "2026Q2", "real_gdp_sa_level": 102.0,
             "publication_stage": "FIRST"}
        return a, b

    def test_two_consecutive_levels_same_vintage_calculate_nonannualized_qoq(self):
        a, b = self.valid_quarters()
        self.assertAlmostEqual(research_qoq_from_same_vintage_levels(
            a, b, cutoff="2026-09-15T00:00:00Z"), 2.0, places=9)
        # BEA-style SAAR level itself is fine with a ratio; published annualized
        # *growth RATE* would be rejected under a different type.
        b["real_gdp_sa_level"] = 98
        self.assertAlmostEqual(research_qoq_from_same_vintage_levels(
            a, b, cutoff="2026-09-15T00:00:00Z"), -2.0)

    def test_pure_growth_math_rejects_annualized_headline_future_and_mixed_vintages(self):
        a, b = self.valid_quarters()
        bad = []
        c = copy.deepcopy(b); c["measure"] = "GDP_ANNUALIZED_GROWTH_RATE"; bad.append((a, c))
        c = copy.deepcopy(b); c["source_snapshot_sha256"] = "b" * 64; bad.append((a, c))
        c = copy.deepcopy(b); c["quarter"] = "2026Q3"; bad.append((a, c))
        c = copy.deepcopy(b); c["visible_at_utc"] = "2026-09-16T00:00:00Z"; bad.append((a, c))
        c = copy.deepcopy(b); c["publisher_dataset"] = "INDUSTRIAL_PRODUCTION"; bad.append((a, c))
        c = copy.deepcopy(b); c["real_gdp_sa_level"] = None; bad.append((a, c))
        c = copy.deepcopy(b); c["real_gdp_sa_level"] = float("inf"); bad.append((a, c))
        c = copy.deepcopy(b); c["real_gdp_sa_level"] = True; bad.append((a, c))
        c = copy.deepcopy(b); c["publication_stage"] = "ESTIMATED"; bad.append((a, c))
        for i, (prior, current) in enumerate(bad):
            with self.subTest(i=i), self.assertRaises((ValueError, TypeError)):
                research_qoq_from_same_vintage_levels(
                    prior, current, cutoff="2026-09-15T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
