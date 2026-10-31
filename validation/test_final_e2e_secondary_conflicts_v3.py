#!/usr/bin/env python3
"""Final E2E: secondary disagreement is never a new official OIS state."""
import copy
import json
import unittest
from pathlib import Path

from validation.run_final_e2e_certification_gate_v3 import (
    certify_secondary_source_state,
)

PATH = Path("live_data/sections/CB_PRICING_ESTIMATED.json")


class SourceQualityFinalE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = PATH.read_bytes()
        cls.currencies = json.loads(cls.raw)["currencies"]

    @classmethod
    def tearDownClass(cls):
        assert PATH.read_bytes() == cls.raw, "final E2E tests altered live source"

    def test_all_three_current_source_states_are_explicit(self):
        for c in ("USD", "EUR", "CHF"):
            grade = certify_secondary_source_state(c, self.currencies[c])
            self.assertIn(grade, (
                "INDEPENDENTLY_TIMESTAMPED_SECONDARY_NOT_OIS",
                "SOURCE_CONFLICT_ANNOTATED_NO_REPRICING",
            ))
            if self.currencies[c]["input_mode"] == "LIVE_SECONDARY_CONFLICT_INDICATIVE":
                self.assertEqual(grade, "SOURCE_CONFLICT_ANNOTATED_NO_REPRICING")

    def modify(self, c="EUR"):
        return copy.deepcopy(self.currencies[c])

    def test_no_policy_or_model_promotion_on_unresolved_conflict(self):
        for modifier in (
            lambda x: x["horizons"]["6m"].__setitem__("policy_delta_bp", 12),
            lambda x: x.__setitem__("change_1d_bp", 5),
            lambda x: x.__setitem__("change_1w_bp", -4),
            lambda x: x.__setitem__("direction_vs_policy", "UP"),
            lambda x: x["governance"].__setitem__("core_score_effect", "LONG"),
            lambda x: x["governance"].__setitem__("pair_engine_effect", "TRADE"),
            lambda x: x["governance"].__setitem__("backtest_eligible_as_official_ois", True),
        ):
            with self.subTest(modifier=str(modifier)):
                row = self.modify()
                modifier(row)
                with self.assertRaises(ValueError):
                    certify_secondary_source_state("EUR", row)

    def test_identity_and_raw_bar_consistency_required(self):
        for modifier in (
            lambda x: x["source_conflict_keys"].clear(),
            lambda x: x["source_conflict_keys"][0].__setitem__("event_id", "forged"),
            lambda x: x["source_conflict_keys"][0].__setitem__("contract", "NOPE"),
            lambda x: x["source_conflict_keys"][0].__setitem__("horizon", "18m"),
            lambda x: x["horizons"]["12m"].__setitem__("quote_timestamp_verified", True),
            lambda x: x["horizons"]["12m"].__setitem__("quote_timestamp_source", "SSR_DAILY_BAR_DATA_UPDATE_TIME"),
        ):
            with self.subTest(modifier=str(modifier)):
                row = self.modify()
                modifier(row)
                with self.assertRaises(ValueError):
                    certify_secondary_source_state("EUR", row)

    def test_conflict_mode_requires_conflict_grade_and_keys(self):
        row = self.modify()
        row["source_quality"] = "OFFICIAL_CERTIFIED"
        with self.assertRaises(ValueError):
            certify_secondary_source_state("EUR", row)
        row = self.modify()
        row["input_mode"] = "LIVE_SECONDARY_OVERLAY"
        with self.assertRaises(ValueError):
            certify_secondary_source_state("EUR", row)

    def test_genuine_clean_grade_remains_independent_of_quarantine(self):
        row = self.modify()
        row["input_mode"] = "LIVE_SECONDARY_OVERLAY"
        row.pop("source_conflict_status", None)
        row.pop("source_conflict_keys", None)
        row["source_quality"] = "SECONDARY_PUBLIC_LIVE_PROXY"
        for p in row["horizons"].values():
            p["quote_timestamp_verified"] = True
            p["quote_timestamp_source"] = "SSR_DAILY_BAR_DATA_UPDATE_TIME"
        self.assertEqual(certify_secondary_source_state("EUR", row),
                         "INDEPENDENTLY_TIMESTAMPED_SECONDARY_NOT_OIS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
