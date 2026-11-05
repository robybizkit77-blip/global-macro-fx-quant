#!/usr/bin/env python3
"""Dated-provenance regression: green job != fresh market quote."""
from __future__ import annotations
import copy
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from report_fxv2_chf_nzd_freshness_v1 import summarize

TODAY = dt.date(2026,11,5)
PREV = {
 "schema":"GMFQ_FXV2_CHF_NZD_BENCHMARK_RESEARCH_V1",
 "eligible_for_core":False, "eligible_for_fx_pair_engine":False,
 "eligible_for_backtests":False, "canonical_government_rates_untouched":True,
 "CHF":{"paired_date":"2026-10-30","2Y":.238,"10Y":.505},
 "NZD":{"latest_date":"2026-11-03","latest_2Y":3.95,"latest_10Y":4.88},
}
class SourceFreshnessContract(unittest.TestCase):
 def test_unchanged_workflow_must_report_unchanged_old_market_quotes(self):
  z=summarize(PREV,copy.deepcopy(PREV),TODAY,False,False)
  self.assertEqual(z["CHF"]["source_calendar_age_days"],6)
  self.assertEqual(z["NZD"]["source_calendar_age_days"],2)
  self.assertEqual(z["CHF"]["capture_result"],"RETAINED_PREVIOUS_DATED_OBSERVATION")
  self.assertEqual(z["NZD"]["capture_result"],"RETAINED_PREVIOUS_DATED_OBSERVATION")
  self.assertFalse(z["accepted_new_chf_date"])
  self.assertFalse(z["accepted_new_nzd_date"])
  self.assertIn("NO_NEW_RBNZ",z["NZD_source_access"])
  self.assertFalse(z["FX_pair_signals_modified"])
 def test_new_same_basis_date_and_new_RBNZ_source_are_distinct(self):
  newer=copy.deepcopy(PREV)
  newer["CHF"].update({"paired_date":"2026-11-04","2Y":.24,"10Y":.52})
  newer["NZD"].update({"latest_date":"2026-11-04","latest_2Y":3.94,"latest_10Y":4.85})
  z=summarize(PREV,newer,TODAY,True,False)
  self.assertTrue(z["accepted_new_chf_date"])
  self.assertTrue(z["accepted_new_nzd_date"])
  self.assertEqual(z["NZD_source_access"],"RBNZ_OFFICIAL_HTML_RESEARCH_READ")
 def test_revised_old_date_does_not_claim_new_date(self):
  updated=copy.deepcopy(PREV)
  updated["CHF"]["2Y"]=.239
  z=summarize(PREV,updated,TODAY,False,True)
  self.assertFalse(z["accepted_new_chf_date"])
  self.assertEqual(z["CHF"]["capture_result"],"REVISED_SAME_DATE_OBSERVATION")
  self.assertEqual(z["NZD_source_access"],"AUTHORIZED_RBNZ_REDISTRIBUTION_RESEARCH_READ")
 def test_source_rollback_future_and_core_promotion_rejected(self):
  for key,val in (("paired_date","2026-10-29"),("paired_date","2026-11-06")):
   x=copy.deepcopy(PREV);x["CHF"][key]=val
   with self.subTest(key=val),self.assertRaisesRegex(ValueError,"rollback|future"):
    summarize(PREV,x,TODAY,False,False)
  for flag in ("eligible_for_core","eligible_for_fx_pair_engine","eligible_for_backtests"):
   x=copy.deepcopy(PREV);x[flag]=True
   with self.subTest(flag=flag),self.assertRaisesRegex(ValueError,"scope"):
    summarize(PREV,x,TODAY,False,False)
 def test_same_date_official_and_vendor_candidate_not_merged(self):
  with self.assertRaisesRegex(ValueError,"competing"):
   summarize(PREV,PREV,TODAY,True,True)
 def test_bool_yield_rejected(self):
  x=copy.deepcopy(PREV);x["NZD"]["latest_2Y"]=True
  with self.assertRaisesRegex(ValueError,"malformed"):
   summarize(PREV,x,TODAY,False,False)

if __name__=="__main__":
 unittest.main()
