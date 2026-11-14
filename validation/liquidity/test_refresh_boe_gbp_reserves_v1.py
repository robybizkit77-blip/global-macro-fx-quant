#!/usr/bin/env python3
"""Official BoE weekly reserves source, publication date, and research isolation."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from validation.liquidity.refresh_boe_gbp_reserves_v1 import (
    latest_link,parse_report,emit_js,previous,run,INDEX,ANCHOR_DATE,ANCHOR_VALUE
)
DAY=date(2026,11,14)
LATEST="https://www.bankofengland.co.uk/weekly-report/2026/11-november-2026"

def index():
    return """<html><body>
      <h1>Bank of England balance sheet and weekly report</h1>
      <a href="/weekly-report/2026/11-november-2026">Weekly report 12 November 2026</a>
      <a href="/weekly-report/2026/4-november-2026">Weekly report 05 November 2026</a>
      <a href="https://example.com/weekly-report/2099/1-january-2099">untrusted site</a>
      </body></html>"""

def weekly_report(*,amount="646,280",previous_balance="641,005",
                  published="12 November 2026",current_date="11 November 2026",
                  prev_date="04 November 2026",unit="£mn",label="Reserves balances"):
    return f"""<!doctype html><html><body>
      <p>Published on {published}</p>
      <h2>Weekly report</h2>
      <table><thead><tr><td></td><th>{current_date}</th><th>{prev_date}</th></tr></thead>
      <tbody><tr><th>{unit}</th><td>{unit}</td><td>{unit}</td></tr>
      <tr><th>Sterling Liabilities</th><td></td><td></td></tr>
      <tr><th>{label}</th><td>{amount}</td><td>{previous_balance}</td></tr>
      <tr><th>Notes in circulation</th><td>100,490</td><td>100,130</td></tr>
      </tbody></table></body></html>"""

class BoEGBPReservesTest(unittest.TestCase):
    def test_find_latest_official_release(self):
        d,url=latest_link(index(),today=DAY)
        self.assertEqual(d.isoformat(),"2026-11-11")
        self.assertEqual(url,LATEST)

    def test_published_and_prior_directly_reported(self):
        d=parse_report(weekly_report(),date(2026,11,11),LATEST,today=DAY)
        self.assertEqual(d["source_period"],"2026-11-11")
        self.assertEqual(d["previous_period"],"2026-11-04")
        self.assertEqual(d["published_on"],"2026-11-12")
        self.assertEqual(d["latest_balance_million_gbp"],646280)
        self.assertEqual(d["previous_balance_million_gbp"],641005)
        self.assertEqual(d["weekly_change_million_gbp"],5275)

    def test_failure_if_source_or_header_does_not_match(self):
        with self.assertRaisesRegex(ValueError,"issuer"):
            latest_link('<html><a href="https://untrusted.example/a">x</a></html>',today=DAY)
        with self.assertRaisesRegex(ValueError,"official report header"):
            parse_report(weekly_report(current_date="10 November 2026"),date(2026,11,11),LATEST,today=DAY)
        with self.assertRaisesRegex(ValueError,"prior Wednesday"):
            parse_report(weekly_report(prev_date="03 November 2026"),date(2026,11,11),LATEST,today=DAY)

    def test_future_old_and_bad_issuer_values_withheld(self):
        with self.assertRaisesRegex(ValueError,"publication timing"):
            parse_report(weekly_report(published="16 November 2026"),date(2026,11,11),LATEST,today=DAY)
        with self.assertRaisesRegex(ValueError,"reserve liability row"):
            parse_report(weekly_report(label="Notes on issue"),date(2026,11,11),LATEST,today=DAY)
        with self.assertRaisesRegex(ValueError,"sterling millions unit"):
            parse_report(weekly_report(unit="USD billion"),date(2026,11,11),LATEST,today=DAY)
        with self.assertRaisesRegex(ValueError,"plausible BoE"):
            parse_report(weekly_report(amount="1,200"),date(2026,11,11),LATEST,today=DAY)

    def test_no_unapproved_core_or_fx_write(self):
        obj=parse_report(weekly_report(),date(2026,11,11),LATEST,today=DAY)
        js=emit_js(obj,DAY.isoformat())
        self.assertEqual(previous(js),{k:obj[k] for k in (
            "source_period","latest_balance_million_gbp",
            "previous_balance_million_gbp","weekly_change_million_gbp")})
        self.assertIn('"value_canonical_overlap": 638012',js)
        self.assertIn('"asof_canonical_overlap": "2026-09-16"',js)
        self.assertIn('"eligible_for_fx_core": false',js)
        self.assertIn('"eligible_for_backtest": false',js)
        with tempfile.TemporaryDirectory() as root:
            ix=Path(root)/"index.html"
            source=Path(root)/"report.html"
            out=Path(root)/"gbp-source.js"
            ix.write_text(index(),encoding="utf-8")
            source.write_text(weekly_report(),encoding="utf-8")
            a=run(destination=out,index_fixture=ix,report_fixture=source,
                  today=DAY,apply=True)
            self.assertEqual(a["write_state"],"RESEARCH_SIDECAR_ONLY")
            self.assertTrue(out.exists())
            again=run(destination=out,index_fixture=ix,report_fixture=source,
                      today=DAY,apply=True)
            self.assertEqual(again["status"],"NO_CHANGE")
            self.assertEqual(again["write_state"],"NO_MUTATION")

if __name__=="__main__":unittest.main()
