#!/usr/bin/env python3
"""Deterministic BoJ exact-series proof, new monthly observations and FX isolation."""
import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from validation.liquidity.refresh_boj_jpy_bank_credit_research_v1 import (
    parse,run,emit_js,existing,existing_payload,parse_tankan,tankan_latest_url,CANON,ORIGINAL_PERIOD,ORIGINAL_VALUE
)
DAY=date(2026,11,14)
CURRENT_CANONICAL=json.loads(CANON.read_text(encoding="utf-8"))
# Preserve the original historical test case even after the live feed advances.
CANONICAL=copy.deepcopy(CURRENT_CANONICAL)
row=CANONICAL["JPY"]["credit"]
n=row["dates"].index(ORIGINAL_PERIOD)+1
row["dates"]=row["dates"][:n];row["values"]=row["values"][:n]
row["last_date"]=row["dates"][-1];row["last_value"]=row["values"][-1]
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
      "runtime_overlap_count":len(CANONICAL["JPY"]["credit"]["dates"]),
      "runtime_exact_match_count":len(CANONICAL["JPY"]["credit"]["dates"]),
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

    def test_recurring_candidate_accepts_advanced_canonical_and_rejects_wrong_anchor(self):
        advanced=copy.deepcopy(CANONICAL)
        row=advanced["JPY"]["credit"]
        row["dates"]+=["2026-08","2026-09"]
        row["values"] += [6778576,6790000]
        row["last_date"]="2026-09";row["last_value"]=6790000
        x=candidate(added=[{"date":"2026-10","value":6791000}])
        x["runtime"]={"last_date":row["last_date"],"last_value":row["last_value"]}
        x["runtime_overlap_count"]=len(row["dates"])
        x["runtime_exact_match_count"]=len(row["dates"])
        p=parse(x,today=DAY,canonical=advanced)
        self.assertEqual(p["last_observation"],"2026-10")
        self.assertEqual(p["new_after_canonical"],1)
        with self.assertRaisesRegex(ValueError,"different canonical feed"):
            parse(candidate(),today=DAY,canonical=advanced)
        row["values"][row["dates"].index(ORIGINAL_PERIOD)]+=1
        with self.assertRaisesRegex(ValueError,"contract has moved"):
            parse(x,today=DAY,canonical=advanced)

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
        bad["runtime_exact_match_count"]=bad["runtime_overlap_count"]-1
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


    def test_tankan_actual_rows_and_retention(self):
        url="https://www.boj.or.jp/en/statistics/tk/yoshi/tk2609.htm"
        def table(label,sign,a,b,delta,extra=""):
            return f'<table><caption>{label} (All industries)</caption><tr><th>DI ({sign}), % points</th><th>June 2026 Survey</th><th>Sept. 2026 Survey</th><th>Change</th></tr><tr><td>All Enterprises</td><td>{a}</td><td>{b}</td><td>{delta}</td>{extra}</tr></table>'
        html=table("Lending Attitude of Financial institutions","accommodative - severe",13,13,0)+table("Financial Position","easy - tight",11,11,0)+table("Change in Interest Rate on Loans","rise - fall",61,68,7,"<td>71</td><td>3</td>")
        x=parse_tankan(html,url,today=DAY)
        self.assertEqual(x["dates"],["2026-Q2","2026-Q3"])
        self.assertEqual(x["lending_attitude"],[13,13])
        self.assertEqual(x["loan_rate_change"],[61,68])
        self.assertEqual(tankan_latest_url('<a href="tk2606.htm">June</a><a href="tk2609.htm">Sept</a><a href="tk2612.htm">Dec</a>',DAY),url)
        for bad in (html.replace("accommodative","other"),html.replace("<td>68</td>","<td>69</td>"),html.replace("All Enterprises","Large Enterprises")):
            with self.assertRaises(ValueError):parse_tankan(bad,url,today=DAY)
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/"candidate.json";dest=Path(root)/"research.js";survey=Path(root)/"survey.html"
            source.write_text(json.dumps(candidate()));survey.write_text(html)
            args={"candidate_file":source,"destination":dest,"apply":True,"today":DAY,"canonical":CANONICAL}
            run(**args)
            old=existing_payload(dest.read_text())
            out=run(**args,tankan_fixture=survey,tankan_url=url)
            self.assertEqual(out["tankan"]["status"],"VERIFIED")
            self.assertEqual(existing_payload(dest.read_text())["values"],old["values"])
            self.assertEqual(existing_payload(dest.read_text())["tankan"],x)
            self.assertEqual(run(**args,tankan_fixture=survey,tankan_url=url)["status"],"NO_CHANGE")
            survey.write_text("bad")
            out=run(**args,tankan_fixture=survey,tankan_url=url)
            self.assertEqual(out["tankan"]["retained_observation"],"2026-Q3")

if __name__=="__main__":unittest.main()
