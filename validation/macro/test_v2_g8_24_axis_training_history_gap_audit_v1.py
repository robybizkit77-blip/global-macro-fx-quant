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
