"""Adversarial current-snapshot source synchronization; 28 FX pairs get NO signal."""
from __future__ import annotations
import copy
import json
import unittest

from validation.macro.v2_domestic_candidate_explicit_formula_v1 import run as domestic_run
from validation.macro.v2_core_quant_falsification_readiness_v1 import (
    ROOT, run as quant_run
)
from validation.macro.v2_fx_28pair_synchronized_evidence_gate_v1 import (
    SCHEMA, SECTION, evaluate, run
)

class Relative28FXSourceSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load=lambda x:json.loads((SECTION/(x+".json")).read_text(encoding="utf-8"))
        cls.kw={
            "domestic":domestic_run(as_of="2026-10-27"),
            "rates":load("NATIVE_RATES_DATA"),
            "ois":load("OIS_OPERATIONAL_VIEW"),
            "readiness":load("OIS_SOURCE_READINESS_VIEW"),
            "cb":load("NATIVE_CB_DATA"),
            "setup":load("PAIR_SETUP_OPERATIONAL_VIEW"),
            "core":load("D"),
            "quant":quant_run(as_of="2026-10-28"),
        }
        cls.result=evaluate(**cls.kw)

    def bad(self,name,modify):
        x=copy.deepcopy(self.kw[name])
        modify(x)
        params=dict(self.kw)
        params[name]=x
        with self.assertRaises(ValueError):
            evaluate(**params)

    def test_28_pairs_exact_and_source_dating_truth(self):
        d=self.result
        s=d["summary"]
        self.assertEqual(d["schema"],SCHEMA)
        self.assertEqual(s["currencies"],8)
        self.assertEqual(s["pairs_total"],28)
        self.assertEqual(len(d["pair_evidence"]),28)
        self.assertEqual(s["country_official_OIS_6m_count"],4)
        self.assertEqual(s["country_only_indicative_or_unavailable_OIS_6m_count"],4)
        self.assertEqual(s["country_2Y_and_official_OIS_same_date_count"],2)
        self.assertEqual(s["countries_same_date_2Y_official_OIS"],["GBP","JPY"])
        self.assertEqual(s["pair_same_day_2Y_raw_description_only"],4)
        self.assertEqual(s["pair_both_official_OIS_6m_any_dates"],6)
        self.assertEqual(s["pair_both_official_OIS_6m_same_date"],3)
        self.assertEqual(s["pair_full_bundle_2Y_and_official_OIS_exact_date"],0)
        for r in d["pair_evidence"].values():
            self.assertIsNone(r["macro_strength_diff_z"])
            self.assertFalse(r["CB_Want_Can_pair_comparison_validated"])
            self.assertFalse(r["2Y_basis_instrument_homogeneity_certified"])
            self.assertFalse(r["can_construct_model_relative_FX_score"])
            self.assertFalse(r["original_D_pair_rebuilt"])
        self.assertEqual(s["relative_FX_pair_scores_authorized"],0)
        self.assertEqual(s["Beta_forward_signals_generated"],0)
        self.assertFalse(d["safe_to_publish_D_json"])

    def test_same_day_matching_enforced_without_synthetic_cross_date_spreads(self):
        d=self.result["pair_evidence"]
        self.assertTrue(d["EUR/GBP"]["2Y_same_observation_day"])
        self.assertIsNotNone(d["EUR/GBP"]["2Y_raw_yield_difference_bp_DESCRIPTION_ONLY"])
        self.assertFalse(d["EUR/GBP"]["6m_official_same_observation_day"])
        self.assertIsNone(d["EUR/GBP"]["6m_official_curve_difference_bp_DESCRIPTION_ONLY"])
        self.assertTrue(d["AUD/JPY"]["6m_official_same_observation_day"])
        self.assertIsNotNone(d["AUD/JPY"]["6m_official_curve_difference_bp_DESCRIPTION_ONLY"])
        self.assertFalse(d["AUD/JPY"]["2Y_same_observation_day"])
        self.assertIsNone(d["AUD/JPY"]["2Y_raw_yield_difference_bp_DESCRIPTION_ONLY"])
        self.assertFalse(d["GBP/JPY"]["6m_official_same_observation_day"])
        self.assertFalse(d["GBP/JPY"]["2Y_same_observation_day"])
        self.assertFalse(d["EUR/USD"]["6m_official_both_legs"])

    def test_currency_indicative_is_visible_but_never_upgraded_to_OIS(self):
        d=self.result["source_currencies"]
        self.assertFalse(d["EUR"]["OIS_6m_is_official"])
        self.assertFalse(d["USD"]["OIS_6m_is_official"])
        self.assertIsNotNone(d["EUR"]["OIS_6m_level_pct"])
        self.assertIsNotNone(d["USD"]["OIS_6m_level_pct"])
        self.assertIsNone(d["CHF"]["OIS_6m_level_pct"])
        self.assertIsNone(d["NZD"]["OIS_6m_level_pct"])
        self.assertTrue(d["GBP"]["OIS_6m_is_official"])
        self.assertFalse(d["NZD"]["CB_Want_Can_publisher_statement_qualitatively_attested"])
        self.bad("ois",lambda x:x["currencies"]["EUR"].update(quality="OFFICIAL_CERTIFIED"))
        self.bad("ois",lambda x:x["currencies"]["CHF"].update(
            official_status="ACTIVE",backtest_eligible_as_official=True))
        self.bad("ois",lambda x:x["currencies"]["USD"].update(change_1w_available=True))
        self.bad("readiness",lambda x:x["currencies"]["EUR"].update(
            usable_for_policy_pricing=True))

    def test_no_fake_source_clocks_or_macro_fx_score(self):
        self.bad("rates",lambda x:x["AUD"].update(date="2026-10-27"))
        self.bad("rates",lambda x:x["CHF"].update(date="2026-10-29"))
        self.bad("rates",lambda x:x["USD"].update(quality="ESTIMATED"))
        self.bad("ois",lambda x:x["currencies"]["GBP"].update(as_of="2026-10-29"))
        self.bad("cb",lambda x:x["USD"].update(rate=float("nan")))
        self.bad("setup",lambda x:x.update(pair_count=27))
        self.bad("domestic",lambda x:x["countries"]["CAD"].update(
            FX_strength_candidate=0.4))
        self.bad("domestic",lambda x:x.update(safe_to_publish_D=True))
        self.bad("quant",lambda x:x.update(safe_to_recalculate_28_pairs=True))

    def test_no_production_rewrite_and_repeated_deterministic_receipt(self):
        protected=[SECTION/"D.json",SECTION/"PAIR_SETUP_OPERATIONAL_VIEW.json",
                   SECTION/"NATIVE_RATES_DATA.json",SECTION/"OIS_OPERATIONAL_VIEW.json",
                   ROOT/"validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl"]
        before={str(x):x.read_bytes() for x in protected}
        again=run("2026-10-28")
        self.assertEqual(again["receipt_sha256"],self.result["receipt_sha256"])
        self.assertEqual(before,{str(x):x.read_bytes() for x in protected})
        for field in ("safe_to_publish_D_json","safe_to_recalculate_28_pairs",
                      "safe_for_beta","safe_for_forward","writes_live_data"):
            self.assertFalse(again[field])
        with self.assertRaises(ValueError):
            run("2026-10-29")

if __name__=="__main__":
    unittest.main()
