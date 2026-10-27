"""Adversarial 24-source first-web historical training completeness audit."""
from __future__ import annotations

import copy
import json
import unittest

from validation.macro.v2_g8_24_axis_training_history_gap_audit_v1 import (
    ASOF, DIMENSIONS, FX, REGISTRY, SCHEMA, evidence, idx
)
from validation.macro.v2_shadow_features_v1 import ROOT


class HistoricalTrainingGapAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = evidence(cutoff=ASOF)

    def test_24_currency_pillars_and_every_past_window_is_readonly(self):
        x = self.r
        self.assertEqual(x["schema"], SCHEMA)
        self.assertEqual(x["summary"]["economic_slots"], 24)
        self.assertEqual(x["summary"]["currencies"], 8)
        self.assertEqual(set(x["slots"]), {c + "." + p
                                            for c in FX for p in DIMENSIONS})
        self.assertEqual(x["summary"]["genuinely_historic_PIT_training_slots_certified"], 0)
        self.assertEqual(x["summary"]["currency_FX_strength_scores_approved"], 0)
        self.assertTrue(x["series_counts_do_not_equal_valid_historical_PIT_trading_samples"])
        self.assertTrue(x["EUR_EA21_membership_break_not_hidden"])
        self.assertTrue(x["CHF_SECO_rounded_never_called_first_SNB_exact"])
        self.assertTrue(x["current_US_BLS_oct2025_gap_never_imputed_as_observed"])
        for f in ("safe_to_publish_new_D", "safe_to_recalculate_28_pairs",
                  "safe_to_use_for_beta", "safe_to_use_for_forward", "writes_live_data"):
            self.assertFalse(x[f])
        for row in x["slots"].values():
            self.assertFalse(row["model_PIT_training_approved"])
            self.assertFalse(row["FX_signal_approved"])
            self.assertFalse(row["safe_to_update_D"])
            self.assertFalse(row["complete_source_day_original_bytes_and_revision_chain_certified"])
            self.assertTrue(row["not_same_as_model_PIT_training_approved"])

    def test_growth_12_quarter_training_windows_all_bounded_no_score(self):
        rows = self.r["slots"]
        for c in FX:
            r = rows[c + ".growth"]
            self.assertEqual(r["published_observation_frequency"], "Q")
            self.assertEqual(r["prior_first_release_periods_required"], 12)
            self.assertTrue(r["prior_initial_web_sequence_complete_mathematically"])
            self.assertEqual(r["missing_required_prior_periods"], [])
            self.assertEqual(r["training_evidence_source_id"],
                             "GDP_RESEARCH_TARGET_NOT_CANONICAL_REGISTERED")
            self.assertIsNone(r["model_canonical_source_id"])
            self.assertFalse(r["model_PIT_training_approved"])
        self.assertTrue(rows["EUR.growth"]["current_PIT_research_comparability_caveats"])
        self.assertTrue(rows["CHF.growth"]["current_PIT_research_comparability_caveats"])

    def test_eur_105_first_HICP_reports_not_24_homogeneous_ea21_months(self):
        x = self.r["slots"]["EUR.inflation"]
        self.assertEqual(x["first_web_periods_documented_asof"], 105)
        self.assertEqual(x["prior_first_release_periods_required"], 24)
        self.assertTrue(x["prior_initial_web_sequence_complete_mathematically"])
        self.assertFalse(x["missing_required_prior_periods"])
        self.assertIn("EURO_AREA_EA19_EA20_EA21_PRIOR_24M_NOT_HOMOGENEOUS",
                      x["current_PIT_research_comparability_caveats"])
        self.assertEqual(x["research_only_quality_label"], "DEFINITION_OR_SEMANTIC_RISK")

    def test_abs_34_source_quarters_never_substituted_from_monthly_CPI(self):
        x = self.r["slots"]["AUD.inflation"]
        self.assertEqual(x["first_web_periods_documented_asof"], 34)
        self.assertEqual(x["published_observation_frequency"], "Q")
        self.assertEqual(x["training_web_data_source_type"],
                         "ARCHIVED_PUBLISHER_FIRST_WEB_CSV_SHA_PINNED_NOT_REVERIFIED_SOURCE_DAY")
        self.assertTrue(x["prior_initial_web_sequence_complete_mathematically"])
        self.assertTrue(x["candidate_differs_from_core_or_alias_needs_review"])
        self.assertFalse(x["source_measurement_alternative_not_interchangeable"])

    def test_US_unemployment_25_historical_pilot_stops_before_shutdown_and_live_2026(self):
        x = self.r["slots"]["USD.labour"]
        # Pilot has a CONTIGUOUS 2023-09..2025-09 25-release sample. This
        # does NOT include the later October-2025 BLS missing observation,
        # and does NOT attest the 2026 economic first releases.
        self.assertEqual(x["reference_period_last_first_web"], "2025-09")
        self.assertEqual(x["first_web_periods_documented_asof"], 25)
        self.assertEqual(x["missing_required_prior_periods"], [])
        self.assertTrue(x["prior_initial_web_sequence_complete_mathematically"])
        self.assertTrue(x["bounded_BLS_pilot_ends_before_structural_oct2025_gap"])
        self.assertEqual(x["BLS_oct2025_observation_not_published"], ["2025-10"])
        self.assertTrue(x["current_live_observed_series_not_equivalent_to_bounded_web_pilot"])
        self.assertEqual(x["research_only_quality_label"],
                         "STALE_BLS_WEB_PILOT_ONLY_NOT_2026_ECONOMIC_RELEASES")
        self.assertEqual(x["training_evidence_source_id"], "LNS14000000")
        self.assertEqual(x["training_web_data_source_type"],
                         "BLS_LNS14000000_TO_FRED_UNRATE_LINEAGE_NOT_ORIGINAL_FULL_CHAIN")
        self.assertFalse(x["model_PIT_training_approved"])

    def test_chf_seco_one_decimal_does_not_certify_amarbma_exact_vintage(self):
        x = self.r["slots"]["CHF.labour"]
        self.assertEqual(x["training_web_data_source_type"],
                         "SECO_ROUNDED_ALTERNATIVE_NEVER_EXACT_SNB_SOURCE")
        self.assertIn("SECO_ONE_DECIMAL_NOT_CANONICAL_SNB_EXACT_FIRST_VINTAGE",
                      x["current_PIT_research_comparability_caveats"])
        self.assertTrue(x["source_measurement_alternative_not_interchangeable"])
        self.assertNotEqual(x["training_evidence_source_id"], x["model_canonical_source_id"])

    def test_BLS_original_news_receipt_does_not_upgrade_CPIAUCSL_or_22_of_24(self):
        result = self.r
        news = result["separate_original_BLS_news_rounded_SA_not_CPIAUCSL_exact"]
        self.assertIsNotNone(news)
        self.assertTrue(result["BLS_nov2025_two_month_change_NOT_November_MOM"])
        self.assertEqual(news["summary"]["official_issuer_archive_links_documented"], 24)
        self.assertEqual(news["summary"]["official_BLS_HTML_news_releases_opened_and_read"], 24)
        self.assertEqual(news["summary"]["archive_index_only_unreadable_HTML_links"], 0)
        self.assertEqual(news["summary"]["new_exact_CPIAUCSL_first_vintage_index_levels"], 0)
        self.assertTrue(news["reported_SA_rounded_changes_not_exact_CPIAUCSL_vintages"])
        self.assertTrue(news["2025_11_change_is_two_month_not_November_MOM"])
        self.assertFalse(news["safe_to_publish_new_D"])
        self.assertEqual(result["summary"]["prior_first_web_contiguous_12Q_or_24M_slots"], 22)
        self.assertEqual(
            result["summary"]["US_inflation_exact_CPIAUCSL_first_vintage_index_levels_added"], 0)

    def test_ALFRED_seven_release_day_index_mirror_does_not_upweight_USD(self):
        a = self.r["separate_ALFRED_release_day_index_mirror_not_BLS_original_PIT"]
        self.assertIsNotNone(a)
        self.assertEqual(a["source_page_count"], 7)
        self.assertEqual(a["BLS_original_issue_day_bytes_sha256_captured"], 0)
        self.assertEqual(a["canonical_CPIAUCSL_first_releases_source_day_certified"], 0)
        self.assertFalse(a["safe_to_publish_new_D"])
        self.assertEqual(self.r["summary"]["USD_CPI_ALFRED_release_day_SA_index_mirror_anchors"], 7)
        self.assertEqual(self.r["summary"]["US_inflation_BLS_news_pages_read"], 24)
        self.assertEqual(self.r["summary"]["US_inflation_BLS_news_index_only_links"], 0)
        self.assertEqual(self.r["summary"]["prior_first_web_contiguous_12Q_or_24M_slots"], 22)

    def test_24_BLS_issuer_month_3dp_SA_index_and_same_vintage_base_remain_research(self):
        x = self.r["separate_BLS_24_issue_month_exact_SA_indexes_not_historic_day_bytes"]
        self.assertIsNotNone(x)
        self.assertEqual(x["summary"]["published_month_workbooks_captured"], 24)
        self.assertEqual(x["summary"]["exact_SA_index_and_12m_base_candidates"], 24)
        self.assertEqual(x["summary"]["ALFRED_release_date_anchor_matches"], 7)
        self.assertEqual(x["issuer_day_original_bytes_certified"], 0)
        self.assertTrue(x["2025_10_unpublished_BLS_all_items_index_still_missing"])
        self.assertTrue(x["cannot_claim_strict_consecutive_24m_training"])
        self.assertFalse(x["safe_to_publish_new_D"])
        self.assertEqual(self.r["summary"]["USD_CPI_BLS_issuer_month_exact_SA_index_candidates_late_capture"], 24)
        self.assertEqual(self.r["summary"]["USD_CPI_BLS_issuer_month_same_vintage_12m_index_bases_late_capture"], 24)
        self.assertEqual(self.r["summary"]["USD_CPI_original_day_byte_certifications"], 0)
        self.assertEqual(self.r["summary"]["prior_first_web_contiguous_12Q_or_24M_slots"], 22)

    def test_USD_CPI_annual_revision_history_and_2026_yoy_gap_remain_nonPIT(self):
        x = self.r["separate_USD_CPI_annual_SA_revisions_and_missing_YOY_gap_policy"]
        self.assertEqual(x["sampled_cross_issuer_month_revision_pairs"], 15)
        self.assertEqual(x["maximum_SA_index_revision_points"], "0.170")
        self.assertTrue(x["structurally_missing_2025_10_SA_index"])
        self.assertTrue(x["prospectively_missing_2026_10_SA_yoy_when_oct26_index_published"])
        self.assertFalse(x["original_CPIAUCSL_24m_strict_training_approved"])
        self.assertFalse(x["safe_to_publish_new_D"])
        self.assertEqual(self.r["summary"]["USD_CPI_annual_seasonal_revision_pairs_verified"], 15)
        self.assertTrue(self.r["summary"]["USD_CPI_2025_10_index_missing_2026_10_SA_yoy_prospective_missing"])
        self.assertEqual(self.r["summary"]["prior_first_web_contiguous_12Q_or_24M_slots"],22)
        self.assertEqual(self.r["summary"]["genuinely_historic_PIT_training_slots_certified"],0)

    def test_aug2024_corrected_preceding24_issuer_z_shadow_keeps_22_24_PIT_unchanged(self):
        x = self.r["separate_USD_CPI_corrected_24_prior_issued_vs_revised_Z_not_PIT"]
        self.assertEqual(x["summary"]["official_published_prior_months"],24)
        self.assertEqual(x["summary"]["prior_calendar_months"],25)
        self.assertEqual(x["summary"]["missing_prior_month"],"2025-10")
        self.assertEqual(x["summary"]["model_PIT_history_certified"],0)
        self.assertEqual(x["Aug_2024_new_publisher_month_SA_index"],"314.121")
        self.assertTrue(x["comparison_first_issue_vs_asof_revised_never_full_PIT"])
        self.assertFalse(x["safe_to_publish_D_json"])
        self.assertFalse(x["safe_to_recalculate_28_pairs"])
        self.assertAlmostEqual(x["summary"]["robust_z_candidate_minus_revised"],-0.003115,places=6)
        self.assertEqual(self.r["summary"]["USD_CPI_issuer_month_prior_observed_corrected_23_to_24"],24)
        self.assertEqual(self.r["summary"]["prior_first_web_contiguous_12Q_or_24M_slots"],22)
        self.assertEqual(self.r["summary"]["genuinely_historic_PIT_training_slots_certified"],0)

    def test_missing_month_detected_by_period_not_merely_count(self):
        self.assertEqual(idx("2026-06", "Q"), idx("2026Q2", "Q"))
        self.assertEqual(idx("2025-12", "Q"), idx("2025Q4", "Q"))
        with self.assertRaises(ValueError):
            idx("2026-05", "Q")

    def test_tampered_canonical_registry_blocked(self):
        wrong = json.loads(REGISTRY.read_text(encoding="utf-8"))
        wrong["series"]["AUD.inflation"]["frequency"] = "M"
        with self.assertRaises(ValueError):
            evidence(cutoff=ASOF, registry=wrong)

    def test_future_cutoff_and_no_time_zone_rejected(self):
        for instant in ("2099-01-01T00:00:00Z", "2026-10-26T18:00:00+02:00"):
            with self.subTest(instant=instant), self.assertRaises(ValueError):
                evidence(cutoff=instant)

    def test_no_mutation_existing_D_and_28_pairs(self):
        folder = ROOT / "live_data/sections"
        protected = ("D.json", "PAIR_SETUP_OPERATIONAL_VIEW.json")
        before = {name: (folder/name).read_bytes() for name in protected}
        r = evidence(cutoff=ASOF)
        after = {name: (folder/name).read_bytes() for name in protected}
        self.assertEqual(before, after)
        self.assertEqual(r["receipt_sha256"], self.r["receipt_sha256"])


if __name__ == "__main__":
    unittest.main()
