"""Adversarial availability-time matrix across all 24 G8 economic dimensions."""
from __future__ import annotations

import copy
import json
import math
import unittest

from validation.macro.v2_g8_24_axis_asof_evidence_v1 import (
    SCHEMA, FX, DIMENSIONS, REGISTRY, run, source_snapshot,
)
from validation.macro.v2_eur_aud_archival_first_web_overlay_v1 import archived_overlay
from validation.macro.v2_shadow_features_v1 import ROOT


class SynchronizedMacroEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.day = "2026-10-27T00:00:00Z"
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.snapshot = run(as_of=cls.day)

    def test_all_24_dimensions_have_unique_release_clock_and_pillar_identity(self):
        r = self.snapshot
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["summary"]["target_slots"], 24)
        self.assertEqual(r["summary"]["currency_count"], 8)
        self.assertEqual(set(r["slots"]), {f"{ccy}.{p}" for ccy in FX for p in DIMENSIONS})
        self.assertTrue(r["release_clock_not_same_as_economic_reference_period"])
        self.assertTrue(r["cross_country_economic_periods_not_synchronized"])
        self.assertTrue(r["no_cross_currency_rank_or_FX_direction_estimated"])
        for name in ("safe_to_publish_new_D", "safe_to_update_pair_theses",
                     "safe_to_use_for_beta", "safe_to_use_for_forward",
                     "writes_live_data"):
            self.assertFalse(r[name])
        self.assertEqual(r["summary"]["model_macro_scores_approved"], 0)
        self.assertEqual(r["summary"]["FX_pair_rankings_rebuilt"], 0)
        self.assertEqual(r["summary"]["official_complete_PIT_training_slots"], 0)
        for row in r["slots"].values():
            self.assertFalse(row["model_score_authorized"])
            self.assertFalse(row["fx_signal_authorized"])
            self.assertFalse(row["complete_pit_training_history_verified"])
            self.assertFalse(
                row["source_byte_archived_for_original_publication_day_independently_reverified"])

    def test_archive_retains_original_HICP_flash_and_quarterly_ABS_metric(self):
        rows = self.snapshot["slots"]
        eur = rows["EUR.inflation"]
        self.assertEqual(eur["reported_economic_period"], "2026-09")
        self.assertEqual(eur["first_web_value"], 3.8)
        self.assertEqual(eur["eurozone_membership"], "EA21")
        self.assertFalse(eur["homogeneous_24_month_EA_membership_reference"])
        self.assertEqual(eur["same_membership_prior_months"], 8)
        self.assertEqual(eur["available_canonical_initial_archived_release_records"], 105)
        self.assertTrue(eur["candidate_detailed_never_rewrites_first_flash"])
        aud = rows["AUD.inflation"]
        self.assertEqual(aud["registered_canonical_frequency"], "Q")
        self.assertEqual(aud["official_web_candidate_frequency"], "M")
        self.assertEqual(aud["reported_economic_period"], "2026-06")
        self.assertEqual(aud["first_web_value"], 3.9)
        self.assertEqual(aud["available_canonical_initial_archived_release_records"], 34)
        self.assertTrue(aud["quarterly_abs_cpi_never_replaced_by_monthly_candidate"])
        self.assertEqual(
            self.snapshot["summary"]["first_release_observations_in_archived_EUR_AUD"], 139)

    def test_chf_rounded_only_with_no_fake_SNB_exact_release_timestamp(self):
        swiss = self.snapshot["slots"]["CHF.labour"]
        self.assertEqual(swiss["reported_economic_period"], "2026-09")
        self.assertEqual(swiss["first_web_value"], 3.1)
        self.assertEqual(
            swiss["compatible_exact_rate_interval_pct"],
            {"lower_inclusive": 3.05, "upper_exclusive": 3.15})
        self.assertEqual(
            swiss["source_quality"],
            "ALTERNATIVE_SECO_ROUNDED_FIRST_WEB_NOT_SNB_EXACT_VINTAGE")
        self.assertTrue(swiss["rounded_SECO_as_provisional_alternative_not_exact_SNB"])
        self.assertIsNone(swiss["canonical_exact_SNB_first_release_timestamp_utc"])
        self.assertFalse(swiss["canonical_exact_SNB_value_on_first_release_verified"])

    def test_same_reference_month_does_not_mean_same_release_day(self):
        r = self.snapshot["slots"]
        dates = {x["first_documented_web_gate_utc"]
                 for x in r.values() if x["web_first_release_known_at_cutoff"]}
        self.assertGreater(len(dates), 8)
        self.assertEqual(r["USD.growth"]["original_reported_unit"],
                         "PERCENT_SAAR_ANNUALIZED")
        self.assertAlmostEqual(r["USD.growth"]["first_web_value"],
                               100 * (1.015 ** 0.25 - 1), places=10)
        self.assertEqual(r["USD.growth"]["reported_economic_period"], "2026Q2")
        self.assertEqual(r["EUR.growth"]["reported_economic_period"], "2026Q2")
        self.assertEqual(r["EUR.inflation"]["reported_economic_period"], "2026-09")
        self.assertEqual(r["AUD.inflation"]["reported_economic_period"], "2026-06")

    def test_chf_rounded_rate_not_visible_before_2026_oct7_gate(self):
        before = run(as_of="2026-10-06T23:59:59Z")
        after = run(as_of="2026-10-07T00:00:00Z")
        self.assertNotEqual(
            before["slots"]["CHF.labour"].get("source_quality"),
            "ALTERNATIVE_SECO_ROUNDED_FIRST_WEB_NOT_SNB_EXACT_VINTAGE")
        self.assertEqual(after["slots"]["CHF.labour"]["first_web_value"], 3.1)
        self.assertEqual(
            after["slots"]["CHF.labour"]["first_documented_web_gate_utc"],
            "2026-10-07T00:00:00+00:00")

    def test_EUR_2026_sep_flash_not_visible_on_october2(self):
        before = run(as_of="2026-10-02T23:59:59Z")
        after = run(as_of="2026-10-03T00:00:00Z")
        self.assertEqual(before["slots"]["EUR.inflation"]["reported_economic_period"],
                         "2026-08")
        self.assertEqual(after["slots"]["EUR.inflation"]["reported_economic_period"],
                         "2026-09")
        self.assertEqual(after["slots"]["EUR.inflation"]["first_web_value"], 3.8)

    def test_AUD_quarterly_June_2026_not_early_at_1130_Canberra(self):
        before = run(as_of="2026-07-29T01:29:59Z")
        after = run(as_of="2026-07-29T01:30:00Z")
        self.assertEqual(before["slots"]["AUD.inflation"]["reported_economic_period"],
                         "2026-03")
        self.assertEqual(after["slots"]["AUD.inflation"]["reported_economic_period"],
                         "2026-06")
        self.assertEqual(after["slots"]["AUD.inflation"]["first_web_value"], 3.9)

    def test_poisoned_registries_and_archived_sources_fail_closed(self):
        wrong = copy.deepcopy(self.registry)
        wrong["series"]["AUD.inflation"]["frequency"] = "M"
        with self.assertRaisesRegex(ValueError, "four acknowledged semantic source mismatches"):
            source_snapshot(cutoff=self.day, registry=wrong)
        wrong = copy.deepcopy(self.registry)
        del wrong["series"]["USD.labour"]
        with self.assertRaisesRegex(ValueError, "16 G8"):
            source_snapshot(cutoff=self.day, registry=wrong)
        damaged = archived_overlay(as_of=self.day)
        damaged["summary"]["pinned_original_first_web_rows"] = 140
        with self.assertRaisesRegex(ValueError, "archived canonical"):
            source_snapshot(cutoff=self.day, registry=self.registry, archival=damaged)

    def test_future_lookahead_and_non_UTC_cutoff_refused(self):
        for time in ("2099-01-01T00:00:00Z",
                     "2026-10-27T14:00:00+02:00",
                     "2026-10-27"):
            with self.subTest(time=time), self.assertRaises(ValueError):
                run(as_of=time)

    def test_no_mutation_of_live_core_and_pairs(self):
        root = ROOT / "live_data/sections"
        names = ("D.json", "PAIR_SETUP_OPERATIONAL_VIEW.json")
        before = {p: (root / p).read_bytes() for p in names}
        again = run(as_of=self.day)
        after = {p: (root / p).read_bytes() for p in names}
        self.assertEqual(before, after)
        self.assertEqual(again["receipt_sha256"], self.snapshot["receipt_sha256"])


if __name__ == "__main__":
    unittest.main()
