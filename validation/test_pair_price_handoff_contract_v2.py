#!/usr/bin/env python3
"""Pure deterministic contract tests: auto-price overlay cannot update Macro score."""
import copy
import itertools
import unittest
from datetime import date

from validation.pair_price_handoff_contract_v2 import FX, classify


def fixtures():
    pairs = {}
    for a, b in itertools.combinations(FX, 2):
        pairs[a+b] = {
            "canonical_pair": f"{a}/{b}",
            "setup": {"structuralFav": a, "quality": "DA MONITORARE"},
            "decision_frame": {"macroSide": a, "policySide": None},
            "transition": {}, "relative_dynamics": {},
        }
    base = {
        "schema": "GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1",
        "status": "CURRENT_CANONICAL_ENGINE",
        "pair_count": 28,
        "thesis_is_not_entry": True,
        "entry_level_published": False,
        "price_asof": "2026-10-16",
        "macro_baseline_asof": "2026-09-25",
        "price_audit": {
            "status": "PASS", "no_lookahead": True, "returns_complete": True,
            "complete_return_values": 140, "as_of": "2026-10-16", "pair_count": 28,
        },
        "pairs": pairs,
    }
    return base, {"asOf": "2026-09-25"}, {
        "schema": "GMFQ_ECB_G8_PRICE_HISTORY_V1",
        "status": "CURRENT_OFFICIAL_HISTORY",
        "pair_count": 28, "last_as_of": "2026-10-19",
        "rows": [{"Date": "2026-10-19"}],
    }


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.prior, self.d, self.ecb = fixtures()
        self.candidate = copy.deepcopy(self.prior)
        self.candidate["price_asof"] = "2026-10-19"
        self.candidate["price_audit"]["as_of"] = "2026-10-19"
        self.today = date(2026, 10, 20)

    def test_only_price_refresh_is_eligible(self):
        self.candidate["pairs"]["USDEUR"]["setup"]["quality"] = "CON RISCHI"
        row = classify(self.candidate, self.prior, self.d, self.ecb, self.today)
        self.assertEqual(row["status"], "PRICE_CONTEXT_UPDATE")
        self.assertEqual(row["macro_asof"], "2026-09-25")
        self.assertIs(row["macro_current"], False)
        self.assertIs(row["structural_preferences_preserved"], True)

    def test_same_snapshot_no_change(self):
        self.ecb["last_as_of"] = "2026-10-16"
        self.ecb["rows"][-1]["Date"] = "2026-10-16"
        self.candidate = copy.deepcopy(self.prior)
        self.assertEqual(classify(self.candidate, self.prior, self.d, self.ecb,
                                  self.today)["status"], "NO_CHANGE")

    def test_structural_bias_cannot_change_from_new_fx_fixing(self):
        self.candidate["pairs"]["USDEUR"]["setup"]["structuralFav"] = "EUR"
        with self.assertRaisesRegex(ValueError, "structuralFav changed"):
            classify(self.candidate, self.prior, self.d, self.ecb, self.today)

    def test_new_macro_baseline_must_be_certified_separately(self):
        self.d["asOf"] = "2026-10-19"
        self.candidate["macro_baseline_asof"] = "2026-10-19"
        row = classify(self.candidate, self.prior, self.d, self.ecb, self.today)
        self.assertEqual(row["status"], "BLOCKED_MACRO_REBASE")
        self.assertEqual(row["action"], "NO_WRITE")

    def test_future_ecb_is_rejected(self):
        self.ecb["last_as_of"] = "2026-10-21"
        self.ecb["rows"][-1]["Date"] = "2026-10-21"
        with self.assertRaisesRegex(ValueError, "future"):
            classify(self.candidate, self.prior, self.d, self.ecb, self.today)

    def test_data_asof_discrepancy_fails_closed(self):
        self.candidate["price_asof"] = "2026-10-18"
        self.candidate["price_audit"]["as_of"] = "2026-10-18"
        with self.assertRaisesRegex(ValueError, "candidate Price must match"):
            classify(self.candidate, self.prior, self.d, self.ecb, self.today)

    def test_fake_entry_flag_rejected(self):
        self.candidate["entry_level_published"] = True
        with self.assertRaisesRegex(ValueError, "no-entry semantics"):
            classify(self.candidate, self.prior, self.d, self.ecb, self.today)

    def test_reversed_pair_duplicate_rejected(self):
        self.candidate["pairs"].pop("USDEUR")
        self.candidate["pairs"]["EURUSD"] = {
            "canonical_pair": "EUR/USD", "setup": {"structuralFav": "EUR"},
            "decision_frame": {}, "transition": {}, "relative_dynamics": {},
        }
        with self.assertRaisesRegex(ValueError, "duplicate/unknown"):
            classify(self.candidate, self.prior, self.d, self.ecb, self.today)

    def test_old_price_snapshot_rejected(self):
        self.candidate["price_asof"] = "2026-10-15"
        self.candidate["price_audit"]["as_of"] = "2026-10-15"
        with self.assertRaisesRegex(ValueError, "candidate Price must match"):
            classify(self.candidate, self.prior, self.d, self.ecb, self.today)


if __name__ == "__main__":
    unittest.main()
