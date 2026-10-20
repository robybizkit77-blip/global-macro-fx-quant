#!/usr/bin/env python3
"""Negative tests for score provenance. Do not certify unversioned Macro numbers."""
from __future__ import annotations

import copy
import json
import unittest
from datetime import date

from validation.macro.score_formula_provenance_v1 import (
    ROOT, PARTS, inspect, run,
)

AUDIT_DATE = date(2026, 10, 20)


class ScoreProvenanceBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        read = lambda p: (ROOT / p).read_text(encoding="utf-8")
        cls.model = json.loads(read("live_data/sections/D.json"))
        cls.setup = json.loads(read("live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json"))
        cls.parts = {kind: read(path) for kind, path in PARTS.items()}

    def audit(self, model=None, setup=None, parts=None):
        return inspect(copy.deepcopy(self.model if model is None else model),
                       copy.deepcopy(self.setup if setup is None else setup),
                       copy.deepcopy(self.parts if parts is None else parts), AUDIT_DATE)

    def test_current_historical_numeric_scores_and_pair_rules_are_separate(self):
        out = self.audit()
        self.assertEqual(out["historical_scalar_scores"], 24)
        self.assertEqual(out["historical_regimes"], 8)
        self.assertEqual(out["pairs_in_source_snapshot"], 28)
        self.assertEqual(out["model_as_of"], "2026-09-25")
        self.assertEqual(out["price_as_of"], "2026-10-20")
        self.assertEqual(out["certified_semantics"]["macroSimpleScore"],
                         "DISPLAY_LABELS_FROM_ALREADY_STORED_NUMBER")
        self.assertEqual(out["certified_semantics"]["derivePairDecisionFrame"],
                         "STRUCTURAL_DIRECTION_FROM_TWO_CURRENCY_VOTES_AND_EMBEDDED_2Y")
        self.assertEqual(len(out["runtime_function_sha256"]), 6)
        self.assertEqual(len(out["source_files_sha256"]), 3)
        self.assertFalse(out["ready_for_numeric_macro_rebase"])
        self.assertFalse(out["safe_to_publish_new_D"])
        self.assertFalse(out["safe_to_update_28_pair_theses"])
        self.assertFalse(out["writes_live_data"])

    def test_finite_but_unauthorized_historical_score_change_is_rejected(self):
        model = copy.deepcopy(self.model)
        model["macro"]["USD"]["growth"] = 0.14
        with self.assertRaisesRegex(ValueError, "frozen historical score or cycle"):
            self.audit(model=model)

    def test_recognized_but_unauthorized_historical_cycle_change_is_rejected(self):
        model = copy.deepcopy(self.model)
        model["macro"]["AUD"]["cycle"] = "GOLDILOCKS"
        with self.assertRaisesRegex(ValueError, "frozen historical score or cycle"):
            self.audit(model=model)

    def test_historical_snapshot_provenance_is_explicit(self):
        out = self.audit()
        self.assertTrue(out["historical_values_locked_to_first_repo_snapshot"])
        self.assertEqual(out["historical_snapshot_commit"],
                         "529acdd6026c88ecee8451e2e5bc36c740eece7d")

    def test_pillar_value_missing_or_nonfinite_is_rejected(self):
        for v in (None, True, float("nan"), float("inf")):
            with self.subTest(value=repr(v)):
                model = copy.deepcopy(self.model)
                model["macro"]["USD"]["inflation"] = v
                with self.assertRaisesRegex(ValueError, "historical numeric score malformed"):
                    self.audit(model=model)

    def test_changing_cycle_vintage_or_snapshot_is_rejected(self):
        model = copy.deepcopy(self.model)
        model["macro"]["CHF"]["cycle"] = "INVENTED_CYCLE"
        with self.assertRaisesRegex(ValueError, "unrecognized historical regime"):
            self.audit(model=model)
        setup = copy.deepcopy(self.setup)
        setup["macro_baseline_asof"] = setup["price_asof"]
        with self.assertRaisesRegex(ValueError, "not identical"):
            self.audit(setup=setup)
        setup = copy.deepcopy(self.setup)
        setup["price_asof"] = "2026-10-21"
        with self.assertRaisesRegex(ValueError, "future baseline"):
            self.audit(setup=setup)

    def test_qualitative_direction_cannot_replace_numeric_score_lineage(self):
        parts = dict(self.parts)
        parts["structural_currency"] = parts["structural_currency"].replace(
            "layerPolarity(d.macro)", "Number(D.macro?.[c]?.growth)", 1)
        with self.assertRaisesRegex(ValueError, "structural directional labels changed"):
            self.audit(parts=parts)

    def test_presentation_thresholds_cannot_claim_economic_weights(self):
        parts = dict(self.parts)
        parts["display"] = parts["display"].replace(
            "return 'forte'", "return 'CERTIFIED_NUMERIC_SCORE'", 1)
        with self.assertRaisesRegex(ValueError, "visual score interpretation has changed"):
            self.audit(parts=parts)

    def test_pair_currency_composition_and_trade_sep_fail_closed(self):
        setup = copy.deepcopy(self.setup)
        key = next(iter(setup["pairs"]))
        setup["pairs"][key]["canonical_pair"] = "WRONG/KEY"
        with self.assertRaisesRegex(ValueError, "canonical key mismatch"):
            self.audit(setup=setup)
        setup = copy.deepcopy(self.setup)
        setup["entry_level_published"] = True
        with self.assertRaisesRegex(ValueError, "thesis / trade"):
            self.audit(setup=setup)

    def test_stale_baseline_is_mandatory_for_this_evidence(self):
        with self.assertRaisesRegex(ValueError, "no longer stale"):
            self.audit(model={**self.model, "asOf": "2026-10-20"},
                       setup={**self.setup, "macro_baseline_asof": "2026-10-20"})

    def test_read_only_run_has_no_runtime_mutations(self):
        result = run(today=AUDIT_DATE)
        self.assertFalse(result["writes_live_data"])
        self.assertFalse(result["safe_to_publish_new_D"])


if __name__ == "__main__":
    unittest.main()
