#!/usr/bin/env python3
"""Synthetic source fixtures; no official vendor CSV re-published."""
import math
import unittest
from datetime import date
from validation.cb_pricing.probe_eurex_clearing_discount_curve_v1 import (
    CURVE, DATE, parse_stream, relevant_futures, required_dates
)

class ClearingOisSourceTests(unittest.TestCase):
    def rows(self, *,curve=CURVE,source_day=DATE,duplicates=False,missing=None,
             differ=False,format_semicolon=False):
        futures=relevant_futures()
        days=sorted(required_dates(futures))
        sep=";" if format_semicolon else ","
        out=[sep.join(["Value DateTime","Curve ID","Maturity Offset",
                       "Maturity Date","Value Type","Value"])]
        seen=0
        for d in days:
            if d==missing: continue
            days_from=(date.fromisoformat(d)-date.fromisoformat(source_day)).days
            df=math.exp(-.025*days_from/360)
            row=[f"{source_day} 23:59:00",curve,str(days_from),
                 f"{d} 00:00:00","S",f"{df:.12f}"]
            out.append(sep.join(row)); seen+=1
            if duplicates and seen==1:
                row[-1]=str(df-.003 if differ else df)
                out.append(sep.join(row))
        return [x+"\n" for x in out]

    def test_actual_archive_has_two_unstarted_futures_on_29_oct(self):
        f=relevant_futures()
        self.assertEqual({r["contract"] for r in f},
                         {"FST3G2027","FST3M2027"})
        self.assertEqual(len(required_dates(f)),4)

    def test_only_correct_estr_curve_and_same_day_may_match(self):
        r=parse_stream(self.rows())
        self.assertEqual(r["status"],"EXACT_29OCT_ESTR_DISCOUNT_FACTORS_FOUND")
        self.assertEqual(r["exact_discount_factor_count"],4)
        self.assertEqual(r["matched_observations_count"],2)
        self.assertEqual(r["independent_OIS_traded_benchmark_count"],0)
        self.assertIsNone(r["MAE_vs_true_OIS_bp"])
        self.assertFalse(r["eligible_to_modify_live_OIS_or_FX"])
        self.assertFalse(r["raw_vendor_data_stored"])
        for item in r["matched_futures"]:
            self.assertAlmostEqual(
                item["otc_model_estr_forward_from_discount_factors_pct"],2.5,
                delta=.01)
            self.assertFalse(item["direct_independent_dealer_quote"])
            self.assertTrue(item["curve_from_same_eurex_group"])

    def test_different_euribor_curve_not_substituted(self):
        r=parse_stream(self.rows(curve="EUR.EURIBOR.3M"))
        self.assertEqual(r["matched_observations_count"],0)
        self.assertEqual(r["exact_discount_factor_count"],0)
        self.assertEqual(r["status"],
                         "NO_VALID_ESTR_DISCOUNT_FACTORS_FOR_EXACT_WINDOWS")

    def test_different_val_date_not_substituted(self):
        r=parse_stream(self.rows(source_day="2026-10-28"))
        self.assertEqual(r["matched_observations_count"],0)
        self.assertEqual(r["exact_discount_factor_count"],0)

    def test_no_extrapolation_if_missing_factor(self):
        d=sorted(required_dates(relevant_futures()))[0]
        r=parse_stream(self.rows(missing=d))
        self.assertEqual(r["matched_observations_count"],1)
        self.assertEqual(r["status"],
                         "PARTIAL_ESTR_DISCOUNT_FACTORS_FOUND")
        self.assertIsNone(r["MAE_vs_true_OIS_bp"])

    def test_conflicting_same_timestamp_factor_rejected(self):
        # Inject a duplicate factor with changed value at a different index.
        rows=self.rows(duplicates=True,differ=True)
        r=parse_stream(rows)
        self.assertEqual(r["status"],"CONFLICTING_DUPLICATE_DISCOUNT_FACTORS")
        self.assertEqual(r["matched_observations_count"],0)

    def test_semicolon_csv_header_supported(self):
        r=parse_stream(self.rows(format_semicolon=True))
        self.assertEqual(r["matched_observations_count"],2)
        self.assertEqual(r["delimiter"],";")

if __name__=="__main__":
    unittest.main()
