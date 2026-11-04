#!/usr/bin/env python3
"""Offline adversarial tests for AUD same-row RBA F2 weekly research reading."""
from __future__ import annotations
import datetime as dt
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
path = ROOT/"validation/rates/refresh_fxv2_aud_rba_f2_context.py"
spec = importlib.util.spec_from_file_location("fxv2_aud_f2", path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
TODAY = dt.date(2026,11,4)
AUD = {"AUD":{"date":"2026-10-28","2Y":4.951,"10Y":5.208}}

def csv_fixture(pub="30-Oct-2026", two="4.951", ten="5.208", name="Australian Government 2 year bond",
                source="RBA", future_row=False):
    t=[[""]*4 for _ in range(11)]
    t[1][1]=name;t[1][2]="Australian Government 10 year bond"
    t[3][1]=t[3][2]="Daily"
    t[8][1]=t[8][2]=source
    t[9][1]=t[9][2]=pub
    t[10]=["Series ID",m.SERIES_2Y,m.SERIES_10Y,"DUMMY"]
    t += [["27-Oct-2026","4.946","5.201",""],["28-Oct-2026",two,ten,""]]
    if future_row:t.append(["05-Nov-2026","4.9","5.1",""])
    import csv,io
    f=io.StringIO()
    w=csv.writer(f);w.writerows(t)
    return f.getvalue().encode()+b" "*260

class AUDF2Test(unittest.TestCase):
    def test_same_day_official_csv(self):
        record=m.parse_f2(csv_fixture(),TODAY)
        self.assertEqual(record["as_of"],"2026-10-28")
        self.assertEqual(record["publication_date"],"2026-10-30")
        report=m.build(record,AUD,None,TODAY)
        self.assertEqual(report["status"],"OFFICIAL_F2_CSV_FETCHED_RESEARCH_ONLY")
        self.assertEqual(report["curve_bp"],25.7)
        self.assertEqual(report["next_regular_release_friday_sydney"],"2026-11-06")
        self.assertFalse(report["eligible_for_fx_pair_engine"])
        self.assertFalse(report["eligible_for_core"])
    def test_wrong_source_rejected(self):
        with self.assertRaises(ValueError):m.parse_f2(csv_fixture(source="UNVERIFIED"),TODAY)
    def test_wrong_series_header_rejected(self):
        with self.assertRaises(ValueError):m.parse_f2(csv_fixture(name="3 year"),TODAY)
    def test_future_observation_rejected(self):
        with self.assertRaises(ValueError):m.parse_f2(csv_fixture(future_row=True),TODAY)
    def test_future_publication_rejected(self):
        with self.assertRaises(ValueError):m.parse_f2(csv_fixture(pub="06-Nov-2026"),TODAY)
    def test_rollback_rejected(self):
        record=m.parse_f2(csv_fixture(),TODAY)
        prior=m.build(record,AUD,None,TODAY)
        record["as_of"]="2026-10-27"
        with self.assertRaises(ValueError):m.build(record,AUD,prior,TODAY)
    def test_canonical_must_not_be_older(self):
        record=m.parse_f2(csv_fixture(),TODAY)
        with self.assertRaises(ValueError):
            m.build(record,{"AUD":{"date":"2026-11-03"}},None,TODAY)
    def test_sydney_friday_schedule_not_observed_market_quote(self):
        self.assertEqual(m.next_friday(dt.date(2026,11,6)).isoformat(),"2026-11-06")
        self.assertEqual(m.next_friday(dt.date(2026,11,7)).isoformat(),"2026-11-13")

if __name__=="__main__":
    unittest.main()
