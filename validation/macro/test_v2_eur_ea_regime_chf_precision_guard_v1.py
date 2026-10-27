"""Falsification and exact publisher as-of tests for EA19/EA20/EA21 and CHF."""
from __future__ import annotations

import copy
import math
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from validation.macro.v2_eur_ea_regime_chf_precision_guard_v1 import (
    SCHEMA, euro_quality, swiss_quality, audit
)
from validation.macro.v2_eur_aud_archival_first_web_overlay_v1 import (
    rows_and_events
)
from validation.macro.v2_shadow_features_v1 import ROOT


class EurozonePopulationAndSwissRounding(unittest.TestCase):
    def test_all_105_first_flash_events_are_assigned_3_real_regimes(self):
        e = euro_quality()
        self.assertEqual(e["regime_counts"], {"EA19": 60, "EA20": 36, "EA21": 9})
        self.assertEqual(e["homogeneous_24_prior_month_windows"], 48)
        self.assertEqual(e["nonhomogeneous_or_insufficient_24m_windows"], 57)
        pairs = {x["reference_month"]: x for x in e["period_quality"]}
        self.assertEqual(pairs["2022-12"]["membership"], "EA19")
        self.assertEqual(pairs["2023-01"]["membership"], "EA20")
        self.assertEqual(pairs["2025-12"]["membership"], "EA20")
        self.assertEqual(pairs["2026-01"]["membership"], "EA21")
        self.assertTrue(pairs["2025-12"]["prior_24_same_membership"])
        self.assertFalse(pairs["2023-01"]["prior_24_same_membership"])
        self.assertFalse(pairs["2026-01"]["prior_24_same_membership"])

    def test_2026_september_ea21_has_only_8_preceding_months(self):
        e = euro_quality(cutoff="2026-10-27T00:00:00Z")
        latest = e["last_visible_first_flash"]
        self.assertEqual(latest["period"], "2026-09")
        self.assertEqual(latest["membership"], "EA21")
        self.assertEqual(latest["prior_visible_same_membership_months"], 8)
        self.assertEqual(latest["value_yoy_pct"], 3.8)
        self.assertFalse(latest["same_membership_24m_reference_sufficient"])
        self.assertIsNone(latest["research_z_homogeneous"])
        self.assertTrue(latest["mixed_membership_24m_reference_must_be_estimate"])

    def test_eur_flash_october_2_not_visible_until_october_3(self):
        previous = euro_quality(cutoff="2026-10-02T23:59:59Z")
        after = euro_quality(cutoff="2026-10-03T00:00:00Z")
        self.assertEqual(previous["last_visible_first_flash"]["period"], "2026-08")
        self.assertEqual(after["last_visible_first_flash"]["period"], "2026-09")
        self.assertEqual(after["last_visible_first_flash"]["first_publisher_gate_utc"],
                         "2026-10-03T00:00:00+00:00")

    def test_chf_rounded_interval_exactness_not_inferred(self):
        s = swiss_quality(cutoff="2026-10-27T00:00:00Z")
        self.assertEqual(s["rounded_SECO_sa_rate_pct_visible"], 3.1)
        self.assertEqual(s["rounding_consistency_interval_pct"],
                         {"lower_inclusive": 3.05, "upper_exclusive": 3.15})
        self.assertTrue(s["rounded_3p1_cannot_prove_an_exact_number"])
        self.assertTrue(s["original_exact_SNB_value_on_official_SECO_release_unverified"])
        self.assertIsNone(s["exact_SNB_release_timestamp_utc"])
        self.assertFalse(s["SNB_exact_historic_release_PIT_approved"])
        self.assertTrue(s["no_imputation_of_exact_SNB_vintage"])

    def test_chf_rate_after_report_is_visible_only_at_next_UTC_date(self):
        a = swiss_quality(cutoff="2026-10-06T23:59:59Z")
        b = swiss_quality(cutoff="2026-10-07T00:00:00Z")
        self.assertIsNone(a["rounded_SECO_sa_rate_pct_visible"])
        self.assertIsNone(a["august_count_revision_visible_only_after_sep_release"])
        self.assertEqual(b["rounded_SECO_sa_rate_pct_visible"], 3.1)
        self.assertEqual(b["august_count_revision_visible_only_after_sep_release"], -84)
        self.assertEqual(b["sep_SA_registered_count"], 147411)
        self.assertEqual(b["august_first_SECO_sa_count"], 147970)
        self.assertEqual(b["seco_august_and_september_rounded_rate_same_despite_revision"], True)

    def test_poisoned_historic_ea_archive_period_is_rejected(self):
        raw = copy.deepcopy(rows_and_events("EUR.inflation"))
        raw["events"][20]["reference_period"] = "2026-07"
        with self.assertRaisesRegex(ValueError, "missing or unordered"):
            euro_quality(source=raw)

    def test_future_EA_month_or_illegal_promotion_refused(self):
        bad = copy.deepcopy(rows_and_events("EUR.inflation"))
        bad["events"][-1]["PIT_history_replay_for_trading_authorized"] = True
        with self.assertRaisesRegex(ValueError, "first-flash EUR archive"):
            euro_quality(source=bad)

    def test_report_read_only_and_no_core_or_pair_rewrite(self):
        root = ROOT / "live_data/sections"
        protected = ["D.json", "PAIR_SETUP_OPERATIONAL_VIEW.json"]
        before = {name: (root / name).read_bytes() for name in protected}
        s = audit(as_of="2026-10-27T00:00:00Z")
        after = {name: (root / name).read_bytes() for name in protected}
        self.assertEqual(before, after)
        self.assertEqual(s["schema"], SCHEMA)
        self.assertFalse(s["summary"]["eur_current_24m_same_membership_reference_sufficient"])
        self.assertEqual(s["summary"]["macro_strength_scores_approved"], 0)
        self.assertEqual(s["summary"]["FX_pair_rankings_changed"], 0)
        for key in ["safe_to_publish_new_D", "safe_to_change_28_pairs",
                    "safe_for_beta", "safe_for_forward", "writes_live_data"]:
            self.assertFalse(s[key])


if __name__ == "__main__":
    unittest.main()
