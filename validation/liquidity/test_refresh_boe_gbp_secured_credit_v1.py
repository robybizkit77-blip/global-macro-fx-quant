#!/usr/bin/env python3
"""Deterministic official IADB LPMVTYI GBP secured credit source-contract tests."""
import calendar
import csv
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path
from validation.liquidity.refresh_boe_gbp_secured_credit_v1 import (
    parse,rows_from_csv,emit_js,run,existing_values,existing_payload,parse_ccs,ccs_latest_url,KNOWN,SERIES
)
DAY=date(2026,11,14)

def fixture(*,reverse=False,date_style="iso",series=SERIES):
    lines=[]
    for year in range(2021,2027):
        for month in range(1,13):
            if (year,month)>(2026,9):break
            p=f"{year}-{month:02}"
            period=date(year,month,calendar.monthrange(year,month)[1])
            ds=(period.isoformat() if date_style=="iso" else period.strftime("%d %b %y"))
            value=KNOWN.get(p,round(2.5+0.04*(month%7),2))
            lines.append([ds,str(value)])
    if reverse:lines.reverse()
    txt=io.StringIO()
    w=csv.writer(txt)
    w.writerow(["DATE",series])
    w.writerows(lines)
    return txt.getvalue()

class GBPBoESecuredCreditTest(unittest.TestCase):
    def test_exact_official_series_monthly_yoy_not_stocks(self):
        x=parse(fixture(),today=DAY)
        self.assertEqual(x["last_observation"],"2026-09")
        self.assertEqual(x["dates"][-3:],["2026-07","2026-08","2026-09"])
        self.assertEqual(x["values"][-3:],[3.6,3.6,3.4])
        self.assertEqual(len(x["dates"]),48)
        self.assertEqual(x["official_july_overlap_revision_pp"],0)

    def test_boe_date_formats_and_reverse_rows(self):
        x=parse(fixture(reverse=True,date_style="english"),today=DAY)
        self.assertEqual(x["last_observation"],"2026-09")
        self.assertEqual(x["values"][-1],3.4)

    def test_incorrect_key_or_html_withheld(self):
        with self.assertRaisesRegex(ValueError,"exact secured lending code"):
            parse(fixture(series="LPMVTYE"),today=DAY)
        with self.assertRaisesRegex(ValueError,"HTML/error"):
            parse("<html><title>LPMVTYI</title></html>",today=DAY)

    def test_canonical_overlap_mismatch_withheld(self):
        s=fixture().replace("2026-07-31,3.6","2026-07-31,4.1")
        with self.assertRaisesRegex(ValueError,"source level or revision variant"):
            parse(s,today=DAY)

    def test_month_gap_duplicate_and_future_date_withheld(self):
        src=fixture()
        gap="\n".join(x for x in src.splitlines() if "2026-08-31" not in x)+"\n"
        with self.assertRaisesRegex(ValueError,"unexpected gap"):
            parse(gap,today=DAY)
        with self.assertRaisesRegex(ValueError,"duplicated month"):
            parse(src+"2026-09-30,3.4\n",today=DAY)
        with self.assertRaisesRegex(ValueError,"future"):
            parse(src,today=date(2026,8,14))

    def test_source_value_outliers_and_point_change_conservation(self):
        s=fixture().replace("2026-09-30,3.4","2026-09-30,33.4")
        with self.assertRaisesRegex(ValueError,"outside prudent range"):
            parse(s,today=DAY)
        x=parse(fixture(),today=DAY)
        self.assertAlmostEqual(x["values"][-1]-x["values"][-2],-0.2)
        output=emit_js(x,DAY.isoformat())
        self.assertIn('"eligible_for_fx_core": false',output)
        self.assertIn('"eligible_for_backtest": false',output)
        self.assertIn('"seasonally_adjusted": true',output)
        self.assertIn('"unit": "percent_yoy"',output)
        self.assertEqual(existing_values(output),(x["dates"],x["values"]))

    def test_initial_empty_research_placeholder_is_not_false_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/"boe.csv"
            sidecar=Path(temp)/"gbp-secured.js"
            source.write_text(fixture(),encoding="utf-8")
            sidecar.write_text("const data={dates:[],values:[]};",encoding="utf-8")
            receipt=run(destination=sidecar,fixture=source,today=DAY,apply=True)
            self.assertEqual(receipt["write_state"],"RESEARCH_SIDECAR_ONLY")
            self.assertEqual(receipt["latest_observation"],"2026-09")

    def test_apply_only_research_sidecar_and_idempotence(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/"boe.csv"
            sidecar=Path(temp)/"gbp-secured.js"
            source.write_text(fixture(),encoding="utf-8")
            first=run(destination=sidecar,fixture=source,today=DAY,apply=True)
            self.assertEqual(first["write_state"],"RESEARCH_SIDECAR_ONLY")
            self.assertEqual(first["latest_growth_yoy_pct"],3.4)
            self.assertTrue(sidecar.exists())
            second=run(destination=sidecar,fixture=source,today=DAY,apply=True)
            self.assertEqual(second["status"],"NO_CHANGE")
            self.assertEqual(second["write_state"],"NO_MUTATION")


    def test_ccs_actual_quarters_and_independent_retention(self):
        url="https://www.bankofengland.co.uk/credit-conditions-survey/2026/2026-q3"
        html="<table><tr><th>2025</th><th>2026</th></tr><tr><th></th><th>Q2</th><th>Q3</th><th>Q4</th><th>Q1</th><th>Q2</th><th>Q3</th></tr><tr><td rowspan='2'>How has the availability of credit provided to the corporate sector overall changed?</td><td>Past three months</td><td>7.9</td><td>7.7</td><td>3.5</td><td>3.0</td><td>0.0</td><td>-0.1</td></tr><tr><td>Next three months</td><td>9.1</td><td>7.1</td><td>2.7</td><td>2.3</td><td>-2.0</td><td>1.9</td></tr></table>"
        x=parse_ccs(html,url,today=DAY)
        self.assertEqual(x["dates"][-2:],["2026-Q2","2026-Q3"])
        self.assertEqual(x["values"][-2:],[0,-.1])
        self.assertEqual(ccs_latest_url('<a href="/credit-conditions-survey/2026/2026-q3">Q3</a>',DAY),url)
        for bad in (html.replace("Past three months","Next three months"),html.replace("0.0</td>","10.0</td>"),html.replace("corporate sector overall","small businesses")):
            with self.assertRaises(ValueError):parse_ccs(bad,url,today=DAY)
        with tempfile.TemporaryDirectory() as temp:
            f=Path(temp)/"mortgage.csv";s=Path(temp)/"survey.html";dest=Path(temp)/"out.js"
            f.write_text(fixture());s.write_text(html)
            args={"destination":dest,"fixture":f,"today":DAY,"apply":True}
            run(**args)
            before=existing_payload(dest.read_text())
            f.write_text("invalid mortgage")
            result=run(**args,ccs_fixture=s,ccs_url=url)
            self.assertEqual(result["ccs"]["status"],"VERIFIED")
            self.assertTrue(result["credit"]["status"].startswith("WITHHELD"))
            self.assertEqual(existing_payload(dest.read_text())["values"],before["values"])
            self.assertEqual(existing_payload(dest.read_text())["lending_conditions"],x)
            f.write_text(fixture())
            self.assertEqual(run(**args,ccs_fixture=s,ccs_url=url)["status"],"NO_CHANGE")
            s.write_text("invalid CCS")
            self.assertEqual(run(**args,ccs_fixture=s,ccs_url=url)["ccs"]["retained_observation"],"2026-Q3")

if __name__=="__main__":unittest.main()
