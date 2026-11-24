#!/usr/bin/env python3
"""RBA adjusted business credit growth: official-release semantics and isolation."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from validation.liquidity.refresh_rba_aud_business_credit_growth_v1 import (
    latest_release_from_archive, parse_release, parse_f7, existing_payload, emit_js, run, BASE
)

DAY=date(2026,11,14)
LINK=BASE+"/statistics/frequency/fin-agg/2026/fin-agg-0926.html"

def index():
    return """<html><body>
      <a href="fin-agg-0826.html">August 2026</a>
      <a href="fin-agg-0926.html">September 2026</a>
    </body></html>"""

def document(*,business="0.9,0.9,9.4,11.3",released="30 October 2026",
             disclaimer=True):
    cells="".join("<td>"+x+"</td>" for x in business.split(","))
    caution=("All growth rates for the financial aggregates are seasonally adjusted, "
       "and adjusted for the effects of breaks in the series. Data for the levels "
       "of financial aggregates are not adjusted for series breaks, and growth rates "
       "should not be calculated from data on the levels of credit.") if disclaimer else ""
    return f"""<html><body><h1>Financial Aggregates September 2026</h1>
      <p>Release date: {released}</p>
      <table><tr><th>Financial Aggregates</th><th>August</th>
      <th>September</th><th>Sep 2025</th><th>Sep 2026</th></tr>
      <tr><th>– Business(a)</th>{cells}</tr>
      <tr><th>– Housing</th><td>0.4</td><td>0.4</td>
      <td>6.3</td><td>7.0</td></tr></table>
      <p>{caution}</p></body></html>"""

class RBAAdjustedGrowthTest(unittest.TestCase):
    def test_official_month_link(self):
        x=latest_release_from_archive(index(),2026,today=DAY)
        self.assertEqual(x["period"],"2026-09")
        self.assertEqual(x["url"],LINK)

    def test_official_break_adjusted_not_stock(self):
        d=parse_release(document(),expected_period="2026-09",url=LINK,today=DAY)
        self.assertEqual(d["release_date"],"2026-10-30")
        self.assertEqual(d["monthly_growth_pct"],0.9)
        self.assertEqual(d["prior_month_growth_pct"],0.9)
        self.assertEqual(d["annual_growth_pct"],11.3)
        self.assertEqual(d["prior_year_growth_pct"],9.4)
        self.assertTrue(d["source_breaks_adjusted"])

    def test_wrong_content_or_issuer_caveat_withheld(self):
        with self.assertRaisesRegex(ValueError,"mandatory break-adjustment"):
            parse_release(document(disclaimer=False),expected_period="2026-09",url=LINK,today=DAY)
        with self.assertRaisesRegex(ValueError,"growth row"):
            parse_release(document(business="1.0,1.1"),expected_period="2026-09",url=LINK,today=DAY)

    def test_future_release_is_never_used(self):
        with self.assertRaisesRegex(ValueError,"future-dated"):
            parse_release(document(released="30 December 2026"),expected_period="2026-09",url=LINK,today=DAY)

    def test_no_duplicate_business_rows(self):
        duplicate=document().replace("</table>","<tr><th>Business</th><td>1.2</td><td>1.1</td><td>9.6</td><td>11.0</td></tr></table>")
        with self.assertRaisesRegex(ValueError,"uniquely"):
            parse_release(duplicate,expected_period="2026-09",url=LINK,today=DAY)

    def test_research_only_commit_boundary(self):
        d=parse_release(document(),expected_period="2026-09",url=LINK,today=DAY)
        js=emit_js(d,DAY.isoformat())
        self.assertIn('"eligible_for_fx_core": false',js)
        self.assertIn('"eligible_for_backtest": false',js)
        self.assertIn('"is_credit_stock": false',js)
        self.assertIn('"breaks_adjusted": true',js)
        with tempfile.TemporaryDirectory() as directory:
            a=Path(directory)/"index.html"
            b=Path(directory)/"release.html"
            dest=Path(directory)/"rba-adjusted.js"
            a.write_text(index(),encoding="utf-8")
            b.write_text(document(),encoding="utf-8")
            first=run(destination=dest,today=DAY,archive_fixture=a,release_fixture=b,apply=True)
            self.assertEqual(first["write_state"],"RESEARCH_SIDECAR_ONLY")
            self.assertTrue(dest.exists())
            second=run(destination=dest,today=DAY,archive_fixture=a,release_fixture=b,apply=True)
            self.assertEqual(second["status"],"NO_CHANGE")
            self.assertEqual(second["write_state"],"NO_MUTATION")


    def test_f7_loan_price_not_lending_standards(self):
        html="""<table><caption>Housing and Business Rates [a] September 2026</caption><tr><th>Loan purpose</th><th>Outstanding loans % per annum</th><th>New loans % per annum</th></tr><tr><th>Business (Table F7)</th></tr><tr><td>Small business</td><td>7.48</td><td>7.38</td></tr><tr><td>Medium business</td><td>6.30</td><td>6.27</td></tr><tr><td>Large business</td><td>5.85</td><td>5.71</td></tr></table>"""
        x=parse_f7(html,today=DAY)
        self.assertEqual(x["history"]["2026-09"]["small"]["new"],7.38)
        self.assertEqual(x["history"]["2026-09"]["large"]["outstanding"],5.85)
        self.assertEqual(x["proxy_kind"],"loan_price_not_lending_standards")
        for bad in (html.replace("New loans","Loans"),html.replace("7.38","38"),html.replace("Small business","Other business")):
            with self.assertRaises(ValueError):parse_f7(bad,today=DAY)
        with tempfile.TemporaryDirectory() as d:
            a,b,s,out=[Path(d)/n for n in ("index.html","release.html","f7.html","out.js")]
            a.write_text(index());b.write_text(document());s.write_text(html)
            args=dict(destination=out,today=DAY,archive_fixture=a,release_fixture=b,apply=True,f7_fixture=s)
            result=run(**args)
            self.assertEqual(result["f7"]["status"],"VERIFIED")
            self.assertEqual(existing_payload(out.read_text())["lending_rate_proxy"],x)
            self.assertEqual(run(**args)["status"],"NO_CHANGE")
            s.write_text("invalid")
            self.assertEqual(run(**args)["f7"]["status"],"WITHHELD")
            self.assertEqual(existing_payload(out.read_text())["lending_rate_proxy"],x)

if __name__=="__main__":unittest.main()
