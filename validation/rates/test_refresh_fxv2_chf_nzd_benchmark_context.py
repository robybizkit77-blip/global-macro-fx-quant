#!/usr/bin/env python3
"""Adversarial offline tests: FX V2 CHF same-date spot / NZD benchmark roll guard."""
import copy
import datetime as dt
import importlib.util
import json
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[2]
SRC=ROOT/"validation/rates/refresh_fxv2_chf_nzd_benchmark_context.py"
spec=importlib.util.spec_from_file_location("fxv2_chf_nzd_context",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
TODAY=dt.date(2026,11,4)
BASE={"CHF":{"date":"2026-09-30","2Y":0.287,"10Y":0.586}}
SNB={
 "schema":"GMFQ_SNB_CHF_2Y_10Y_OFFICIAL_CANDIDATE_V1",
 "source_url":m.SNB_SOURCE,"filter":"D0(CHF),D1(2J,10J)",
 "changed_native_rates":False,"auto_promotion":False,
 "candidate":{"status":"REVIEWABLE_NEW_OFFICIAL_PAIR","source_as_of":"2026-10-30",
 "last_certified_as_of":"2026-09-30","2Y":0.238,"10Y":0.505,
 "curve_bp":26.7,"common_date_observations":26,"eligible_for_automatic_promotion":False},
}
WEB10={"schema":"GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1",
 "provenance":"SNB_PUBLIC_PAGE_DATED_EXACT_10Y",
 "eligible_for_curve_spreads":False,"has_current_2y":False,
 "as_of":"2026-11-03","value_percent":0.509,
 "source_url":"https://www.snb.ch/en/the-snb/mandates-goals/statistics/statistics-pub/current_interest_exchange_rates"}
RBNZ_OLD={
 "schema":"GMFQ_NZD_B2_LATEST_GOVT_HTML_RESEARCH_V1",
 "status":"SINGLE_OFFICIAL_RBNZ_HTML_TEXT_CAPTURE__INDEPENDENT_XLSX_REVIEW_PENDING",
 "source_url":"https://www.rbnz.govt.nz/en/statistics/series/exchange-and-interest-rates/wholesale-interest-rates",
 "latest_official_web_read_only":{"date":"2026-10-29","2Y":3.77,"10Y":4.87}
}
ROLL={"schema":"GMFQ_NZD_B2_OCT30_WEB_CONTEXT_V1","observed":"2026-10-30",
 "benchmark_roll_on_observation_date":True,"government_bond_2y":3.96,
 "government_bond_10y":4.9,"eligible_for_trading_signals":False}
NEW={"schema":"GMFQ_NZD_B2_GOVT_WEB_REVIEW_CONTEXT_V1",
 "status":"TWO_WEB_READS_MATCH__UNAPPROVED_RESEARCH_ONLY",
 "latest_official_web_context":{
  "status":"LATEST_INDICATIVE_CONTEXT_NOT_CANONICAL",
  "quality":"OFFICIAL_WEB_DISPLAY_RESEARCH_NOT_XLSX_RECONCILED",
  "guards":{"independent_xlsx_review_completed":False},
  "source_url":"https://www.rbnz.govt.nz/en/statistics/series/exchange-and-interest-rates/wholesale-interest-rates",
  "as_of":"2026-11-02","government_bond_2y_pct":3.97,
  "government_bond_10y_pct":4.91,"quoted_curve_bp":94,
  "benchmarks":{"roll_date":"2026-10-30","two_year_before":"May 2028",
   "two_year_from":"April 2029","ten_year_before":"May 2036",
   "ten_year_from":"April 2037"}
 }}
class TestChfNzdResearch(unittest.TestCase):
 def test_chf_same_date_official_candidate_remains_research(self):
  x=m.chf_context(SNB,WEB10,BASE,TODAY)
  self.assertEqual((x["paired_date"],x["2Y"],x["10Y"],x["curve_bp"]),
                   ("2026-10-30",.238,.505,26.7))
  self.assertEqual(x["separate_10y"]["as_of"],"2026-11-03")
  self.assertTrue(x["separate_10y"]["not_joinable_with_paired_2y"])
  self.assertFalse(x["eligible_for_pair_spreads"])
 def test_chf_cannot_join_10y_from_newer_date(self):
  x=m.chf_context(SNB,WEB10,BASE,TODAY)
  self.assertNotEqual(x["paired_date"],x["separate_10y"]["as_of"])
  self.assertEqual(x["10Y"],0.505)
 def test_chf_rejects_source_basis_drift(self):
  x=copy.deepcopy(SNB);x["candidate"]["last_certified_as_of"]="2026-09-29"
  with self.assertRaises(ValueError):m.chf_context(x,WEB10,BASE,TODAY)
 def test_chf_rejects_false_automatic_promotion(self):
  x=copy.deepcopy(SNB);x["candidate"]["eligible_for_automatic_promotion"]=True
  with self.assertRaises(ValueError):m.chf_context(x,WEB10,BASE,TODAY)
 def test_chf_rejects_old_pair(self):
  x=copy.deepcopy(SNB);x["candidate"]["source_as_of"]="2026-10-01"
  with self.assertRaises(ValueError):m.chf_context(x,WEB10,BASE,TODAY)
 def test_nzd_separates_benchmark_segments_and_computes_same_bond_change(self):
  x=m.nzd_context(RBNZ_OLD,ROLL,NEW,TODAY)
  self.assertEqual(x["before_roll"][0]["date"],"2026-10-29")
  self.assertEqual([a["date"] for a in x["after_roll"]],["2026-10-30","2026-11-02"])
  self.assertEqual(x["latest_curve_bp"],94)
  self.assertAlmostEqual(x["same_benchmark_change_bp"]["2Y"],1)
  self.assertAlmostEqual(x["same_benchmark_change_bp"]["10Y"],1)
  self.assertFalse(x["cross_roll_change_allowed"])
  self.assertFalse(x["independent_xlsx_reconciled"])
 def test_roll_missing_or_bad_benchmark_fails(self):
  x=copy.deepcopy(NEW);x["latest_official_web_context"]["benchmarks"]["ten_year_from"]="May 2036"
  with self.assertRaises(ValueError):m.nzd_context(RBNZ_OLD,ROLL,x,TODAY)
 def test_xlsx_not_approved_must_not_be_misrepresented(self):
  x=copy.deepcopy(NEW);x["latest_official_web_context"]["guards"]["independent_xlsx_review_completed"]=True
  with self.assertRaises(ValueError):m.nzd_context(RBNZ_OLD,ROLL,x,TODAY)
 def test_cross_roll_never_computed(self):
  x=m.nzd_context(RBNZ_OLD,ROLL,NEW,TODAY)
  # +19bp from 10/29 to 10/30 is a benchmark-change gap, NOT a policy repricing.
  self.assertEqual(round((x["after_roll"][0]["2Y"]-x["before_roll"][0]["2Y"])*100),19)
  self.assertFalse(x["cross_roll_change_allowed"])
 def test_feed_contains_no_core_permissions(self):
  a=m.chf_context(SNB,WEB10,BASE,TODAY);b=m.nzd_context(RBNZ_OLD,ROLL,NEW,TODAY)
  x=m.create_report(a,b,TODAY.isoformat())
  self.assertFalse(x["eligible_for_fx_pair_engine"])
  self.assertFalse(x["eligible_for_backtests"])
  self.assertTrue(x["canonical_government_rates_untouched"])
if __name__=="__main__":
 unittest.main()
