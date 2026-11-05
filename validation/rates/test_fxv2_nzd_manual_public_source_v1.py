#!/usr/bin/env python3
"""Validate dated, manually reviewed public RBNZ B2 research, no web access.

A dated public research observation can be supplied from review of the
public release, but is NOT a runner download, a Core promotion, or XLSX PIT.
The reviewed Nov4 row is independent of the Oct30 benchmark transition.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "site/fx-quant-v2/chf-nzd-benchmark-research.json"
G8 = ROOT / "live_data/sections/NATIVE_RATES_DATA.json"


class NZDPublicResearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=json.loads(RESEARCH.read_text())
        cls.row=cls.report["NZD"]

    def test_same_benchmark_post_roll_observations(self):
        r=self.row
        self.assertEqual(r["roll_date"],"2026-10-30")
        self.assertEqual(r["new_benchmark"],{"2Y":"April 2029","10Y":"April 2037"})
        self.assertEqual(r["old_benchmark"],{"2Y":"May 2028","10Y":"May 2036"})
        self.assertFalse(r["cross_roll_change_allowed"])
        after=r["after_roll"]
        self.assertEqual(after[0],{"date":"2026-10-30","2Y":3.96,"10Y":4.9})
        self.assertGreaterEqual(len(after),2)
        ds=[dt.date.fromisoformat(x["date"]) for x in after]
        self.assertEqual(ds,sorted(set(ds)))
        self.assertEqual(after[-1]["date"],r["latest_date"])
        self.assertEqual(after[-1]["2Y"],r["latest_2Y"])
        self.assertEqual(after[-1]["10Y"],r["latest_10Y"])
        self.assertGreaterEqual(ds[-1],dt.date(2026,11,4))
        self.assertEqual(round((r["latest_10Y"]-r["latest_2Y"])*100,1),
                         r["latest_curve_bp"])
        delta=r["same_benchmark_change_bp"]
        self.assertEqual(delta["start"],after[0]["date"])
        self.assertEqual(delta["end"],after[-1]["date"])
        for tenor,key in (("2Y","latest_2Y"),("10Y","latest_10Y")):
            self.assertTrue(math.isfinite(r[key]))
            self.assertAlmostEqual(delta[tenor],
                                   round((r[key]-after[0][tenor])*100,1))
        if r["latest_date"]=="2026-11-04":
            self.assertEqual((r["latest_2Y"],r["latest_10Y"]),(3.83,4.81))
            self.assertEqual(r["source_release_date"],"2026-11-05")

    def test_not_an_automated_download_or_official_core_promotion(self):
        r=self.row
        self.assertEqual(r["source_capture_method"],
                         "OFFICIAL_WEB_PAGE_RESEARCH_CAPTURE_NOT_GITHUB_DOWNLOAD")
        self.assertTrue(r["source_url"].startswith("https://www.rbnz.govt.nz/"))
        self.assertEqual(r.get("source_release_date_quality"),
                         "OFFICIAL_RBNZ_PUBLIC_PAGE_DATE")
        self.assertGreaterEqual(dt.date.fromisoformat(r["source_release_date"]),
                                dt.date.fromisoformat(r["latest_date"]))
        self.assertFalse(r["independent_xlsx_reconciled"])
        for key in ("eligible_for_core","eligible_for_pair_spreads",
                    "eligible_for_backtests","eligible_for_automatic_promotion"):
            self.assertIs(r[key],False,key)
        self.assertIs(self.report["eligible_for_fx_pair_engine"],False)
        self.assertIs(self.report["canonical_government_rates_untouched"],True)

    def test_source_permission_gate_is_active(self):
        workflow=(ROOT/".github/workflows/fxv2-chf-nzd-benchmark-research.yml").read_text()
        self.assertIn("secrets.RBNZ_AUTOMATED_ACCESS_AUTHORIZED",workflow)
        self.assertIn('if [ "${RBNZ_AUTOMATED_ACCESS_AUTHORIZED:-}" != "true" ]; then',
                      workflow)
        self.assertIn("NZD_RBNZ_DIRECT=SKIPPED_NO_AUTOMATED_ACCESS_PERMISSION",workflow)
        self.assertIn("EOLAS_API_KEY",workflow)
        self.assertIn("test_fxv2_nzd_manual_public_source_v1.py",workflow)

    def test_canonical_nzd_not_confused_with_research(self):
        core=json.loads(G8.read_text())
        self.assertGreaterEqual(dt.date.fromisoformat(self.row["latest_date"]),
                                dt.date.fromisoformat(core["NZD"]["date"]))
        self.assertNotIn("eligible_for_fx_engine",self.row)

if __name__=="__main__":
    unittest.main()
