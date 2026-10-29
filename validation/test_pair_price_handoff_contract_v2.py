#!/usr/bin/env python3
"""Pure deterministic contract tests: auto-price overlay cannot update Macro score."""
import copy
import itertools
import unittest
from datetime import date
from pathlib import Path

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
    def test_workflow_preserves_queued_recovery_and_post_dxy_retry(self):
        flow = (Path(__file__).resolve().parents[1] /
                ".github/workflows/pair-setup-operational-view-v1.yml").read_text(encoding="utf-8")
        block = flow.split("  workflow_run:", 1)[1].split("  workflow_dispatch:", 1)[0]
        for source in (
            "Price History Persistent Daily V1",
            "Macro Persistent Daily V1",
            "Price Persistent Daily V1",
            "DXY Synthetic ECB Research V1",
        ):
            self.assertEqual(block.count(f"      - '{source}'"), 1)
        self.assertIn("types: [completed]", block)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", flow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", flow)
        self.assertIn("queue: max", flow)
        self.assertIn("cancel-in-progress: false", flow)
        self.assertIn("pair-validation-pr-{0}", flow)
        self.assertIn("Main moved since validation. Safe retry required.", flow)
        self.assertIn("Main moved during Pair persistence. Safe retry required.", flow)
        self.assertIn("steps.handoff.outputs.status == 'PRICE_CONTEXT_UPDATE'", flow)
        self.assertEqual(flow.count("    - cron:"), 1)

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

    def test_official_overlay_ahead_of_separate_ecb_history_waits_without_write(self):
        # A verified current overlay can lead the official historical archive.
        # Its date is not certification of an independently persisted archive.
        self.candidate["price_asof"] = "2026-10-20"
        self.candidate["price_audit"]["as_of"] = "2026-10-20"
        self.today = date(2026, 10, 20)
        row = classify(self.candidate, self.prior, self.d, self.ecb, self.today)
        self.assertEqual(row["status"], "WAITING_FOR_ECB_HISTORY_SAME_DAY")
        self.assertEqual(row["action"], "NO_WRITE")
        self.assertFalse(row["ready_for_forward_v2"])
        self.assertEqual(row["candidate_price_asof"], "2026-10-20")
        self.assertEqual(row["official_history_asof"], "2026-10-19")
        # The SAME candidate becomes eligible only after the official
        # independent history catches up, with no model refresh.
        self.ecb["last_as_of"] = "2026-10-20"
        self.ecb["rows"][-1]["Date"] = "2026-10-20"
        row = classify(self.candidate, self.prior, self.d, self.ecb, self.today)
        self.assertEqual(row["status"], "PRICE_CONTEXT_UPDATE")
        self.assertEqual(row["action"], "ELIGIBLE_FOR_PERSISTENCE")

    def test_mismatched_older_candidate_still_rejected(self):
        self.candidate["price_asof"] = "2026-10-18"
        self.candidate["price_audit"]["as_of"] = "2026-10-18"
        with self.assertRaisesRegex(ValueError, "candidate Price must match"):
            classify(self.candidate, self.prior, self.d, self.ecb, self.today)

    def test_wait_state_never_approves_changed_macro_or_future_price(self):
        self.candidate["price_asof"] = "2026-10-20"
        self.candidate["price_audit"]["as_of"] = "2026-10-20"
        self.d["asOf"] = "2026-10-01"
        with self.assertRaisesRegex(ValueError, "provenance differs"):
            classify(self.candidate, self.prior, self.d, self.ecb, self.today)
        self.d["asOf"] = "2026-09-25"
        self.candidate["price_asof"] = "2026-10-21"
        self.candidate["price_audit"]["as_of"] = "2026-10-21"
        with self.assertRaisesRegex(ValueError, "future"):
            classify(self.candidate, self.prior, self.d, self.ecb, self.today)

    def test_fake_entry_flag_rejected(self):
        self.candidate["entry_level_published"] = True
        with self.assertRaisesRegex(ValueError, "no-entry semantics"):
            classify(self.candidate, self.prior, self.d, self.ecb, self.today)

    def test_reversed_pair_duplicate_rejected(self):
        self.candidate["pairs"].pop("USDGBP")
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
