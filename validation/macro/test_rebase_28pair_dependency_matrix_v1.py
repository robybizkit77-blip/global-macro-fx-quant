#!/usr/bin/env python3
"""Regression and adversarial tests of the current non-promotional G8 rebase grid."""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from validation.macro.rebase_joint_gate_v1 import run as joint_run
from validation.macro.score_formula_provenance_v1 import run as score_run
from validation.macro.rebase_28pair_dependency_matrix_v1 import (
    CCYS, GATES, ROOT, build, run,
)
from datetime import date

ASOF = "2026-10-31"
PATHS = [
    "live_data/sections/D.json",
    "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
    "live_data/sections/NATIVE_RATES_DATA.json",
    "live_data/sections/OIS_OPERATIONAL_VIEW.json",
]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class MacroCurrent28PairRebaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                      for p in PATHS}
        cls.gate = joint_run(root=ROOT, today=date.fromisoformat(ASOF))
        cls.score = score_run(root=ROOT, today=date.fromisoformat(ASOF))
        cls.model, cls.setup, cls.rates, cls.ois = [read(x) for x in PATHS]

    @classmethod
    def tearDownClass(cls):
        cls.after = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                     for p in PATHS}
        assert cls.before == cls.after, "read-only audit modified production data"

    def case(self, *, gate=None, score=None, model=None, setup=None,
             rates=None, ois=None):
        return build(
            copy.deepcopy(self.gate if gate is None else gate),
            copy.deepcopy(self.score if score is None else score),
            copy.deepcopy(self.model if model is None else model),
            copy.deepcopy(self.setup if setup is None else setup),
            copy.deepcopy(self.rates if rates is None else rates),
            copy.deepcopy(self.ois if ois is None else ois),
        )

    def test_exact_g8_28_pairs_with_no_model_promotions(self):
        output = self.case()
        self.assertEqual(output, run(as_of=ASOF))
        self.assertEqual(output["historical_macro_baseline_as_of"], "2026-09-25")
        self.assertEqual(output["latest_ecb_price_as_of"], "2026-10-30")
        self.assertEqual(output["summary"]["macro_axes_historical"], 24)
        self.assertEqual(output["summary"]["latest_labour_inflation_source_rows"], 16)
        self.assertEqual(output["summary"]["pairs"], 28)
        self.assertEqual(set(output["countries"]), set(CCYS))
        self.assertEqual(set(output["pairs"]), set(self.setup["pairs"]))
        self.assertFalse(output["safe_to_publish_D_json"])
        self.assertFalse(output["safe_to_update_28_pairs"])
        self.assertFalse(output["safe_for_forward"])
        self.assertFalse(output["safe_for_beta"])
        self.assertIsNone(output["candidate_D_json"])
        self.assertEqual(output["summary"]["pairs_allowed_to_rebase_structural"], 0)
        self.assertTrue(all(
            pair["global_model_blockers"] == list(GATES)
            and pair["eligible_to_recalculate_structural_fx_thesis"] is False
            and pair["candidate_favored"] is None
            and pair["candidate_policy_side"] is None
            and pair["candidate_macro_side"] is None
            for pair in output["pairs"].values()
        ))
        self.assertEqual(
            output["summary"]["pairs_full_same_day_2y_ois_6m"],
            sum(p["full_same_day_2y_and_ois_6m_both_legs"]
                for p in output["pairs"].values()),
        )

    def test_frozen_score_scalar_change_rejected(self):
        legacy = copy.deepcopy(self.model)
        legacy["macro"]["USD"]["growth"] += 0.001
        with self.assertRaisesRegex(ValueError, "frozen scores"):
            self.case(model=legacy)

    def test_frozen_cycle_change_rejected(self):
        legacy = copy.deepcopy(self.model)
        legacy["macro"]["CAD"]["cycle"] = "FAKE_REFLATION"
        with self.assertRaisesRegex(ValueError, "frozen scores"):
            self.case(model=legacy)

    def test_unapproved_source_grade_rejected(self):
        gate = copy.deepcopy(self.gate)
        gate["release_grades"]["FULL_RELEASE_INSTANT"] += 1
        with self.assertRaisesRegex(ValueError, "16 released"):
            self.case(gate=gate)

    def test_fake_rebase_permission_rejected(self):
        gate = copy.deepcopy(self.gate)
        gate["safe_to_publish_new_D"] = True
        with self.assertRaisesRegex(ValueError, "upstream joint PIT"):
            self.case(gate=gate)

    def test_wrong_price_vintage_rejected(self):
        setup = copy.deepcopy(self.setup)
        setup["price_asof"] = "2026-10-29"
        with self.assertRaisesRegex(ValueError, "price layer"):
            self.case(setup=setup)

    def test_missing_ois_currency_rejected(self):
        ois = copy.deepcopy(self.ois)
        del ois["currencies"]["USD"]
        with self.assertRaisesRegex(ValueError, "G8 source"):
            self.case(ois=ois)

    def test_duplicate_reversed_pair_rejected(self):
        setup = copy.deepcopy(self.setup)
        key = next(iter(setup["pairs"]))
        reversed_key = key[3:] + key[:3]
        # Keep exactly 28 records so the test reaches the inverted identity check.
        remove = next(k for k in setup["pairs"] if k != key and k != reversed_key)
        setup["pairs"].pop(remove)
        item = copy.deepcopy(setup["pairs"][key])
        item["canonical_pair"] = reversed_key[:3] + "/" + reversed_key[3:]
        setup["pairs"][reversed_key] = item
        with self.assertRaisesRegex(ValueError, "duplicate inverted"):
            self.case(setup=setup)

    def test_future_source_asof_rejected(self):
        rates = copy.deepcopy(self.rates)
        rates["EUR"]["date"] = "2026-11-02"
        with self.assertRaisesRegex(ValueError, "future observation"):
            self.case(rates=rates)

    def test_secondary_estimates_do_not_become_ois_or_fx_scores(self):
        out = self.case()
        for c in CCYS:
            op = self.ois["currencies"][c]
            derived = out["countries"][c]
            if op["operational_status"] == "GREEN_ESTIMATED":
                self.assertFalse(derived["official_monetary_6m_recent"])
                self.assertTrue(derived["indicative_monetary_6m_visible"])
            self.assertIsNone(derived["new_fx_currency_strength"])
            self.assertIsNone(derived["new_legacy_compatible_macro_score"])
            self.assertFalse(derived["historical_source_vintages_approved"])

    def test_altered_formula_certificate_rejected(self):
        score = copy.deepcopy(self.score)
        score["ready_for_numeric_macro_rebase"] = True
        with self.assertRaisesRegex(ValueError, "score provenance"):
            self.case(score=score)


if __name__ == "__main__":
    unittest.main(verbosity=2)
