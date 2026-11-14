#!/usr/bin/env python3
"""Deterministic BoJ exact-series proof, new monthly observations and FX isolation."""
import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from validation.liquidity.refresh_boj_jpy_bank_credit_research_v1 import (
    parse,run,emit_js,existing,CANON,ORIGINAL_PERIOD,ORIGINAL_VALUE
)
DAY=date(2026,11,14)
CANONICAL=json.loads(CANON.read_text(encoding="utf-8"))
LAST="2026-09"
ADDED=[
    {"date":"2026-08","value":6778576},
    {"date":"2026-09","value":6790000}
]

def candidate(*,added=None):
    x=copy.deepcopy(ADDED if added is None else added)
    return {
      "schema":"GMFQ_LIQUIDITY_JPY_BANK_CREDIT_CANDIDATE_V1",
      "status":"GREEN_SOURCE_CANDIDATE_ONLY",
      "source":{
        "publisher":"Bank of Japan",
        "database":"MD11",
        "series_id":"DLCLAEDBLTTO",
        "unit":"100 million yen",
        "frequency":"MONTHLY",
        "url":"https://www.stat-search.boj.or.jp/api/v1/getDataCode?db=MD11&code=DLCLAEDBLTTO"
      },
      "runtime":{
        "last_date":ORIGINAL_PERIOD,
        "last_value":ORIGINAL_VALUE
      },
      "runtime_overlap_count":28,
      "runtime_exact_match_count":28,
      "runtime_match_confirmed":True,
      "latest_date":x[-1]["date"] if x else ORIGINAL_PERIOD,
      "latest_value":x[-1]["value"] if x else ORIGINAL_VALUE,
      "new_observations":x,
      "candidate_update_available":bool(x),
      "publication_performed":False,
      "runtime_mutated":False
    }

class JPYOfficialBankCreditResearchTest(unittest.TestCase):
    def test_source_and_exact_overlap(self):
        p=parse(candidate(),today=DAY,canonical=CANONICAL)
        self.assertEqual(p["last_observation"],LAST)
        self.assertEqual(p["values"][-2:], [6778576,6790000])
        self.assertGreaterEqual(p["matched_canonical_months"],12)
        self.assertEqual(p["new_after_canonical"],2)

    def test_monthly_chronology_and_source_contract(self):
        p=parse(candidate(),today=DAY,canonical=CANONICAL)
        self.assertEqual(p["dates"][-3:],
                         [ORIGINAL_PERIOD,"2026-08","2026-09"])
        bad=candidate()
        bad["source"]["unit"]="millions of yen"
        with self.assertRaisesRegex(ValueError,"wrong issuer"):
            parse(bad,today=DAY,canonical=CANONICAL)
        bad=candidate()
        bad["source"]["series_id"]="DLCLAEDBLTCO"
        with self.assertRaisesRegex(ValueError,"wrong issuer"):
            parse(bad,today=DAY,canonical=CANONICAL)

    def test_historical_mismatch_no_silent_credit_rebase(self):
        bad=candidate()
        bad["runtime_exact_match_count"]=27
        with self.assertRaisesRegex(ValueError,"nonexact"):
            parse(bad,today=DAY,canonical=CANONICAL)
        alt=copy.deepcopy(CANONICAL)
        alt["JPY"]["credit"]["values"][-1]+=5
        alt["JPY"]["credit"]["last_value"]+=5
        with self.assertRaisesRegex(ValueError,"canonical JPY credit contract has moved"):
            parse(candidate(),today=DAY,canonical=alt)

    def test_missing_future_and_invalid_stock_rejected(self):
        bad=candidate()
        bad["new_observations"][0]["date"]="2026-09"
        with self.assertRaisesRegex(ValueError,"nonconsecutive"):
            parse(bad,today=DAY,canonical=CANONICAL)
        bad=candidate()
        bad["new_observations"][-1]["value"]=15000000
        bad["latest_value"]=15000000
        with self.assertRaisesRegex(ValueError,"implausible"):
            parse(bad,today=DAY,canonical=CANONICAL)
        with self.assertRaisesRegex(ValueError,"future"):
            parse(candidate(),today=date(2026,8,14),canonical=CANONICAL)

    def test_empty_new_observations_is_idempotent_and_reviewable(self):
        p=parse(candidate(added=[]),today=DAY,canonical=CANONICAL)
        self.assertEqual(p["last_observation"],ORIGINAL_PERIOD)
        self.assertEqual(p["new_after_canonical"],0)

    def test_sidecar_apply_and_no_fx_core(self):
        p=parse(candidate(),today=DAY,canonical=CANONICAL)
        js=emit_js(p,DAY.isoformat())
        self.assertIn('"eligible_for_fx_core": false',js)
        self.assertIn('"eligible_for_backtest": false',js)
        self.assertIn('"first_release_pit_verified": false',js)
        self.assertIn('"unit": "100 milioni JPY"',js)
        self.assertEqual(existing(js),(p["dates"],p["values"]))
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/"candidate.json"
            dest=Path(root)/"jpy-credit-research.js"
            source.write_text(json.dumps(candidate()),encoding="utf-8")
            dest.write_text("const data={dates:[],values:[]};",encoding="utf-8")
            receipt=run(candidate_file=source,destination=dest,apply=True,
                        today=DAY,canonical=CANONICAL)
            self.assertEqual(receipt["write_state"],"RESEARCH_SIDECAR_ONLY")
            self.assertEqual(receipt["last_observation"],LAST)
            again=run(candidate_file=source,destination=dest,apply=True,
                      today=DAY,canonical=CANONICAL)
            self.assertEqual(again["status"],"NO_CHANGE")
            self.assertEqual(again["write_state"],"NO_MUTATION")

if __name__=="__main__":unittest.main()
