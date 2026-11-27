#!/usr/bin/env python3
"""Offline source guards for RBA ES balances, weekly vs daily A3, Core isolation."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from validation.liquidity.refresh_rba_aud_es_balances_v1 import (
    parse,emit_js,previous_values,run,SOURCE,ANCHOR_VALUE,ANCHOR_DATE,
    validate_canonical,validate_source_overlap
)
TODAY=date(2026,11,14)
def document(*,when="Wednesday, 11 November 2026",current="185,950",
             move="4,213",unit="$ million",label="Exchange Settlement balances"):
    return f"""<!doctype html><html><head><title>Reserve Bank of Australia Balance Sheet</title></head>
    <body><h1>Reserve Bank of Australia Balance Sheet</h1>
    <p>At close of business on {when}</p>
    <p>{unit}</p>
    <table><thead><tr><th>Liabilities and Equity</th><th>Movement</th>
    <th>Assets</th><th>Movement</th></tr></thead>
    <tbody><tr><th>Australian notes on issue</th><td>110,104</td>
    <td>342</td><td>Gold and foreign exchange</td></tr>
    <tr><th><span>{label}</span></th><td>{current}</td>
    <td>{move}</td><td>Australian dollar investments</td></tr>
    <tr><th>Deposits (excluding Exchange Settlement balances)</th>
    <td>49,978</td><td>-3,530</td></tr></tbody></table>
    <p>The Bank's liabilities and assets data are provided on a more disaggregated basis.</p>
    </body></html>"""

class RBAESBalanceTest(unittest.TestCase):
    def test_exact_issuer_weekly_balance_and_movement(self):
        x=parse(document(),today=TODAY)
        self.assertEqual(x["source_period"],"2026-11-11")
        self.assertEqual(x["latest_balance_million_aud"],185950)
        self.assertEqual(x["weekly_movement_million_aud"],4213)
        self.assertEqual(x["previous_implied_million_aud"],181737)
        self.assertFalse(x["source_release_timestamp_verified"])

    def test_rba_date_not_a_claim_of_release_time(self):
        with self.assertRaisesRegex(ValueError,"weekday"):
            parse(document(when="Thursday, 11 November 2026"),today=TODAY)
        with self.assertRaisesRegex(ValueError,"future"):
            parse(document(when="Wednesday, 18 November 2026"),today=TODAY)
        with self.assertRaisesRegex(ValueError,"excessively stale"):
            parse(document(when="Wednesday, 16 September 2026"),today=TODAY)

    def test_issuer_field_cannot_be_substituted(self):
        with self.assertRaisesRegex(ValueError,"nonunique"):
            parse(document(label="Deposits excluding ES balances"),today=TODAY)
        with self.assertRaisesRegex(ValueError,"nonunique"):
            parse(document().replace("</tbody>","<tr><th>Exchange Settlement balances</th><td>190,000</td><td>100</td></tr></tbody>"),
                  today=TODAY)
        with self.assertRaisesRegex(ValueError,"unit"):
            parse(document(unit="USD billion"),today=TODAY)

    def test_signed_weekly_change_and_no_stocks_as_credit(self):
        x=parse(document(current="181,737",move="-1,853"),today=TODAY)
        self.assertEqual(x["weekly_movement_million_aud"],-1853)
        self.assertEqual(x["previous_implied_million_aud"],183590)
        with self.assertRaisesRegex(ValueError,"implausible"):
            parse(document(current="1,000"),today=TODAY)

    def test_emitted_sidecar_keeps_source_and_fx_guards(self):
        x=parse(document(),today=TODAY)
        js=emit_js(x,TODAY.isoformat())
        self.assertEqual(previous_values(js),
             {k:x[k] for k in ("source_period","latest_balance_million_aud",
                  "weekly_movement_million_aud","previous_implied_million_aud")})
        self.assertIn('"eligible_for_fx_core": false',js)
        self.assertIn('"eligible_for_backtest": false',js)
        self.assertIn('"first_release_pit_verified": false',js)
        self.assertIn('"value_canonical_overlap": 173965',js)
        self.assertIn('"asof_canonical_overlap": "2026-09-16"',js)

    def test_historical_anchor_survives_valid_append_but_not_revision(self):
        row={"dates":[ANCHOR_DATE,"2026-11-04","2026-11-11"],
             "values":[ANCHOR_VALUE,181737,185950],
             "last_date":"2026-11-11","last_value":185950}
        history=validate_canonical({"AUD":{"liquidity":row}})
        parsed=parse(document(),today=TODAY)
        self.assertEqual(validate_source_overlap(parsed,history),["2026-11-11","2026-11-04"])
        with self.assertRaisesRegex(ValueError,"overlap mismatch"):
            validate_source_overlap(dict(parsed,latest_balance_million_aud=185951),history)
        row["values"][0]+=1
        with self.assertRaisesRegex(ValueError,"anchor changed"):
            validate_canonical({"AUD":{"liquidity":row}})

    def test_idempotent_research_only_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture=Path(tmp)/"rba-balance-sheet.html"
            sidecar=Path(tmp)/"sidecar.js"
            fixture.write_text(document(),encoding="utf-8")
            r=run(destination=sidecar,fixture=fixture,apply=True,today=TODAY)
            self.assertEqual(r["write_state"],"RESEARCH_SIDECAR_ONLY")
            self.assertTrue(sidecar.exists())
            self.assertTrue(r["canonical_liquidity_unchanged"])
            second=run(destination=sidecar,fixture=fixture,apply=True,today=TODAY)
            self.assertEqual(second["status"],"NO_CHANGE")
            self.assertEqual(second["write_state"],"NO_MUTATION")
            fixture.write_text(document(when="Wednesday, 4 November 2026",
                                         current="181,737",move="-1,853"),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"rolled back"):
                run(destination=sidecar,fixture=fixture,apply=True,today=TODAY)

if __name__=="__main__":unittest.main()
