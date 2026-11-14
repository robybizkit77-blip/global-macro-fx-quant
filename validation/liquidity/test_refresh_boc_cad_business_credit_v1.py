#!/usr/bin/env python3
"""Deterministic tests; never contact live Bank of Canada during unit tests."""
import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from validation.liquidity.refresh_boc_cad_business_credit_v1 import (
    parse, emit_js, existing_observations, run, DEST, INITIAL_OBSERVED
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
        self.assertEqual(existing_observations(current),(
            p["dates"],[int(x) for x in p["values"]]))
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

if __name__=="__main__":unittest.main()
