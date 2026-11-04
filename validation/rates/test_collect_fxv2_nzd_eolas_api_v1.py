#!/usr/bin/env python3
"""Offline tests for authorized eolas B2 daily redistribution, without API key."""
import copy
import datetime as dt
import importlib.util
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("eolas_reader",ROOT/"validation/rates/collect_fxv2_nzd_eolas_api_v1.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
NOW=dt.datetime(2026,11,4,17,0,tzinfo=ZoneInfo("Pacific/Auckland"))
def row(date,y2,y10):
    return {"date":date,m.TWO:y2,m.TEN:y10,m.TWO_BOND:y2,m.TEN_BOND:y10}

ROWS=[row("2026-10-30",3.96,4.9),row("2026-11-02",3.97,4.91),row("2026-11-03",3.95,4.88)]

class AuthorizedEolasReader(unittest.TestCase):
    def test_post_roll_same_bond_yields(self):
        x=m.parse(copy.deepcopy(ROWS),now_nz=NOW)
        self.assertEqual((x["as_of"],x["2Y"],x["10Y"]),("2026-11-03",3.95,4.88))
        self.assertEqual(x["curve_bp"],93)
        self.assertEqual(x["provider"],"eolas")
        self.assertTrue(x["third_party_redistribution"])
        self.assertFalse(x["official_html_observed"])
        self.assertFalse(x["independent_xlsx_reconciled"])
        self.assertFalse(x["eligible_for_core"])
        self.assertEqual(x["release_date_quality"],"UNVERIFIED_PROVIDER_AS_OF_ONLY")
    def test_wrong_roll_bond_rejected(self):
        rs=copy.deepcopy(ROWS);rs[-1][m.TWO_BOND]=3.77
        with self.assertRaises(ValueError): m.parse(rs,now_nz=NOW)
    def test_wrong_10y_bond_rejected(self):
        rs=copy.deepcopy(ROWS);rs[-1][m.TEN_BOND]=4.99
        with self.assertRaises(ValueError): m.parse(rs,now_nz=NOW)
    def test_cannot_trick_with_unrelated_swap(self):
        rs=copy.deepcopy(ROWS);rs[-1][m.TEN]=None
        rs[-1]["swap_rates_close_10_year"]=4.88
        with self.assertRaises(ValueError): m.parse(rs,now_nz=NOW)
    def test_no_schema_alternatives_or_future(self):
        with self.assertRaises(ValueError):m.parse({"data":ROWS},now_nz=NOW)
        rs=copy.deepcopy(ROWS);rs[-1]["date"]="2026-11-05"
        with self.assertRaises(ValueError):m.parse(rs,now_nz=NOW)
    def test_missing_post_roll_anchor_rejected(self):
        with self.assertRaises(ValueError):m.parse(ROWS[1:],now_nz=NOW)
    def test_duplicate_market_row_rejected(self):
        with self.assertRaises(ValueError):m.parse(ROWS+[ROWS[-1]],now_nz=NOW)
    def test_old_provider_rejected(self):
        with self.assertRaises(ValueError):
            m.parse(ROWS,now_nz=dt.datetime(2026,12,1,12,tzinfo=ZoneInfo("Pacific/Auckland")))

if __name__=="__main__":
    unittest.main()
