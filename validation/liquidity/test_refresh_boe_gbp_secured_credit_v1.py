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
    parse,rows_from_csv,emit_js,run,existing_values,KNOWN,SERIES
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

if __name__=="__main__":unittest.main()
