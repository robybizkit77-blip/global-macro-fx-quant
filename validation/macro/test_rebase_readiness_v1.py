#!/usr/bin/env python3
"""Fail-closed tests against real canonical G8 source fixtures (no network)."""
import copy
import json
import unittest
from datetime import date

from validation.macro.rebase_readiness_v1 import ROOT, PATHS, g8_coverage


def load():
    return {
        key: json.loads((ROOT / path).read_text(encoding="utf-8"))
        for key, path in PATHS.items()
    }


class RebaseReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load()
        cls.today = date(2026, 10, 20)

    def run_audit(self, **overrides):
        d = dict(self.inputs)
        d.update(overrides)
        return g8_coverage(*(d[k] for k in PATHS), self.today)

    def test_full_g8_source_lineage_but_no_score_promotion(self):
        out = self.run_audit()
        self.assertEqual(out["source_lineage"], "PASS")
        self.assertEqual(out["structural_rebase"], "BLOCKED_SCORE_CONTRACT")
        self.assertIs(out["safe_to_publish_D"], False)
        self.assertIs(out["safe_to_update_structural_pair_preferences"], False)
        self.assertEqual(out["registered_macro_series"], 16)
        self.assertEqual(out["tracked_currencies"], 8)
        self.assertEqual(out["tracked_pairs"], 28)
        self.assertGreaterEqual(out["growth_sources_inventoried"], 8)
        for c in out["currencies"].values():
            self.assertIsNone(c["proposed_scores"])
            self.assertIsNone(c["inflation"]["release_timestamp"])
            self.assertIsNone(c["labour"]["release_timestamp"])
        for p in out["pairs"].values():
            self.assertIsNone(p["certified_delta"])
            self.assertEqual(p["status"], "WITHHELD_UNTIL_VERSIONED_SCORE_REBASE")

    def test_heat_series_id_mismatch_rejected(self):
        h = copy.deepcopy(self.inputs["heat"])
        h["currencies"]["EUR"]["labour"]["series_id"] = "FAKE_UNEMP"
        with self.assertRaisesRegex(ValueError, "live heatmap does not match"):
            self.run_audit(heat=h)

    def test_observation_month_mismatch_rejected(self):
        h = copy.deepcopy(self.inputs["heat"])
        h["currencies"]["CAD"]["inflation"]["as_of"] = "2026-08"
        with self.assertRaisesRegex(ValueError, "observation date mismatch"):
            self.run_audit(heat=h)

    def test_future_observation_rejected(self):
        s = copy.deepcopy(self.inputs["series"])
        target = next(x for x in s["USD"] if x["id"] == "US_UNRATE_history_value")
        target["dates"][-1] = "2026-11-01"
        h = copy.deepcopy(self.inputs["heat"])
        h["currencies"]["USD"]["labour"]["as_of"] = "2026-11-01"
        with self.assertRaisesRegex(ValueError, "future observation"):
            self.run_audit(series=s, heat=h)

    def test_unready_source_adapter_rejected(self):
        r = copy.deepcopy(self.inputs["registry"])
        r["series"]["CHF.labour"]["source_adapter_status"] = "WITHHELD"
        with self.assertRaisesRegex(ValueError, "not READY"):
            self.run_audit(registry=r)

    def test_missing_macro_growth_source_rejected(self):
        s = copy.deepcopy(self.inputs["series"])
        s["GBP"] = [x for x in s["GBP"] if x.get("category") != "Crescita"]
        with self.assertRaisesRegex(ValueError, "no dated Growth source"):
            self.run_audit(series=s)

    def test_pair_duplicate_rejected(self):
        p = copy.deepcopy(self.inputs["pair_setup"])
        # Replace an unrelated pair with the reverse of an existing key.
        self.assertIn("EURUSD", p["pairs"])
        p["pairs"].pop("AUDCAD")
        p["pairs"]["USDEUR"] = copy.deepcopy(p["pairs"]["EURUSD"])
        p["pairs"]["USDEUR"]["canonical_pair"] = "USD/EUR"
        with self.assertRaisesRegex(ValueError, "duplicated or invalid pair"):
            self.run_audit(pair_setup=p)

    def test_macro_date_mismatch_rejected(self):
        p = copy.deepcopy(self.inputs["pair_setup"])
        p["macro_baseline_asof"] = "2026-10-19"
        with self.assertRaisesRegex(ValueError, "Macro provenance inconsistent"):
            self.run_audit(pair_setup=p)

    def test_no_rate_or_estimated_pricing_promotion(self):
        out = self.run_audit()
        self.assertEqual(out["currencies"]["CHF"]["rates_2y_10y"]["status"], "WITHHELD")
        self.assertEqual(out["currencies"]["NZD"]["policy_pricing"]["status"], "NO_OFFICIAL_REPRICING")
        self.assertIs(out["currencies"]["USD"]["policy_pricing"]["official_current"], False)
        self.assertIs(out["currencies"]["EUR"]["policy_pricing"]["official_current"], False)


if __name__ == "__main__":
    unittest.main()
