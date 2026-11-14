#!/usr/bin/env python3
"""Deterministic ECB NFC credit stock source-contract tests; no HTTP in unit tests."""
import csv
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path
from validation.liquidity.refresh_ecb_eur_nfc_credit_v1 import (
    parse, emit_js, run, SERIES, ANCHOR_DATE, ANCHOR_VALUE, existing_observations
)
TODAY=date(2026,11,14)

def fixture(*,reversed_rows=False):
    months=[f"{y}-{m:02}" for y in (2025,2026) for m in range(1,13)
            if (y,m)>=(2025,1) and (y,m)<=(2026,9)]
    idx=months.index(ANCHOR_DATE)
    rows=[{"KEY":SERIES,"TIME_PERIOD":m,
           "OBS_VALUE":str(round(ANCHOR_VALUE+(i-idx)*11250,4)),
           "UNIT_MULT":"6","DECIMALS":"2"} for i,m in enumerate(months)]
    if reversed_rows:rows.reverse()
    b=io.StringIO()
    w=csv.DictWriter(b,fieldnames=["KEY","TIME_PERIOD","OBS_VALUE","UNIT_MULT","DECIMALS"])
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()

class ECBNFCSourceTest(unittest.TestCase):
    def test_official_series_and_month_end_stock(self):
        x=parse(fixture(),today=TODAY)
        self.assertEqual(x["latest_observation"],"2026-09")
        idx=x["dates"].index(ANCHOR_DATE)
        self.assertAlmostEqual(x["values"][idx],ANCHOR_VALUE,places=3)
        self.assertEqual(x["anchor_revision_pct"],0)
        self.assertEqual(len(x["dates"]),21)

    def test_ecb_can_return_newest_first(self):
        x=parse(fixture(reversed_rows=True),today=TODAY)
        self.assertEqual(x["latest_observation"],"2026-09")

    def test_strict_series_variant_and_units(self):
        with self.assertRaisesRegex(ValueError,"alternative ECB"):
            parse(fixture().replace(SERIES,"BSI.M.U2.Y.U.A20.A.1.U2.2240.Z01.E"),today=TODAY)
        with self.assertRaisesRegex(ValueError,"unit multiplier"):
            parse(fixture().replace(",6,2",",0,2"),today=TODAY)

    def test_revised_overlap_recorded_but_wrong_series_withheld(self):
        modified=fixture().replace(str(ANCHOR_VALUE),str(round(ANCHOR_VALUE*1.004,4)))
        x=parse(modified,today=TODAY)
        self.assertAlmostEqual(x["anchor_revision_pct"],.4,places=3)
        with self.assertRaisesRegex(ValueError,"diverges"):
            parse(fixture().replace(str(ANCHOR_VALUE),str(ANCHOR_VALUE*1.05)),today=TODAY)

    def test_gap_future_and_duplicate_are_not_published(self):
        rows=fixture().splitlines()
        gap="\n".join(x for x in rows if "2026-08" not in x)+"\n"
        with self.assertRaisesRegex(ValueError,"gap"):
            parse(gap,today=TODAY)
        with self.assertRaisesRegex(ValueError,"future"):
            parse(fixture(),today=date(2026,8,14))
        with self.assertRaisesRegex(ValueError,"duplicated"):
            parse(fixture()+rows[-1]+"\n",today=TODAY)

    def test_no_fx_core_writes_and_idempotence(self):
        x=parse(fixture(),today=TODAY)
        js=emit_js(x,TODAY.isoformat())
        self.assertIn('"first_release_pit_verified": false',js)
        self.assertIn('"eligible_for_fx_core": false',js)
        self.assertIn('"eligible_for_backtest": false',js)
        self.assertEqual(existing_observations(js),(x["dates"],x["values"]))
        with tempfile.TemporaryDirectory() as root:
            sample=Path(root)/"ecb.csv"
            dest=Path(root)/"ecb-research.js"
            sample.write_text(fixture(),encoding="utf-8")
            first=run(dest,apply=True,fixture=sample,today=TODAY)
            self.assertEqual(first["write_state"],"RESEARCH_SIDECAR_ONLY")
            self.assertTrue(dest.exists())
            repeated=run(dest,apply=True,fixture=sample,today=TODAY)
            self.assertEqual(repeated["status"],"NO_CHANGE")
            self.assertEqual(repeated["write_state"],"NO_MUTATION")

if __name__=="__main__":unittest.main()
