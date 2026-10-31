#!/usr/bin/env python3
"""Adversarial numeric/source check for NZD study-only ASX BB/OCR scenarios."""
from __future__ import annotations
import copy
import json
import unittest
from datetime import date, timedelta
from pathlib import Path

from nzd_asx_scenario_sensitivity_v2 import ASX, CAL, check_asx, calibration, build, expiry_for

ASOF = date(2026,10,31)


class NzdScenarioSensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Fixed 30-Oct ASX public-research replay, never pinned to the
        # moving newest operational quote feed used on future weekdays.
        cls.feed=json.loads(ASX.read_text(encoding="utf-8"))
        cls.feed["as_of"]="2026-10-30"
        cls.feed["source_url"]=(
            "https://www.asx.com.au/data/futures/reports/"
            "EODWebMarketSummary261030ZFT.htm")
        cls.feed["horizons"]={
            h:{
                "expiry_label":label, "expiration":expiry,
                "settlement_price":100-rate,
                "implied_bank_bill_rate":rate,
                "settlement_change":0.06, "change_1d_bp":-6.0,
                "change_1w_bp":weekly,
                "weekly_reference_trade_date":"2026-10-23",
                "mapping":f"nearest listed expiry to trade_date+{days}d; no interpolation"
            } for h,(label,expiry,rate,weekly,days) in {
               "3m":("Mar 2027","2027-03-10",3.59,-21.0,90),
               "6m":("Jun 2027","2027-06-16",3.9,-16.0,180),
               "12m":("Sep 2027","2027-09-15",4.05,-12.0,365)
            }.items()}
        cls.cal=json.loads(CAL.read_text(encoding="utf-8"))

    def test_source_31_oct_three_bills_reproducible_and_not_ois(self):
        result=build(self.feed,self.cal,asof=ASOF)
        fit=result["calibration"]
        self.assertEqual(fit["central_basis_bp"],24)
        self.assertEqual(fit["stress_recent_q3_basis_bp"],38)
        self.assertEqual(fit["historical_training_observations"],19)
        self.assertEqual(fit["historical_holdout_observations"],3)
        self.assertEqual(fit["pre_registered_point_test_mae_bp"],16.33)
        self.assertTrue(fit["interval_50bp_selected_after_holdout"])
        self.assertFalse(result["policy_or_fx_signal_allowed"])
        self.assertFalse(result["out_of_sample_interval_coverage_certified"])
        self.assertFalse(result["official_ois_runtime_mutated"])
        self.assertEqual(result["source_evidence_grade"],
                         "ASX_OFFICIAL_EXCHANGE_FUTURES_NOT_OIS")
        self.assertEqual(set(result["horizons"]),{"3m","6m","12m"})
        self.assertEqual({h:q["central_non_ois_scenario_pct"]
                          for h,q in result["horizons"].items()},
                         {"3m":3.35,"6m":3.66,"12m":3.81})
        self.assertEqual({h:q["stress_q3_basis_non_ois_scenario_pct"]
                          for h,q in result["horizons"].items()},
                         {"3m":3.21,"6m":3.52,"12m":3.67})
        for q in result["horizons"].values():
            self.assertEqual(q["point_vs_stress_abs_bp"],14)
            self.assertFalse(q["policy_repricing_signal"])
            self.assertFalse(q["official_ois_eligible"])
            self.assertEqual(q["model_fx_effect"],"NONE")
            self.assertLess(q["descriptive_ex_post_lower_pct"],
                            q["central_non_ois_scenario_pct"])
            self.assertLess(q["stress_q3_basis_non_ois_scenario_pct"],
                            q["descriptive_ex_post_upper_pct"])

    def bad(self,change,label):
        s=copy.deepcopy(self.feed)
        change(s)
        with self.subTest(label=label):
            with self.assertRaises(ValueError,msg=label):
                build(s,self.cal,asof=ASOF)

    def test_price_and_change_arithmetic_tampering(self):
        self.bad(lambda s:s["horizons"]["6m"].__setitem__("settlement_price",96.11),
                 "bad settlement/100 yield identity")
        self.bad(lambda s:s["horizons"]["12m"].__setitem__("implied_bank_bill_rate",3.97),
                 "bad yield identity")
        self.bad(lambda s:s["horizons"]["3m"].__setitem__("change_1d_bp",+6.0),
                 "wrong 1d futures rate sign")
        self.bad(lambda s:s["horizons"]["6m"].__setitem__("settlement_change",0.07),
                 "changed settlement not matching 1d")
        self.bad(lambda s:s["horizons"]["6m"].__setitem__("change_1w_bp",None),
                 "orphan weekly date")

    def test_contract_identity_and_tenor_tampering(self):
        self.bad(lambda s:s["horizons"]["3m"].__setitem__("expiry_label","Jun 2027"),
                 "wrong nearby contract label")
        self.bad(lambda s:s["horizons"]["6m"].__setitem__("expiration","2027-06-17"),
                 "forged expiry")
        self.bad(lambda s:s["horizons"]["12m"].__setitem__("mapping","interpolated"),
                 "interpolated curve")
        self.bad(lambda s:s["horizons"]["12m"].__setitem__("expiry_label","Mar 2027"),
                 "same or wrong expiry")
        self.bad(lambda s:s["horizons"].pop("6m"),"missing 6m")
        self.bad(lambda s:s["horizons"].__setitem__("18m",{}),"extra tenor")

    def test_date_source_and_weekly_tampering(self):
        self.bad(lambda s:s.__setitem__("source_url","https://example.com/fake"),
                 "forged source")
        self.bad(lambda s:s.__setitem__("as_of","2026-10-29"),
                 "asof does not match official ASX report filename")
        self.bad(lambda s:s["horizons"]["3m"].__setitem__(
            "weekly_reference_trade_date","2026-10-01"),"stale weekly reference")
        with self.assertRaises(ValueError):
            build(self.feed,self.cal,asof=date(2026,11,10))
        with self.assertRaises(ValueError):
            build(self.feed,self.cal,asof=date(2026,10,29))
        self.bad(lambda s:s.__setitem__("status","WITHHELD"),"unverified source status")

    def test_governance_promotion_rejected(self):
        for change in (
            lambda s:s["governance"].__setitem__("substitutes_for_ois_level",True),
            lambda s:s["governance"].__setitem__("policy_delta_from_proxy_allowed",True),
            lambda s:s["governance"].__setitem__("backtest_eligible_as_official_ois",True),
            lambda s:s["governance"].__setitem__("core_score_effect","NZD_LONG"),
            lambda s:s["governance"].__setitem__("pair_engine_effect","BUY"),
        ):
            self.bad(change,"prohibited OIS or FX effect")

    def test_calibration_point_fit_is_frozen_and_holdout_not_reoptimised(self):
        c=copy.deepcopy(self.cal)
        self.assertEqual(calibration(c)["stress_shift_from_original_bp"],14)
        c["recent_plateau"]["rows"][2]["bank_bill_90d_pct"]=7.5
        with self.assertRaises(ValueError):
            calibration(c)
        c=copy.deepcopy(self.cal)
        c["method"]["weighted_recent_median"]=1.
        with self.assertRaises(ValueError):
            calibration(c)
        c=copy.deepcopy(self.cal)
        c["holdout_2026_q3"]["rows"][1]["bank_bill_90d_pct"]=3.0
        with self.assertRaises(ValueError):
            calibration(c)

    def test_verified_expiry_calendar(self):
        self.assertEqual(expiry_for("Mar 2027"),"2027-03-10")
        self.assertEqual(expiry_for("Jun 2027"),"2027-06-16")
        self.assertEqual(expiry_for("Sep 2027"),"2027-09-15")
        with self.assertRaises(ValueError):
            expiry_for("Mar! 2027")


if __name__=="__main__":
    unittest.main(verbosity=2)
