#!/usr/bin/env python3
"""Synthetic spot OIS curves only; no commercial benchmarks stored in repo."""
import copy
import unittest
from validation.cb_pricing.eur_independent_spot_ois_forward_research_v1 import (
    SOURCE, INPUT_SCHEMA, METHODS, add_months, compare, forward_period,
    interpolate_df, spot_nodes
)
from datetime import date


class IndependentSpotOisResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive=SOURCE.read_text(encoding="utf-8")

    def synthetic(self,day="2026-10-22"):
        return {
          "schema":INPUT_SCHEMA,"currency":"EUR","floating_index":"ESTR",
          "reference_kind":"PUBLIC_SPOT_OIS_PAR_NOT_FUTURES",
          "quote_date":day,
          "source_url":"https://example.org/authorized-independent-reference",
          "fixed_leg_assumption":"SINGLE_PAYMENT_ACT360_UNVERIFIED",
          "market_timestamp_alignment_verified":False,
          "independent_fwd_OIS_benchmark_certified":False,
          "license_to_redistribute_snapshot":False,
          "eligible_to_change_live_OIS":False,
          "tenors":[{"months":m,"par_rate_pct":2.2+.04*m} for m in range(1,13)]
        }

    def test_synthetic_22_oct_exact_future_period_has_one_comparison(self):
        x=compare(self.archive,self.synthetic())
        self.assertEqual(x["spot_quote_day"],"2026-10-22")
        self.assertEqual(x["comparable_reconstructed_forward_count"],1)
        self.assertEqual(x["EUR_futures_rows_on_spot_source_day"],1)
        self.assertEqual(x["comparisons"][0]["contract"],"FST3M2027")
        self.assertEqual(set(x["comparisons"][0][
            "independent_spot_OIS_curve_forward_by_assumption_pct"]),set(METHODS))
        self.assertIsNone(x["historical_OIS_level_prediction_MAE_bp"])
        self.assertIsNone(x["historical_OIS_direction_hit_rate"])
        self.assertFalse(x["eligible_to_change_live_OIS"])
        self.assertFalse(x["eligible_to_change_FX_bias_pairs_or_forward"])
        self.assertFalse(x["writes_live_data"])
        self.assertFalse(x["redistributes_underlying_vendor_spot_rates"])
        self.assertFalse(x["underlying_OIS_quotes_time_aligned_to_futures"])
        self.assertTrue(x["rates_are_NOT_a_direct_forward_OIS_benchmark"])

    def test_synthetic_29_oct_started_contract_is_excluded(self):
        x=compare(self.archive,self.synthetic("2026-10-29"))
        self.assertEqual(x["EUR_futures_rows_on_spot_source_day"],3)
        self.assertEqual(x["comparable_reconstructed_forward_count"],2)
        self.assertEqual({z["contract"] for z in x["comparisons"]},
                         {"FST3G2027","FST3M2027"})
        self.assertEqual(len(x["skipped"]),1)
        self.assertEqual(x["skipped"][0]["contract"],"FST3V2026")
        self.assertEqual(x["skipped"][0]["reason"],"STARTED_OR_START_DAY_NO_PURE_FORWARD")

    def test_interpolation_variants_bounded_on_synthetic_curve(self):
        day,spots=spot_nodes(self.synthetic())
        a=forward_period(day,spots,"2027-06-16","2027-09-15")
        self.assertEqual(set(a),set(METHODS))
        self.assertLess(max(a.values())-min(a.values()),.015)
        self.assertGreater(a["LOG_DISCOUNT"],0)

    def test_bad_governance_or_fake_instrument_is_rejected(self):
        for k,v in [
          ("floating_index","EURIBOR"),
          ("reference_kind","FUTURES_ESTR_SAME_SOURCE"),
          ("fixed_leg_assumption","ACT360_CERTIFIED"),
          ("market_timestamp_alignment_verified",True),
          ("independent_fwd_OIS_benchmark_certified",True),
          ("license_to_redistribute_snapshot",True),
          ("eligible_to_change_live_OIS",True),
          ("source_url","http://unverifiable.invalid")
        ]:
            d=self.synthetic()
            d[k]=v
            with self.subTest(k=k),self.assertRaises(ValueError):
                compare(self.archive,d)

    def test_no_extrapolation_and_sparse_shape_fails_closed(self):
        d=self.synthetic()
        d["tenors"]=[x for x in d["tenors"] if x["months"]!=11]
        x=compare(self.archive,d)
        self.assertEqual(x["comparable_reconstructed_forward_count"],0)
        self.assertEqual(x["skipped"][0]["reason"],
                         "INSUFFICIENT_SPOT_CURVE_NO_EXTRAPOLATION")
        d=self.synthetic()
        d["tenors"][2]["months"]=2
        with self.assertRaises(ValueError):
            compare(self.archive,d)
        d=self.synthetic()
        d["tenors"][3]["par_rate_pct"]=float("nan")
        with self.assertRaises(ValueError):
            compare(self.archive,d)

    def test_no_valid_future_after_start(self):
        day,pts=spot_nodes(self.synthetic("2026-10-29"))
        with self.assertRaises(ValueError):
            forward_period(day,pts,"2026-10-21","2027-01-20")

    def test_actual_month_ends(self):
        self.assertEqual(add_months(date(2026,1,31),1),date(2026,2,28))
        self.assertEqual(add_months(date(2026,10,22),4),date(2027,2,22))


if __name__=="__main__":
    unittest.main()
