#!/usr/bin/env python3
"""Integrity and falsification tests: no apparent returns from future information."""
import copy
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import unittest

from validation.quant.fxv2_rates_fx_temporal_readiness_v1 import (
    FX_PATH, QUOTES_PATH, MACRO_PATH, build,
)

class FXV2TemporalReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx_bytes=FX_PATH.read_bytes()
        cls.quote_bytes=QUOTES_PATH.read_bytes()
        cls.macro_bytes=MACRO_PATH.read_bytes()
        cls.fx=json.loads(cls.fx_bytes)
        cls.macro=json.loads(cls.macro_bytes)
        cls.quotes=[json.loads(line) for line in cls.quote_bytes.splitlines() if line.strip()]
        cls.result=build(cls.fx,cls.macro,cls.quotes,
                         cls.fx_bytes,cls.quote_bytes,cls.macro_bytes)

    def test_source_historical_price_rows_and_research_scope(self):
        o=self.result;s=o["summary"]
        self.assertEqual(s["fx_reference_rows"],self.fx["row_count"])
        self.assertEqual(s["fx_pairs"],28)
        self.assertEqual(s["archived_same_contract_quotes"],len(self.quotes))
        self.assertEqual(s["contract_currencies"],3)
        self.assertEqual(s["pairs_with_any_relative_history"]+
                         s["pairs_without_relative_history"],28)
        self.assertEqual(s["strict_relative_pair_moves"],
                         sum(v["matched_changes"] for v in o["pairs"].values()))
        self.assertEqual(s["strict_relative_pair_moves"],
                         len(o["relative_rate_observations"]))
        self.assertEqual(s["relative_events_with_future_ecb_t0"]+
                         s["relative_events_without_future_ecb_t0"],
                         len(o["relative_rate_observations"]))
        self.assertGreater(s["strict_relative_pair_moves"],0)
        self.assertLess(s["pairs_with_any_relative_history"],28)
        self.assertEqual(o["latest_fx_reference_fixing"],self.fx["last_as_of"])
        self.assertEqual(o["source_hashes_sha256"]["same_contract_futures_history"],
                         hashlib.sha256(self.quote_bytes).hexdigest())
        self.assertFalse(o["macro_point_in_time_feature_history_available"])
        self.assertFalse(o["registered_prospective_prediction_available"])
        self.assertFalse(o["eligible_for_signals"])
        self.assertFalse(o["eligible_for_backtests"])
        self.assertFalse(o["eligible_for_automatic_core_rebase"])
        self.assertTrue(o["canonical_fx_core_untouched"])
        self.assertTrue(o["no_expiry_roll_as_market_change"])
        self.assertTrue(o["no_same_day_fx_reaction_claim"])
        self.assertIsNone(o["statistical_significance"])
        self.assertIsNone(o["sharpe_ratio"])
        self.assertIsNone(o["out_of_sample_skill"])
        self.assertEqual(s["out_of_sample_predictions"],0)
        self.assertEqual(s["generated_fx_signals"],0)

    def test_no_lookahead_and_no_trading_signal_for_every_sample(self):
        o=self.result
        fx_dates=[r["Date"] for r in self.fx["rows"]]
        source_quotes={(r["currency"],r["contract"],r["observation_date"]):r
                       for r in self.quotes}
        for row in o["relative_rate_observations"]:
            p=row["pair"];a,b=p.split("/")
            d0,d1=row["previous_market_date"],row["market_date"]
            self.assertLess(fx_dates.index(d0),fx_dates.index(d1))
            self.assertEqual(fx_dates.index(d1)-fx_dates.index(d0),1)
            for c,k in ((a,"base_contract"),(b,"quote_contract")):
                self.assertIn((c,row[k],d0),source_quotes)
                self.assertIn((c,row[k],d1),source_quotes)
            latest=max(
                source_quotes[(c,row[k],d)]["first_seen_at_utc"]
                for c,k in ((a,"base_contract"),(b,"quote_contract"))
                for d in (d0,d1)
            )
            self.assertEqual(row["source_usable_at_utc"],latest)
            if row["first_strictly_post_capture_ecb_date"]:
                self.assertGreater(row["first_strictly_post_capture_ecb_date"],
                                   latest[:10])
                if row["following_ecb_date"]:
                    self.assertGreater(row["following_ecb_date"],
                                       row["first_strictly_post_capture_ecb_date"])
            self.assertAlmostEqual(row["relative_rate_change_bp"],
                                   row["base_rate_change_bp"]-
                                   row["quote_rate_change_bp"],places=3)
            self.assertFalse(row["is_out_of_sample_prediction"])
            self.assertFalse(row["outcome_used_in_model"])
            self.assertIsNone(row["future_fx_return"])
            self.assertIsNone(row["same_day_fx_return"])
            self.assertIsNone(row["fx_signal"])
            self.assertIsNone(row["policy_repricing_bp"])
            self.assertEqual(row["rate_instrument_quality"],
                             "SECONDARY_FUTURES_NOT_OIS")

    def test_only_three_early_pairs_have_exact_contract_relative_history(self):
        o=self.result
        eligible={p for p,v in o["pairs"].items() if v["matched_changes"]}
        self.assertEqual(eligible,{"EUR/USD","USD/CHF","EUR/CHF"})
        distinct={r["market_date"] for r in o["relative_rate_observations"]}
        self.assertEqual(len(distinct),o["summary"]["distinct_relative_market_days"])
        self.assertLess(len(distinct),30, "a very short window cannot support OOS inference")

    def assert_rejected(self,fx=None,macro=None,quotes=None):
        with self.assertRaises(ValueError):
            build(fx if fx is not None else self.fx,
                  macro if macro is not None else self.macro,
                  quotes if quotes is not None else self.quotes,
                  self.fx_bytes,self.quote_bytes,self.macro_bytes)

    def test_source_tampering_and_expiry_are_rejected(self):
        bad=copy.deepcopy(self.quotes)
        bad.append(copy.deepcopy(bad[0]))
        self.assert_rejected(quotes=bad)
        bad=copy.deepcopy(self.quotes)
        bad[0]["official_ois_quote"]=True
        self.assert_rejected(quotes=bad)
        bad=copy.deepcopy(self.quotes)
        bad[0]["policy_delta_eligible"]=True
        self.assert_rejected(quotes=bad)
        bad=copy.deepcopy(self.quotes)
        bad[0]["first_seen_at_utc"]="2026-10-01T10:00:00Z"
        self.assert_rejected(quotes=bad)
        bad=copy.deepcopy(self.quotes)
        bad[0]["implied_rate"]+=1
        self.assert_rejected(quotes=bad)
        bad=copy.deepcopy(self.quotes)
        bad[0]["expiration"]="2020-01-01"
        self.assert_rejected(quotes=bad)

    def test_fx_history_and_macro_source_cannot_be_promoted(self):
        p=copy.deepcopy(self.fx)
        p["status"]="PROXY_DERIVED"
        self.assert_rejected(fx=p)
        p=copy.deepcopy(self.fx)
        p["rows"][0]["USD"]=0
        self.assert_rejected(fx=p)
        p=copy.deepcopy(self.fx)
        p["rows"][1]["Date"]=p["rows"][0]["Date"]
        self.assert_rejected(fx=p)
        m=copy.deepcopy(self.macro)
        m["eligible_for_backtests"]=True
        self.assert_rejected(macro=m)
        m=copy.deepcopy(self.macro)
        m["pairs"]["EUR/USD"]["macro_fx_signal"]="SELL"
        self.assert_rejected(macro=m)

if __name__=="__main__":
    unittest.main()
