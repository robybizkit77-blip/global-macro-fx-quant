"""Adversarial matched-week Beta diagnostics; never certify historical PIT."""
from __future__ import annotations

import copy
from datetime import date, timedelta
import json
import math
import unittest

from validation.beta import weekly_fx_2y_shadow_oos_v1 as m


class WeeklyBetaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx=json.loads(m.FX_PATH.read_text(encoding="utf-8"))
        cls.rates=json.loads(m.RATE_PATH.read_text(encoding="utf-8"))
        cls.receipt=m.audit(cls.fx,cls.rates)

    def test_real_sources_all_28_no_core_promotion(self):
        a=self.receipt
        self.assertEqual(a["pair_count"],28)
        self.assertEqual(len({x["pair"] for x in a["pairs"]}),28)
        self.assertFalse(a["beta_promoted"])
        self.assertFalse(a["trading_performance_claim"])
        self.assertFalse(a["historical_point_in_time_vintages_verified"])
        self.assertFalse(a["yield_instrument_basis_comparable_across_countries"])
        self.assertTrue(a["training_window_past_only"])
        self.assertTrue(all(not x["forward_prospective_certified"] for x in a["pairs"]))
        self.assertTrue(all(not x["source_definition_comparability_verified"] for x in a["pairs"]))

    def test_jpy_corrupt_chronology_quarantined_not_silently_sorted(self):
        self.assertEqual(self.receipt["rate_2y_series_quality"]["JPY"]["reason"],
                         "NONCANONICAL_2Y_HISTORY_DATE")
        jpy=[p for p in self.receipt["pairs"] if "JPY" in p["pair"]]
        self.assertEqual(len(jpy),7)
        self.assertTrue(all(p["historical_oos_observations"]==0 for p in jpy))
        self.assertTrue(all(p["status"]=="INSUFFICIENT_OR_INVALID_REFERENCE_PANEL" for p in jpy))

    def test_usd_gbp_is_real_pseudo_oos_not_forward(self):
        a=next(p for p in self.receipt["pairs"] if p["pair"]=="USDGBP")
        self.assertGreaterEqual(a["aligned_weekly_fixing_points"],55)
        self.assertGreaterEqual(a["historical_oos_observations"],3)
        self.assertEqual(a["status"],"ILLUSTRATIVE_HISTORICAL_OOS_NOT_PIT")
        for e in a["recent_oos_samples"]:
            self.assertLess(e["training_last_week_end"],e["evaluation_week_end"])
            self.assertEqual(e["train_count"],52)

    def test_2y_current_snapshot_chf_is_stale_not_traded_timing(self):
        self.assertEqual(self.receipt["rate_2y_series_quality"]["CHF"]["reported_as_of"],
                         "2026-09-30")
        self.assertFalse(self.receipt["historical_point_in_time_vintages_verified"])

    def test_reject_fx_wrong_source(self):
        fx=copy.deepcopy(self.fx)
        fx["source_url"]="https://example.invalid/eur"
        with self.assertRaisesRegex(ValueError,"unverified ECB"):
            m.audit(fx,self.rates)

    def test_reject_rate_duplicate_source_date(self):
        d=copy.deepcopy(self.rates)
        d["USD"]["history2"]["dates"][11]=d["USD"]["history2"]["dates"][10]
        _,reason=m.rate_history("USD",d,date(2026,10,26))
        self.assertEqual(reason,"UNORDERED_OR_DUPLICATE_2Y_HISTORY")

    def test_reject_2y_nonfinite(self):
        d=copy.deepcopy(self.rates)
        d["USD"]["history2"]["values"][2]=float("nan")
        _,reason=m.rate_history("USD",d,date(2026,10,26))
        self.assertEqual(reason,"INVALID_2Y_HISTORY_VALUE")

    def test_reject_unmatched_rate_asof(self):
        d=copy.deepcopy(self.rates)
        d["GBP"]["date"]="2026-10-23"
        _,reason=m.rate_history("GBP",d,date(2026,10,26))
        self.assertEqual(reason,"2Y_SOURCE_ASOF_MISMATCH")

    def test_yield_may_be_negative(self):
        d=copy.deepcopy(self.rates)
        d["CHF"]["history2"]["values"][0]=-0.21
        h,reason=m.rate_history("CHF",d,date(2026,10,26))
        self.assertIsNone(reason)
        self.assertEqual(min(h.values()),-0.21)

    def test_fx_rate_cross_formula(self):
        x=m.official_fx(self.fx,date(2026,10,26))
        day=date(2026,10,23)
        self.assertAlmostEqual(x[day]["GBP"]/x[day]["USD"],
                               self.fx["rows"][-1]["GBP"]/self.fx["rows"][-1]["USD"])

    def test_weekly_reference_prevents_gap_stitching(self):
        mk=lambda week: {"week_end":date(2025,1,3)+timedelta(days=7*week),
                         "observed_date":date(2025,1,3)+timedelta(days=7*week),
                         "fx_rate":1.02+week*0.001,
                         "two_y_relative_pp":0.02+week*0.004}
        # Week 2 missing: no 2-week "weekly" return is manufactured.
        pts=[mk(0),mk(1),mk(3),mk(4)]
        a=m.consecutive_returns(pts)
        self.assertEqual(len(a),2)
        self.assertEqual([r["week_end"] for r in a],
                         [mk(1)["week_end"],mk(4)["week_end"]])

    def test_synthetic_prior_training_has_no_future_leak_and_improves_variance(self):
        # Purpose-built synthetic ONLY, never used as reported market evidence.
        day=date(2023,1,6)
        rows=[]
        for i in range(72):
            week=day+timedelta(days=7*i)
            x=((i*19)%17-8)*.001
            noise=((i*7)%13-6)*.00006
            rows.append({"week_end":week,"fx_return":1.8*x+noise,
                         "delta_rel_2y":x})
        obs=m.strict_oos(rows)
        self.assertEqual(len(obs),20)
        self.assertEqual(obs[0]["training_last_week_end"],rows[51]["week_end"].isoformat())
        self.assertEqual(obs[0]["evaluation_week_end"],rows[52]["week_end"].isoformat())
        self.assertAlmostEqual(obs[0]["hedged_reference_residual"],
                               rows[52]["fx_return"]-obs[0]["beta_trained_prior_only"]*rows[52]["delta_rel_2y"])
        ys=[x["fx_return_observed"] for x in obs]
        zs=[x["hedged_reference_residual"] for x in obs]
        self.assertLess(m.pvariance(zs),m.pvariance(ys))

    def test_no_oos_without_52_prior_returns(self):
        day=date(2024,1,5)
        rows=[{"week_end":day+timedelta(days=7*i),
               "fx_return":0.003*i, "delta_rel_2y":0.02*i}
              for i in range(52)]
        self.assertEqual(m.strict_oos(rows),[])

    def test_noncontiguous_52w_training_refused(self):
        day=date(2024,1,5)
        dates=[day+timedelta(days=7*i) for i in range(70)]
        dates[10]=dates[10]-timedelta(days=2)
        rows=[{"week_end":d, "fx_return":.01*i, "delta_rel_2y":.02*i}
              for i,d in enumerate(dates)]
        obs=m.strict_oos(rows)
        self.assertTrue(all(o["evaluation_week_end"]!=rows[52]["week_end"].isoformat()
                            for o in obs))
        self.assertTrue(all(o["training_last_week_end"] < o["evaluation_week_end"] for o in obs))

    def test_bad_input_date_rejected(self):
        with self.assertRaisesRegex(ValueError,"noncanonical ISO date"):
            m.strict_date("2025-5-8")


if __name__=="__main__":
    unittest.main()
