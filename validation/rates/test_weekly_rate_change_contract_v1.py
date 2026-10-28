"""Live Rates producer weekly 2Y/10Y semantic contract and no-read-altering tests."""
from __future__ import annotations
import copy
import json
import unittest
from datetime import date,timedelta
from pathlib import Path

from validation.rates.verify_weekly_rate_change_contract_v1 import (
    LIVE, validate, run
)

class RatesWeeklyReferenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current=json.loads(LIVE.read_text(encoding="utf-8"))
        cls.receipt=validate(cls.current)

    def fail(self,modify):
        src=copy.deepcopy(self.current)
        modify(src)
        with self.assertRaises(ValueError):
            validate(src)

    def test_real_2y10y_weekly_source_receipts_and_swiss_label(self):
        d=self.receipt
        self.assertEqual(d["status"],"PASS_WEEKLY_2Y10Y_REFERENCE_CONTRACT")
        self.assertEqual(d["summary"]["verified_with_dated_2Y_and_10Y_weekly_receipts"],7)
        self.assertEqual(d["summary"]["unverified_without_weekly_receipt"],["CHF"])
        self.assertEqual(d["automatic_source_weekly_receipts_verified"],6)
        self.assertFalse(d["currencies"]["CHF"]["weekly_2Y_10Y_certified"])
        for c in ("USD","EUR","GBP","JPY","CAD","AUD","NZD"):
            for tenor in ("2Y","10Y"):
                row=d["currencies"][c][tenor]
                self.assertTrue(row["weekly_source_receipt_matched"])
                self.assertEqual(row["source_end_day"],self.current[c]["date"])
                self.assertLessEqual(row["source_reference_day"],
                                     row["reference_seven_day_cutoff"])
                self.assertFalse(row["source_pit_release_day_certified"])
        self.assertFalse(d["writes_live_data"])
        self.assertFalse(d["safe_to_change_Core"])
        self.assertFalse(d["safe_to_change_28_pairs"])

    def test_5_adjacent_history_discrepancies_are_valid_weekly_not_errors(self):
        bad_last_two=[]
        for c in ("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"):
            row=self.current[c];v=row["history2"]["values"]
            close_delta=round((v[-1]-v[-2])*100,1)
            if abs(close_delta-row["chg2_bp"])>0.11:
                bad_last_two.append(c)
        self.assertEqual(set(bad_last_two),{"USD","EUR","JPY","CHF","CAD"})
        self.assertEqual(self.current["USD"]["chg2_bp"],-9.0)
        self.assertEqual(self.receipt["currencies"]["USD"]["2Y"]["source_reference_day"],
                         "2026-10-20")
        self.assertEqual(self.current["USD"]["date"],"2026-10-27")
        self.assertEqual(self.current["EUR"]["chg2_bp"],-2.8)
        self.assertEqual(self.receipt["currencies"]["EUR"]["2Y"]["source_reference_day"],
                         "2026-10-19")
        self.assertEqual(self.current["JPY"]["chg2_bp"],-2.1)
        self.assertEqual(self.receipt["currencies"]["JPY"]["2Y"]["source_reference_day"],
                         "2026-10-20")
        self.assertEqual(self.current["CAD"]["chg2_bp"],4.0)
        self.assertEqual(self.receipt["currencies"]["CAD"]["2Y"]["source_reference_day"],
                         "2026-10-19")

    def test_mutating_weekly_display_or_receipt_values_fail_before_publication(self):
        self.fail(lambda d:d["USD"].update(chg2_bp=2.0))
        self.fail(lambda d:d["EUR"]["weekly2_validation"].update(change_bp=99))
        self.fail(lambda d:d["JPY"]["weekly2_validation"].update(
            start_date="2026-10-26"))
        self.fail(lambda d:d["CAD"]["weekly10_validation"].update(
            end_date="2026-10-25"))
        self.fail(lambda d:d["AUD"]["weekly2_validation"].update(
            start_value=123.456))
        self.fail(lambda d:d["GBP"]["history2"]["values"].__setitem__(-1,123))
        self.fail(lambda d:d["NZD"]["history10"].update(last_date="2026-10-15"))

    def test_source_clock_not_silently_rewritten_or_future_faked(self):
        self.fail(lambda d:d["USD"].update(date="2026-10-28"))
        self.fail(lambda d:d["GBP"]["weekly10_validation"].update(
            start_date="2026-10-26"))
        self.fail(lambda d:d["CAD"]["history2"]["dates"].__setitem__(-1,
            "2026-10-27"))
        self.fail(lambda d:d["JPY"].update(chg10_bp=float("nan")))
        self.fail(lambda d:d["EUR"].update(quality="ESTIMATED_INFORMATIONAL"))
        self.fail(lambda d:d["CHF"].update(weekly2_validation={
            "start_date":"2026-09-23","end_date":"2026-09-30"
        }))

    def test_candidate_diff_allowed_only_original_six_auto_official_daily_sources(self):
        # A candidate can be identical, and cannot silently alter live CHF
        # or the separately reviewed NZD manual snapshots.
        d=validate(self.current,reference=self.current)
        self.assertEqual(d["summary"]["changed_currencies"],[])
        altered=copy.deepcopy(self.current)
        altered["CHF"]["2Y"]+=0.01
        with self.assertRaises(ValueError):validate(altered,reference=self.current)
        altered=copy.deepcopy(self.current)
        altered["NZD"]["freshness_note"]="fake new"
        with self.assertRaises(ValueError):validate(altered,reference=self.current)
        altered=copy.deepcopy(self.current)
        altered["USD"]["freshness_note"]="changed without new source"
        with self.assertRaises(ValueError):validate(altered,reference=self.current)

    def test_synthetic_new_USD_source_date_could_pass_only_with_matching_weekly_2y_10y_receipts(self):
        # A deterministic synthetic contract exercise, NOT an observed
        # Treasury print or permission to push a future rate.
        out=copy.deepcopy(self.current)
        row=out["USD"]
        newday=(date.fromisoformat(row["date"])+timedelta(days=1)).isoformat()
        oldday=row["date"]
        row["date"]=newday
        for tenor,hname,receipt_name,delta_name,newvalue in (
            ("2Y","history2","weekly2_validation","chg2_bp",row["2Y"]+0.01),
            ("10Y","history10","weekly10_validation","chg10_bp",row["10Y"]+0.02)
        ):
            history=row[hname]
            history["dates"].append(newday)
            history["values"].append(newvalue)
            history["last_date"]=newday
            history["last_value"]=newvalue
            row[tenor]=newvalue
            cutoff=(date.fromisoformat(newday)-timedelta(days=7)).isoformat()
            refs=[d for d in history["dates"] if d<=cutoff]
            start=max(refs)
            start_value=history["values"][history["dates"].index(start)]
            weekly_bp=round((newvalue-start_value)*100,1)
            row[delta_name]=weekly_bp
            row[receipt_name].update(
                start_date=start,start_value=start_value,
                end_date=newday,end_value=newvalue,change_bp=weekly_bp)
        row["curve_bp"]=round((row["10Y"]-row["2Y"])*100,1)
        verified=validate(out,reference=self.current)
        self.assertEqual(verified["summary"]["changed_currencies"],["USD"])
        self.assertEqual(verified["currencies"]["USD"]["2Y"]["source_end_day"],newday)
        self.assertEqual(verified["currencies"]["USD"]["10Y"]["source_end_day"],newday)
        self.assertEqual(self.current["USD"]["date"],oldday)
        out["USD"]["weekly2_validation"]["start_value"]+=0.5
        with self.assertRaises(ValueError):
            validate(out,reference=self.current)

    def test_read_only_deterministic_and_no_legacy_data_changes(self):
        before=LIVE.read_bytes()
        r=run(candidate_path=LIVE,reference_path=LIVE)
        self.assertEqual(r["summary"]["verified_with_dated_2Y_and_10Y_weekly_receipts"],7)
        self.assertEqual(LIVE.read_bytes(),before)


if __name__=="__main__":unittest.main()
