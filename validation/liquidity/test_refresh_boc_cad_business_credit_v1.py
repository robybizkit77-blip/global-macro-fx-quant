#!/usr/bin/env python3
"""Deterministic tests; never contact live Bank of Canada during unit tests."""
import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from validation.liquidity.refresh_boc_cad_business_credit_v1 import (
    parse, parse_lynx, parse_slos, existing_payload, emit_js, existing_observations, run, DEST, INITIAL_OBSERVED
)
DAY=date(2026,11,14)

def raw():
    return {"observations":[
       {"d":day+"-01","V122667770":{"v":str(value)}}
       for day,value in INITIAL_OBSERVED.items()
    ]}

class BoCCreditResearchTest(unittest.TestCase):
    def test_verified_current_issuer_snapshot(self):
        p=parse(raw(),today=DAY)
        self.assertEqual(p["latest_observation"],"2026-08")
        self.assertEqual(p["values"][-1],944614)
        self.assertFalse(p["revised_august_2026"])

    def test_reverse_chronology_official_valet_response(self):
        x=raw()
        x["observations"].reverse()
        p=parse(x,today=DAY)
        self.assertEqual(p["dates"][-1],"2026-08")
        self.assertEqual(p["values"][-1],944614)

    def test_issuer_revision_under_overlap_guard(self):
        x=raw();x["observations"][-1]["V122667770"]["v"]="945500"
        p=parse(x,today=DAY)
        self.assertTrue(p["revised_august_2026"])

    def test_large_revision_withheld(self):
        x=raw();x["observations"][-1]["V122667770"]["v"]="1000000"
        with self.assertRaisesRegex(ValueError,"August.*mismatch"):
            parse(x,today=DAY)

    def test_incorrect_key_and_outlier_withheld(self):
        x=raw();x["observations"][-1]["V122667770"]={"v":"200000"}
        with self.assertRaisesRegex(ValueError,"stock bounds"):parse(x,today=DAY)
        x=raw();x["observations"][-1]={"d":"2026-08-01","OTHER_KEY":{"v":"944614"}}
        with self.assertRaisesRegex(ValueError,"overlap"):parse(x,today=DAY)

    def test_missing_month_or_duplicate_withheld(self):
        x=raw();x["observations"].pop(2)
        with self.assertRaisesRegex(ValueError,"nonconsecutive"):parse(x,today=DAY)
        x=raw();x["observations"].append(copy.deepcopy(x["observations"][-1]))
        with self.assertRaisesRegex(ValueError,"duplicate"):parse(x,today=DAY)

    def test_future_period_withheld(self):
        x=raw();x["observations"].append({"d":"2026-12-01","V122667770":{"v":"947000"}})
        with self.assertRaisesRegex(ValueError,"future-period"):parse(x,today=DAY)

    def test_source_change_without_unsafe_core_effect(self):
        p=parse(raw(),today=DAY)
        emitted=emit_js(p,DAY.isoformat())
        self.assertIn('"first_release_pit_verified": false',emitted)
        self.assertIn('"eligible_for_fx_core": false',emitted)
        self.assertIn('"eligible_for_backtest": false',emitted)
        self.assertEqual(existing_observations(emitted),(
            p["dates"],p["values"]))
        current=DEST.read_text(encoding="utf-8")
        current_rows=existing_observations(current)
        self.assertIsNotNone(current_rows)
        self.assertIn("2026-08",current_rows[0])
        observed=current_rows[1][current_rows[0].index("2026-08")]
        self.assertLess(abs(observed-944614)/944614,0.03)
        with tempfile.TemporaryDirectory() as temp:
            fixture=Path(temp)/"issuer.json"
            fixture.write_text(json.dumps(raw()),encoding="utf-8")
            out=Path(temp)/"cad-research.js"
            proof=run(out,apply=True,fixture=fixture,today=DAY)
            self.assertEqual(proof["write_state"],"RESEARCH_SIDECAR_ONLY")
            self.assertTrue(out.exists())
            none=run(out,apply=True,fixture=fixture,today=DAY)
            self.assertEqual(none["status"],"NO_CHANGE")
            self.assertEqual(none["write_state"],"NO_MUTATION")


    def test_lynx_source_and_independent_update(self):
        page="<table><tr><th>Millions of dollars</th><th>2026‑11‑12</th><th>2026‑11‑13</th><th>2026‑11‑16</th></tr><tr><th>Total settlement balances</th><td>70,902</td><td>75,275</td><td></td></tr><tr><th>Amount in Lynx</th><td>70,900</td><td>75,273</td><td></td></tr><tr><th>Amount in Real-Time Rail (RTR)</th><td>2</td><td>2</td><td></td></tr></table>"
        x=parse_lynx(page,today=DAY)
        self.assertEqual(x["dates"],["2026-11-12","2026-11-13"])
        self.assertEqual(x["values"],[70900,75273])
        self.assertFalse(x["canonical_monthly_equivalence_verified"])
        for bad in (page.replace("Amount in Lynx","Target in Lynx"),page.replace("75,275","75,200"),page.replace("Millions of dollars","Billions of dollars")):
            with self.assertRaises(ValueError):parse_lynx(bad,today=DAY)
        with tempfile.TemporaryDirectory() as temp:
            f=Path(temp)/"credit.json";l=Path(temp)/"lynx.html";dest=Path(temp)/"out.js"
            f.write_text(json.dumps(raw()));l.write_text(page)
            run(dest,apply=True,fixture=f,today=DAY)
            before=existing_payload(dest.read_text())
            f.write_text("invalid credit")
            args={"apply":True,"fixture":f,"lynx_fixture":l,"today":DAY}
            result=run(dest,**args)
            self.assertEqual(result["lynx"]["status"],"VERIFIED")
            self.assertTrue(result["credit"]["status"].startswith("WITHHELD"))
            after=existing_payload(dest.read_text())
            self.assertEqual(after["values"],before["values"])
            self.assertEqual(after["settlement_balances"],x)
            f.write_text(json.dumps(raw()))
            self.assertEqual(run(dest,**args)["status"],"NO_CHANGE")
            l.write_text("invalid Lynx")
            self.assertEqual(run(dest,**args)["lynx"]["retained_observation"],"2026-11-13")


    def test_slos_exact_series_and_independent_retention(self):
        day=date(2026,11,24)
        payload={"seriesDetail":{"SLOS_BUS_LEND":{"label":"Overall business lending conditions","dateFormat":"quarterly"}},
                 "observations":[{"d":d,"SLOS_BUS_LEND":{"v":str(v)}} for d,v in
                    [("2025-10-01",2.81),("2026-01-01",0.96),("2026-04-01",-1.04),("2026-07-01",-6.48)]]}
        x=parse_slos(payload,today=day)
        self.assertEqual(x["values"][-2:],[-1.04,-6.48])
        self.assertEqual(x["negative_means"],"easing")
        self.assertEqual(x["positive_means"],"tightening")
        for bad in ("label","gap","future","anchor"):
            y=copy.deepcopy(payload)
            if bad=="label":y["seriesDetail"]["SLOS_BUS_LEND"]["label"]="Business price lending conditions"
            elif bad=="gap":y["observations"].pop(1)
            elif bad=="future":y["observations"].append({"d":"2026-10-01","SLOS_BUS_LEND":{"v":"0"}})
            else:y["observations"][2]["SLOS_BUS_LEND"]["v"]="20"
            with self.assertRaises(ValueError):parse_slos(y,today=day)
        with tempfile.TemporaryDirectory() as temp:
            f=Path(temp)/"credit.json";s=Path(temp)/"slos.json";dest=Path(temp)/"out.js"
            f.write_text(json.dumps(raw()));s.write_text(json.dumps(payload))
            run(dest,apply=True,fixture=f,today=day)
            before=existing_payload(dest.read_text())
            f.write_text("invalid credit")
            args={"apply":True,"fixture":f,"slos_fixture":s,"today":day}
            receipt=run(dest,**args)
            self.assertEqual(receipt["slos"]["status"],"VERIFIED")
            self.assertTrue(receipt["credit"]["status"].startswith("WITHHELD"))
            after=existing_payload(dest.read_text())
            self.assertEqual(after["values"],before["values"])
            self.assertEqual(after["lending_conditions"],x)
            f.write_text(json.dumps(raw()))
            self.assertEqual(run(dest,**args)["status"],"NO_CHANGE")
            s.write_text("invalid SLOS")
            self.assertEqual(run(dest,**args)["slos"]["retained_observation"],"2026-07-01")

if __name__=="__main__":unittest.main()
