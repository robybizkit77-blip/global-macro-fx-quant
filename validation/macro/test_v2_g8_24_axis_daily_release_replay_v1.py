"""Strict day-by-day G8 24-axis issuer release replay: never a model PIT backtest."""
from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime, timezone

from validation.macro.v2_g8_24_axis_daily_release_replay_v1 import (
    SCHEMA, FX, DIMENSIONS, REGISTRY, replay
)
from validation.macro.v2_g8_24_axis_asof_evidence_v1 import run as once
from validation.macro.v2_eur_aud_archival_first_web_overlay_v1 import archived_overlay
from validation.macro.v2_shadow_features_v1 import ROOT


class DailyG8ReleaseReconstruction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.month = replay(start="2026-10-01", end="2026-10-20")

    def test_each_utc_day_has_exactly_24_independent_known_asof_slots(self):
        d = self.month
        self.assertEqual(d["schema"], SCHEMA)
        self.assertEqual(d["window"]["daily_cuts"], 20)
        self.assertTrue(d["window"]["latest_incomplete_UTC_day_excluded"])
        self.assertEqual(d["summary"]["G8_currencies"], 8)
        self.assertEqual(d["summary"]["economic_slots_per_day"], 24)
        self.assertEqual(d["summary"]["source_evidence_days"], 20)
        self.assertEqual(d["summary"]["24_axis_joint_original_vintage_training_days_certified"], 0)
        self.assertEqual(d["summary"]["FX_out_of_sample_tests"], 0)
        self.assertEqual(d["summary"]["macro_model_scores_approved"], 0)
        self.assertEqual(d["summary"]["pair_rankings_reshuffled"], 0)
        expected = {f"{currency}.{p}" for currency in FX for p in DIMENSIONS}
        for item in d["daily_evidence_snapshots"]:
            self.assertEqual(set(item["24_slots_latest_known_source"]), expected)
            self.assertEqual(item["as_of_end_utc"][-6:], "+00:00")
            self.assertEqual(item["as_of_end_utc"][11:26], "23:59:59.999999")
            self.assertTrue(item[
                "unchanged_values_are_CARRIED_VISIBLE_EVIDENCE_not_interpolated_new_data"])
            self.assertTrue(item["no_joint_PIT_macro_training_certification"])
            for v in item["24_slots_latest_known_source"].values():
                self.assertFalse(v["source_PIT_historical_training_certified"])
                self.assertFalse(v["can_use_for_FX_ranking"])
        for name in ("safe_to_publish_new_D", "safe_to_update_pair_theses",
                     "safe_for_beta", "safe_for_forward", "writes_live_data"):
            self.assertFalse(d[name])

    def test_october_eurostat_flash_first_gate_and_no_early_september(self):
        days = {d["as_of_day_utc"]: d for d in self.month["daily_evidence_snapshots"]}
        before = days["2026-10-02"]["24_slots_latest_known_source"]["EUR.inflation"]
        after = days["2026-10-03"]["24_slots_latest_known_source"]["EUR.inflation"]
        self.assertEqual(before["reference_period"], "2026-08")
        self.assertEqual(after["reference_period"], "2026-09")
        self.assertEqual(after["first_web_value"], 3.8)
        self.assertEqual(after["eur_membership_regime"], "EA21")
        self.assertFalse(after["eur_24_prior_month_same_membership"])
        self.assertEqual(len(days["2026-10-03"]["publisher_gate_driven_changes_from_prior_day"]) >= 1, True)
        affected = {x["slot"] for x in days["2026-10-03"]
                    ["publisher_gate_driven_changes_from_prior_day"]}
        self.assertIn("EUR.inflation", affected)
        self.assertTrue(all(x["not_a_causal_event_FX_claim"]
                            for x in days["2026-10-03"]
                            ["publisher_gate_driven_changes_from_prior_day"]))

    def test_seco_rounded_3p1_only_from_conservative_october7_gate(self):
        days = {d["as_of_day_utc"]: d for d in self.month["daily_evidence_snapshots"]}
        before = days["2026-10-06"]["24_slots_latest_known_source"]["CHF.labour"]
        after = days["2026-10-07"]["24_slots_latest_known_source"]["CHF.labour"]
        self.assertNotEqual(before["source_quality"],
                            "ALTERNATIVE_SECO_ROUNDED_FIRST_WEB_NOT_SNB_EXACT_VINTAGE")
        self.assertEqual(after["first_web_value"], 3.1)
        self.assertEqual(after["value_precision"], "ONE_DECIMAL_PCT_INTERVAL")
        self.assertEqual(after["chf_precision_interval_if_rounded"],
                         {"lower_inclusive": 3.05, "upper_exclusive": 3.15})
        self.assertTrue(any(x["slot"] == "CHF.labour"
                            for x in days["2026-10-07"]
                            ["publisher_gate_driven_changes_from_prior_day"]))

    def test_revisions_are_separate_from_first_gdp_and_can_change_later(self):
        a = self.month["daily_evidence_snapshots"][-1]["24_slots_latest_known_source"]
        for currency in FX:
            self.assertTrue(a[f"{currency}.growth"]["first_web_known_asof"])
        daily = replay(start="2026-08-15", end="2026-08-25")
        self.assertEqual(daily["window"]["daily_cuts"], 11)
        self.assertTrue(all(not x["source_PIT_historical_training_certified"]
                            for d in daily["daily_evidence_snapshots"]
                            for x in d["24_slots_latest_known_source"].values()))
        # USD GDP always keeps first observation from its own release even
        # after another GDP revision becomes visible at a later timestamp.
        before = once(as_of="2026-08-20T23:59:59Z")["slots"]["USD.growth"]
        later = once(as_of="2026-10-20T23:59:59Z")["slots"]["USD.growth"]
        self.assertAlmostEqual(later["first_web_value"],
                               100 * (1.015 ** .25 - 1), places=10)
        self.assertEqual(later["original_reported_value"], 1.5)
        self.assertGreaterEqual(later["asof_value_latest_known_revision"],
                                later["first_web_value"])

    def test_quiet_days_carry_existing_release_not_interpolated_value(self):
        r = self.month["daily_evidence_snapshots"]
        quiet = [x for x in r[1:] if x["days_without_new_first_web_or_latest_revision"]]
        self.assertGreater(len(quiet), 0)
        for row in quiet:
            self.assertEqual(row["publisher_gate_driven_changes_from_prior_day"], [])
            self.assertTrue(row[
                "unchanged_values_are_CARRIED_VISIBLE_EVIDENCE_not_interpolated_new_data"])

    def test_daily_current_period_never_indicates_same_observation_month(self):
        d = self.month["daily_evidence_snapshots"][-1]["24_slots_latest_known_source"]
        self.assertEqual(d["USD.growth"]["canonical_frequency"], "Q")
        self.assertIsNone(d["USD.growth"]["canonical_series_id"])
        self.assertEqual(d["EUR.inflation"]["canonical_frequency"], "M")
        self.assertEqual(d["AUD.inflation"]["canonical_frequency"], "Q")
        self.assertEqual(d["AUD.inflation"]["reference_period"], "2026-06")
        self.assertTrue(d["AUD.inflation"]["is_canonical_quarterly_AUD_not_monthly"])
        self.assertNotEqual(d["USD.growth"]["reference_period"],
                            d["EUR.inflation"]["reference_period"])

    def test_boundary_monthly_abs_release_uses_first_known_quarter_not_monthly(self):
        july = replay(start="2026-07-28", end="2026-07-30")
        by_day = {x["as_of_day_utc"]: x for x in july["daily_evidence_snapshots"]}
        a = by_day["2026-07-28"]["24_slots_latest_known_source"]["AUD.inflation"]
        b = by_day["2026-07-29"]["24_slots_latest_known_source"]["AUD.inflation"]
        self.assertEqual(a["reference_period"], "2026-03")
        self.assertEqual(b["reference_period"], "2026-06")
        self.assertEqual(b["first_web_value"], 3.9)
        self.assertTrue(b["is_canonical_quarterly_AUD_not_monthly"])

    def test_dossier_event_log_does_not_promote_prices_or_fx_causes(self):
        events = self.month["official_candidate_and_archived_release_gates"]
        self.assertGreater(len(events), 0)
        self.assertTrue(all(e["model_event"] is False for e in events))
        self.assertTrue(all(
            datetime.fromisoformat(e["publisher_gate_utc"]).tzinfo is not None
            for e in events))
        self.assertTrue(self.month["source_event_attestations_not_complete_revision_history"])
        self.assertFalse(self.month["original_publication_day_source_bytes_independently_certified"])
        self.assertTrue(self.month["carry_forward_is_only_LAST_KNOWN_RELEASE_not_economic_estimation"])

    def test_no_full_day_for_today_and_no_long_or_reversed_horizons(self):
        today = datetime.now(timezone.utc).date().isoformat()
        for start, end in (
            ("2026-10-20", today),
            ("2026-07-01", "2027-07-01"),
            ("2026-10-21", "2026-10-20"),
            ("2026-01-01", "2026-10-26"),
        ):
            with self.subTest(start=start,end=end), self.assertRaises(ValueError):
                replay(start=start, end=end)

    def test_no_mutations_to_original_core_or_currency_pairs(self):
        folder = ROOT / "live_data/sections"
        names = ["D.json", "PAIR_SETUP_OPERATIONAL_VIEW.json"]
        before = {n: (folder / n).read_bytes() for n in names}
        x = replay(start="2026-10-25", end="2026-10-26")
        after = {n: (folder / n).read_bytes() for n in names}
        self.assertEqual(before, after)
        self.assertEqual(x["summary"]["model_macro_scores_approved"], 0)
        self.assertFalse(x["safe_to_publish_new_D"])


if __name__ == "__main__":
    unittest.main()
