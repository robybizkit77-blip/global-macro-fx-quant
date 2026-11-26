#!/usr/bin/env python3
"""Deterministic ECB NFC credit stock source-contract tests; no HTTP in unit tests."""
import csv
import io
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from validation.liquidity.refresh_ecb_eur_nfc_credit_v1 import (
    parse, parse_excess_liquidity, existing_payload, EXLIQ_SERIES, emit_js, run, SERIES, ANCHOR_DATE, ANCHOR_VALUE, existing_observations
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
        original=str(round(ANCHOR_VALUE,4))
        modified=fixture().replace(original,str(round(ANCHOR_VALUE*1.004,4)))
        x=parse(modified,today=TODAY)
        self.assertAlmostEqual(x["anchor_revision_pct"],.4,places=3)
        with self.assertRaisesRegex(ValueError,"diverges"):
            parse(fixture().replace(original,str(round(ANCHOR_VALUE*1.05,4))),today=TODAY)

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


    def test_monthly_rollback_does_not_overwrite_newer_sidecar(self):
        with tempfile.TemporaryDirectory() as root:
            f=Path(root)/"nfc.csv";dest=Path(root)/"research.js"
            f.write_text(fixture());run(dest,apply=True,fixture=f,today=TODAY)
            before=dest.read_bytes()
            f.write_text("\n".join(x for x in fixture().splitlines() if "2026-09" not in x)+"\n")
            with self.assertRaisesRegex(ValueError,"rolled back"):
                run(dest,apply=True,fixture=f,today=TODAY)
            self.assertEqual(dest.read_bytes(),before)

    def test_daily_liquidity_isolation_and_retention(self):
        start=date(2026,9,1)
        days=[start+timedelta(days=i) for i in range(74)]
        rows=["KEY,TIME_PERIOD,OBS_VALUE,UNIT_MULT"]+[f"{EXLIQ_SERIES},{d.isoformat()},{2123137+(i-20)*1000},6" for i,d in enumerate(days)]
        raw="\n".join(rows)+"\n"
        x=parse_excess_liquidity(raw,today=TODAY)
        self.assertEqual(x["latest_observation"],"2026-11-13")
        self.assertEqual(x["values"][-1],2176137)
        for bad in (raw.replace(EXLIQ_SERIES,"ILM.D.U2.C.OTHER.U2.EUR"),
                    raw.replace(",6\n",",3\n"),raw+rows[-1]+"\n",
                    raw.replace("2026-09-21,2123137","2026-09-21,3000000")):
            with self.assertRaises(ValueError):parse_excess_liquidity(bad,today=TODAY)
        with tempfile.TemporaryDirectory() as root:
            f=Path(root)/"nfc.csv";e=Path(root)/"exliq.csv";dest=Path(root)/"research.js"
            f.write_text(fixture());e.write_text(raw)
            run(dest,apply=True,fixture=f,today=TODAY)
            before=existing_payload(dest.read_text())
            f.write_text("invalid NFC")
            args={"apply":True,"fixture":f,"exliq_fixture":e,"today":TODAY}
            result=run(dest,**args)
            self.assertEqual(result["excess_liquidity"]["status"],"VERIFIED")
            self.assertTrue(result["nfc"]["status"].startswith("WITHHELD"))
            after=existing_payload(dest.read_text())
            self.assertEqual(after["values"],before["values"])
            self.assertEqual(after["excess_liquidity"],x)
            f.write_text(fixture())
            self.assertEqual(run(dest,**args)["status"],"NO_CHANGE")
            e.write_text("invalid daily liquidity")
            self.assertEqual(run(dest,**args)["excess_liquidity"]["retained_observation"],"2026-11-13")

    def test_bls_reference_period_retention_and_idempotence(self):
        from validation.liquidity.refresh_ecb_eur_nfc_credit_v1 import parse_bls
        from validation.liquidity.probe_ecb_eur_bls_actual_v1 import KEY
        rows=["KEY,TIME_PERIOD,OBS_VALUE"]
        for y in range(2016,2027):
            for q in range(1,5):
                value=7 if (y,q)==(2026,3) else 8.55 if (y,q)==(2026,4) else 0
                rows.append(f"{KEY},{y}-Q{q},{value}")
        raw="\n".join(rows)+"\n"
        x=parse_bls(raw,today=TODAY)
        self.assertEqual(x["latest_observation"],"2026-Q3")
        self.assertEqual(x["publication_quarters"][-1],"2026-Q4")
        self.assertEqual(x["values"][-1],8.55)
        with self.assertRaises(ValueError):
            parse_bls(raw.replace(KEY,"WRONG"),today=TODAY)
        with tempfile.TemporaryDirectory() as root:
            f=Path(root)/"nfc.csv";b=Path(root)/"bls.csv";dest=Path(root)/"research.js"
            f.write_text(fixture());b.write_text(raw)
            args=dict(apply=True,fixture=f,bls_fixture=b,today=TODAY)
            self.assertEqual(run(dest,**args)["write_state"],"RESEARCH_SIDECAR_ONLY")
            self.assertEqual(existing_payload(dest.read_text())["lending_conditions"],x)
            self.assertEqual(run(dest,**args)["status"],"NO_CHANGE")
            b.write_text("invalid")
            result=run(dest,**args)
            self.assertEqual(result["lending_conditions"]["retained_observation"],"2026-Q3")
            self.assertEqual(existing_payload(dest.read_text())["lending_conditions"],x)

if __name__=="__main__":unittest.main()
