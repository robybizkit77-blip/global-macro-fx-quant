#!/usr/bin/env python3
"""Negative and positive contract checks for pair coverage; no network."""
import copy
import itertools
import unittest
from datetime import date

from validation.audit_control_room_pair_coverage_v1 import FX, analyze


def fixture():
    day = "2026-10-19"
    pairs = {
        a + b: {
            "canonical_pair": a + "/" + b,
            "setup": {"quality": "DA MONITORARE"},
            "decision_frame": {"macroSide": None, "policySide": None},
        }
        for a, b in itertools.combinations(FX, 2)
    }
    return {
        "setup": {
            "schema": "GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1",
            "status": "CURRENT_CANONICAL_ENGINE",
            "pair_count": 28,
            "price_asof": day,
            "macro_baseline_asof": day,
            "price_audit": {"status": "PASS", "as_of": day,
                            "no_lookahead": True, "complete_return_values": 140},
            "thesis_is_not_entry": True,
            "entry_level_published": False,
            "pairs": pairs,
        },
        "history": {
            "schema": "GMFQ_ECB_G8_PRICE_HISTORY_V1",
            "status": "CURRENT_OFFICIAL_HISTORY",
            "pair_count": 28, "last_as_of": day,
            "rows": [{"Date": day}],
        },
        "rates": {c: {"date": day, "quality": "FULL_CURRENT_OFFICIAL",
                       "2Y": 2.0, "10Y": 3.0} for c in FX},
        "ois": {"currencies": {c: {
            "as_of": day, "operational_status": "GREEN_OFFICIAL",
            "quality": "OFFICIAL_CERTIFIED", "official_status": "ACTIVE",
            "horizons": {"6m": {"policy_delta_bp": 0.0}},
        } for c in FX}},
        "cot": {c: {"dates": ["2026-10-06", "2026-10-13"],
                    "net": [0, 1]} for c in FX},
        "model": {"asOf": day},
    }


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()
        self.today = date(2026, 10, 20)

    def test_complete_when_all_sources_current(self):
        r = analyze(self.data, self.today)
        self.assertEqual(r["integrity"], "PASS")
        self.assertEqual(r["coverage"], "COMPLETE")
        self.assertEqual(r["fully_supported_pairs"], 28)

    def test_stale_macro_fails_closed_without_model_changes(self):
        self.data["model"]["asOf"] = "2026-09-25"
        r = analyze(self.data, self.today)
        self.assertEqual(r["coverage"], "PARTIAL")
        self.assertEqual(r["fully_supported_pairs"], 0)
        self.assertIn("MACRO_BASELINE_STALE", r["pairs"]["USDEUR"]["gaps"])

    def test_chf_rate_staleness_and_estimate_are_not_official(self):
        self.data["rates"]["CHF"]["date"] = "2026-09-30"
        self.data["ois"]["currencies"]["CHF"].update(
            operational_status="GREEN_ESTIMATED", quality="ESTIMATED_INFORMATIONAL",
            official_status="WITHHELD")
        r = analyze(self.data, self.today)
        self.assertEqual(r["coverage"], "PARTIAL")
        self.assertEqual(r["fully_supported_pairs"], 21)
        self.assertIn("CHF_RATES_WITHHELD", r["pairs"]["NZDCHF"]["gaps"])
        self.assertIn("CHF_OIS_NOT_OFFICIAL_CURRENT", r["pairs"]["NZDCHF"]["gaps"])

    def test_fake_official_ois_is_rejected(self):
        self.data["ois"]["currencies"]["USD"]["quality"] = "ESTIMATED_INFORMATIONAL"
        with self.assertRaisesRegex(ValueError, "falsely promoted"):
            analyze(self.data, self.today)

    def test_reverse_duplicate_detected_even_with_28_keys(self):
        self.data["setup"]["pairs"].pop("USDGBP")
        self.data["setup"]["pairs"]["EURUSD"] = {
            "canonical_pair": "EUR/USD", "setup": {}, "decision_frame": {}}
        with self.assertRaisesRegex(ValueError, "reverse-duplicated"):
            analyze(self.data, self.today)

    def test_future_cot_is_rejected(self):
        self.data["cot"]["JPY"]["dates"][-1] = "2026-10-21"
        with self.assertRaisesRegex(ValueError, "future observation"):
            analyze(self.data, self.today)

    def test_model_macro_provenance_mismatch_fails_closed(self):
        self.data["setup"]["macro_baseline_asof"] = "2026-09-25"
        with self.assertRaisesRegex(ValueError, "Macro baseline as-of"):
            analyze(self.data, self.today)

    def test_price_history_cannot_lag_model_price(self):
        self.data["history"]["last_as_of"] = "2026-10-16"
        self.data["history"]["rows"][-1]["Date"] = "2026-10-16"
        with self.assertRaisesRegex(ValueError, "ahead of the official ECB"):
            analyze(self.data, self.today)


if __name__ == "__main__":
    unittest.main()
