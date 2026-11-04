#!/usr/bin/env python3
"""Offline RBNZ B2 parser: wrong tenor, future, bond roll and anti-rollback fixtures."""
import datetime as dt
import importlib.util
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("rbnz_b2_live",ROOT/"validation/rates/collect_rbnz_b2_daily_web_v1.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
NZ=ZoneInfo("Pacific/Auckland")
NOW=dt.datetime(2026,11,4,17,0,tzinfo=NZ)

def fixture(*,release="04 November 2026",roll="2 November 2026",
            d2="3.95",d10="4.88",h2="2 year",h10="10 year",
            future=False,missing_bond=False):
    hdr=["Date","Official Cash Rate (OCR)","Overnight Deposit Rate",
         "Overnight Reverse Repurchase Facility Rate","Overnight interbank cash rate",
         "30 days","60 days","90 days","1 year",h2,"5 year",h10,"2-10s"]
    rr=[["30 Oct 2026","2.75","2.75","3.25","2.81","2.93","3.05","3.16","3.72","3.96","4.28","4.90","62"],
        ["02 Nov 2026","2.75","2.75","3.25","-","2.92","3.03","3.15","3.73","3.97","4.29","4.91","63"],
        ["03 Nov 2026","2.75","2.75","3.25","-","2.91","3.03","3.14","3.71",d2,"4.27",d10,"62"]]
    if future:rr.append(["05 Nov 2026","2.75","2.75","3.25","-","2.9","3.0","3.1","3.7","3.9","4.2","4.8","60"])
    th=lambda cells:"<tr>"+"".join("<th>"+x+"</th>" for x in cells)+"</tr>"
    td=lambda cells:"<tr>"+"".join("<td>"+x+"</td>" for x in cells)+"</tr>"
    bond="May 2028 to the April 2029 bond; May 2036 to the April 2037 bond"
    if missing_bond: bond="May 2028 to the August 2030 bond"
    return (
      "<html><body><h1>Wholesale interest rates (B2)</h1><p>Released: "+release+
      "</p><div>Secondary market government bond closing yields</div>"+
      "<table>"+th(hdr)+"".join(td(row) for row in rr)+"</table>"+
      "<h3>Changes to the 1, 2 and 10-year bond benchmarks</h3><p>"+roll+"</p><p>"+
      bond+"</p></body></html>"
    )

class OfficialPublicHTML(unittest.TestCase):
    def test_proven_source_and_exact_3nov(self):
        x=m.parse(fixture(),now_nz=NOW)
        self.assertEqual((x["as_of"],x["2Y"],x["10Y"],x["curve_bp"]),
                         ("2026-11-03",3.95,4.88,93))
        self.assertEqual(x["release_date"],"2026-11-04")
        self.assertEqual(x["benchmark_roll_date"],"2026-10-30")
        self.assertFalse(x["eligible_for_core"])
        self.assertFalse(x["independent_xlsx_reconciled"])
        self.assertEqual(len(x["post_roll_table_rows"]),3)
    def test_no_swap_spread_misread(self):
        self.assertEqual(m.parse(fixture(),now_nz=NOW)["10Y"],4.88)
    def test_wrong_government_tenors_rejected(self):
        with self.assertRaises(ValueError):
            m.parse(fixture(h2="3 year"),now_nz=NOW)
    def test_bond_roll_guard(self):
        with self.assertRaises(ValueError):
            m.parse(fixture(missing_bond=True),now_nz=NOW)
        with self.assertRaises(ValueError):
            m.parse(fixture(roll="05 November 2026"),now_nz=NOW)
    def test_future_publication(self):
        with self.assertRaises(ValueError):
            m.parse(fixture(release="05 November 2026"),now_nz=NOW)
    def test_future_benchmark_row(self):
        with self.assertRaises(ValueError):
            m.parse(fixture(future=True),now_nz=NOW)
    def test_missing_table_fails_closed(self):
        with self.assertRaises(ValueError):
            m.parse(fixture().replace("<table>","<div>").replace("</table>","</div>"),now_nz=NOW)
    def test_no_invented_values(self):
        with self.assertRaises(ValueError):
            m.parse(fixture(d2="—"),now_nz=NOW) if False else m.parse(
              fixture().replace(">03 Nov 2026<",">31 Oct 2026<")
              .replace(">30 Oct 2026<",">31 Oct 2026<"),now_nz=NOW)

if __name__=="__main__":
    unittest.main()
