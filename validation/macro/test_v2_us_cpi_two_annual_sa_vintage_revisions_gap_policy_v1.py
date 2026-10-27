"""Adversarial validation for historical BLS CPI SA revision and gap policy."""
from __future__ import annotations
import copy
import json
import unittest

from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_us_cpi_two_annual_sa_vintage_revisions_gap_policy_v1 import (
    ASOF, PATH, SCHEMA, audit, rolling_prior_months
)


class TestUSCPITwoSeasonalRevisionGapPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads(PATH.read_text(encoding="utf-8"))
        cls.result=audit()

    def mutate(self, fn):
        fixture=copy.deepcopy(self.fixture)
        fn(fixture)
        with self.assertRaises(ValueError):
            audit(fixture=fixture)

    def test_two_annual_revisions_research_only(self):
        x=self.result
        self.assertEqual(x["schema"], SCHEMA)
        self.assertEqual(x["sampled_cross_issuer_month_revision_pairs"], 15)
        self.assertEqual(x["historical_2024_annual_revision_values_checked"], 4)
        self.assertEqual(x["historical_2025_annual_revision_values_checked"], 11)
        self.assertEqual(x["maximum_SA_index_revision_points"], "0.170")
        self.assertEqual(x["original_issuer_day_source_bytes_PIT_certified"], 0)
        self.assertFalse(x["original_CPIAUCSL_24m_strict_training_approved"])
        self.assertFalse(x["safe_to_publish_new_D"])
        self.assertFalse(x["safe_to_change_28_pairs"])
        self.assertFalse(x["safe_for_beta"])
        self.assertFalse(x["safe_for_forward"])

    def test_original_vs_later_seasonally_revised_issuer_values(self):
        rows={r["economic_month"]:r for r in self.fixture["revisions"]}
        self.assertEqual(
            (rows["2024-09"]["first_issued_sa_index"],
             rows["2024-09"]["subsequent_issued_sa_index"],
             rows["2024-09"]["delta_index_points"]), ("314.686","314.851","0.165"))
        self.assertEqual(
            (rows["2025-03"]["first_issued_sa_index"],
             rows["2025-03"]["subsequent_issued_sa_index"],
             rows["2025-03"]["delta_index_points"]), ("319.615","319.785","0.170"))
        self.assertEqual(rows["2025-09"]["delta_index_points"], "-0.123")
        self.assertEqual(rows["2025-11"]["delta_index_points"], "0.032")
        self.mutate(lambda d:d["revisions"][0].update(
            delta_index_points="0.166"))
        self.mutate(lambda d:d["revisions"][6].update(
            subsequent_issued_sa_index="319.615"))
        self.mutate(lambda d:d["revisions"][0].update(
            first_issue_xlsx_sha256="deadbeef"))
        self.mutate(lambda d:d["revisions"][0].update(
            subsequent_issue_xlsx_sha256="bad"))
        self.mutate(lambda d:d["revisions"].reverse())
        self.mutate(lambda d:d["revisions"].pop())

    def test_annual_rebasing_must_not_be_backdated_as_available(self):
        self.mutate(lambda d:d["revisions"][0].update(
            subsequent_annual_seasonal_rebase_issue_month="2024-09"))
        self.mutate(lambda d:d["revisions"][0].update(
            publisher_annual_seasonal_revision_issuer_day="2024-10-10"))
        self.mutate(lambda d:d["revisions"][0].update(
            quality="SOURCE_DAY_FIRST_RELEASE_PIT_APPROVED"))
        self.mutate(lambda d:d.update(
            historical_comparison_pair_quality="ORIGINAL_DAY_BYTES_CERTIFIED"))
        self.mutate(lambda d:d["summary"].update(
            source_day_original_binary_hash_confirmations=15))

    def test_separate_2025_oct_index_and_2026_oct_yoy_missing(self):
        x=self.result
        self.assertTrue(x["structurally_missing_2025_10_SA_index"])
        self.assertTrue(x["prospectively_missing_2026_10_SA_yoy_when_oct26_index_published"])
        self.assertTrue(x["future_first_vintage_eligibility_not_yet_certified"])
        self.assertIn("2025-10", rolling_prior_months("2027-10"))
        self.assertNotIn("2025-10", rolling_prior_months("2027-11"))
        self.assertIn("2026-10", rolling_prior_months("2028-10"))
        self.assertNotIn("2026-10", rolling_prior_months("2028-11"))
        self.mutate(lambda d:d["gap_policy"].update(
            missing_original_CPIAUCSL_sa_yoy_months=["2025-10"]))
        self.mutate(lambda d:d["gap_policy"].update(
            internal_BLS_oct2025_seasonal_factor_geometric_mean_is_not_public_all_items_index=False))
        self.mutate(lambda d:d["gap_policy"].update(
            rolling_SA_index_yoy_24_calendar_prior_gap_earliest_reference_month_if_no_new_missing="2027-11"))
        self.mutate(lambda d:d["gap_policy"].update(
            rolling_index_24_calendar_prior_gap_earliest_reference_month_if_no_new_missing="2027-10"))
        self.mutate(lambda d:d["gap_policy"].update(
            never_impute_month_as_original_first_release=False))
        self.mutate(lambda d:d["gap_policy"].update(
            FX_signal_or_original_PIT_training_approved=True))

    def test_estimate_allowed_for_qualitative_research_not_model_training(self):
        self.assertEqual(self.fixture["gap_policy"]["permitted_research_proxy"],
                         "24_PRIOR_PUBLISHED_OBSERVATIONS_ACROSS_25_CALENDAR_MONTHS_LABEL_AS_ESTIMATE_NON_PIT")
        self.assertFalse(self.fixture["gap_policy"]["strict_24_consecutive_month_calendar_training_tolerates_gap"])
        self.mutate(lambda d:d["gap_policy"].update(
            permitted_research_proxy="24_FULLY_CERTIFIED_CONSECUTIVE_FIRST_VINTAGES"))
        self.mutate(lambda d:d["summary"].update(g8_research_numerical_windows_remain=24))
        self.mutate(lambda d:d.update(safe_to_publish_new_D=True))
        self.mutate(lambda d:d.update(safe_for_beta=True))

    def test_readonly_and_deterministic(self):
        root=ROOT/"live_data/sections"
        protected=["D.json","PAIR_SETUP_OPERATIONAL_VIEW.json"]
        before={x:(root/x).read_bytes() for x in protected}
        again=audit()
        after={x:(root/x).read_bytes() for x in protected}
        self.assertEqual(self.result["receipt_sha256"],again["receipt_sha256"])
        self.assertEqual(before,after)


if __name__=="__main__":
    unittest.main()
