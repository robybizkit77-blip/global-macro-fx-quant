"""Regression tests: dated source-clock 2Y changes, no false surprise or FX edge."""
from __future__ import annotations

import copy
import json
import unittest

from validation.macro.v2_fx_2y_repricing_surprise_admission_v1 import (
    EVALUATION_DAY, SECTION, evaluate, inspect_2y, inspect_consensus,
    run
)
from validation.macro.v2_fx_28pair_synchronized_evidence_gate_v1 import run as source_run


class DatedRepricingSurpriseAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        read=lambda f:json.loads((SECTION/(f+".json")).read_text(encoding="utf-8"))
        cls.args={
            "rates":read("NATIVE_RATES_DATA"),
            "source":source_run(as_of=EVALUATION_DAY),
            "calendar":read("MACRO_CONSENSUS_SECONDARY_V1"),
            "seed":read("MACRO_RELEASE_OFFICIAL_SEED_V1")
        }
        cls.output=evaluate(**cls.args)

    def bad(self,key,change):
        d=copy.deepcopy(self.args[key])
        change(d)
        inputs=dict(self.args)
        inputs[key]=d
        with self.assertRaises(ValueError):
            evaluate(**inputs)

    def test_5_2Y_reported_change_values_do_not_mean_adjacent_history_change(self):
        s=self.output["summary"]
        self.assertEqual(s["currencies"],8)
        self.assertEqual(s["2Y_displayed_change_not_adjacent_history_count"],5)
        self.assertEqual(
            s["2Y_displayed_change_not_adjacent_history_currencies"],
            ["CAD","CHF","EUR","JPY","USD"])
        self.assertEqual(
            s["2Y_numeric_compatible_but_reference_unverified_currencies"],
            ["AUD","GBP","NZD"])
        c=self.output["currencies"]
        self.assertAlmostEqual(c["USD"]["calculated_latest_adjacent_history_change_bp"],2)
        self.assertEqual(c["USD"]["displayed_chg2_bp"],-9)
        self.assertAlmostEqual(c["EUR"]["calculated_latest_adjacent_history_change_bp"],4.191942,places=5)
        self.assertEqual(c["EUR"]["displayed_chg2_bp"],-2.8)
        self.assertAlmostEqual(c["CAD"]["calculated_latest_adjacent_history_change_bp"],15)
        self.assertAlmostEqual(c["JPY"]["calculated_latest_adjacent_history_change_bp"],0)
        self.assertTrue(all(
            r["chg2_source_reference_clock_verified_as_adjacent_history"] is False
            for r in c.values()))
        self.assertTrue(all(r["usable_for_model_2Y_repricing"] is False
                            for r in c.values()))

    def test_only_pairwise_common_real_start_and_end_dates_make_descriptive_2Y_deltas(self):
        summary=self.output["summary"]
        self.assertEqual(summary["28_pair_universe"],28)
        self.assertEqual(summary["2Y_pairs_same_last_observation_date"],4)
        self.assertEqual(summary["2Y_pairs_same_start_and_end_date_and_7day_gap"],4)
        self.assertEqual(set(summary["2Y_pairs_with_matched_window_descriptive_change"]),
                         {"EUR/CAD","EUR/GBP","GBP/CAD","USD/JPY"})
        e=self.output["pairs"]
        self.assertEqual(e["EUR/GBP"]["2Y_common_start"],"2026-10-23")
        self.assertEqual(e["EUR/GBP"]["2Y_common_end"],"2026-10-26")
        self.assertIsNotNone(e["EUR/GBP"]["2Y_relative_change_bp_DESCRIPTIVE_ONLY"])
        self.assertEqual(e["USD/JPY"]["2Y_common_start"],"2026-10-26")
        self.assertEqual(e["USD/JPY"]["2Y_common_end"],"2026-10-27")
        self.assertAlmostEqual(e["USD/JPY"]["2Y_relative_change_bp_DESCRIPTIVE_ONLY"],2)
        self.assertIsNone(e["EUR/USD"]["2Y_relative_change_bp_DESCRIPTIVE_ONLY"])
        self.assertIsNone(e["AUD/JPY"]["2Y_relative_change_bp_DESCRIPTIVE_ONLY"])
        for r in e.values():
            self.assertFalse(r["2Y_instruments_comparable_same_risk_free_basis"])
            self.assertFalse(r["source_original_release_day_PIT_2Y_proven"])
            self.assertFalse(r["CB_Want_Can_confirmed_from_issuer_statements"])
            self.assertIsNone(r["official_6m_OIS_relative_repricing_bp"])
            self.assertIsNone(r["FX_direction"])
            self.assertIsNone(r["FX_strength_score"])

    def test_two_future_forecasts_are_not_actual_macro_surprises(self):
        r=self.output
        s=r["summary"]
        self.assertEqual(s["secondary_future_forecasts_count"],2)
        self.assertEqual(s["official_actuals_with_prior_locked_consensus"],0)
        self.assertEqual(s["validated_macro_surprises"],0)
        self.assertEqual(s["CB_Want_Can_verified_from_statement"],0)
        for event in r["consensus_future_events"]:
            self.assertEqual(event["official_release_day"],"2026-10-30")
            self.assertIsNone(event["official_actual"])
            self.assertIsNone(event["actual_publisher_release_clock"])
            self.assertIsNone(event["surprise_actual_minus_forecast"])
            self.assertFalse(event["surprise_available_for_FX"])
        self.bad("calendar",lambda d:d["events"][0].update(
            official_date="2026-10-28"))
        self.bad("calendar",lambda d:d["events"][0].update(
            actual_ignored_for_pre_release_consensus=False))
        self.bad("calendar",lambda d:d["events"][0].update(
            consensus=""))
        self.bad("seed",lambda d:d.update(consensus="OFFICIAL_INCLUDED"))

    def test_clock_and_definition_misrepresentation_fail_closed(self):
        self.bad("rates",lambda d:d["USD"].update(date="2026-10-29"))
        self.bad("rates",lambda d:d["GBP"].update(**{"2Y":float("nan")}))
        self.bad("rates",lambda d:d["CAD"]["history2"]["dates"].__setitem__(
            -1, "2026-10-25"))
        self.bad("rates",lambda d:d["USD"]["history2"]["values"].__setitem__(
            -1, 4.71))
        self.bad("source",lambda d:d.update(safe_to_publish_D_json=True))
        self.bad("source",lambda d:d["pair_evidence"]["USD/JPY"].update(
            can_construct_model_relative_FX_score=True))

    def test_no_live_writes_and_deterministic_research_result(self):
        files=["D.json","NATIVE_RATES_DATA.json","OIS_OPERATIONAL_VIEW.json",
               "PAIR_SETUP_OPERATIONAL_VIEW.json","MACRO_CONSENSUS_SECONDARY_V1.json"]
        before={f:(SECTION/f).read_bytes() for f in files}
        r=run()
        self.assertEqual(self.output["receipt_sha256"],r["receipt_sha256"])
        self.assertEqual(before,{f:(SECTION/f).read_bytes() for f in files})
        for key in ("safe_to_publish_new_D","safe_to_change_28_pair_states",
                    "safe_to_promote_a_2Y_change_to_tradable_signal",
                    "safe_to_use_for_beta","safe_to_use_for_forward","writes_live_data"):
            self.assertFalse(r[key])
        with self.assertRaises(ValueError):run("2026-10-29")

if __name__=="__main__":
    unittest.main()
