#!/usr/bin/env python3
"""Prospective scoring must use the earliest frozen forecast and first later value."""
import copy
import json
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
from validation.macro.capture_g8_prospective_v1 import build_receipt
from validation.macro.score_g8_prospective_v1 import (
    evaluate, score_pair, publish_outcome, valid_receipt, SCHEMA,
)

ROOT=Path(__file__).resolve().parents[2]


class FirstSeenScoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        m=(ROOT/"live_data/sections/MACRO_SERIES.json").read_bytes()
        s=(ROOT/"site/fx-quant-v2/next/g8-growth-shadow.js").read_bytes()
        cls.issue=build_receipt(m,s,"a"*40,datetime(2026,11,12,8,58,tzinfo=timezone.utc))

    def seen(self,value=17060.0,baseline_revision=0.0,day="2026-11-14"):
        r=copy.deepcopy(self.issue)
        r["capture_rome_date"]=day
        r["captured_at_utc"]=day+"T10:00:00Z"
        r["captured_at_rome"]=day+"T11:00:00+01:00"
        r["source_main_commit"]="f"*40
        r["source_macro_sha256"]="b"*64
        c=r["selected_macro_vintage"]["USD"]
        last=c["observations"][-1]
        self.assertEqual(last["period"],"2026-09")
        last["value"]+=baseline_revision
        c["observations"].append({"period":"2026-10","value":value})
        c["latest_observation_period"]="2026-10"
        # First-seen new observation is part of an updated model's inputs,
        # not a new prediction of the already observed October.
        r["forecast_evidence"]["currencies"]["USD"]["candidate"]=False
        r["forecast_evidence"]["currencies"]["USD"]["forecast"]=None
        r["forecast_evidence"]["currencies"]["USD"]["nextObservationPeriod"]="2026-11"
        return r

    def test_earliest_forecast_against_first_later_observation(self):
        intermediate=copy.deepcopy(self.issue)
        intermediate["captured_at_utc"]="2026-11-13T08:00:00Z"
        intermediate["capture_rome_date"]="2026-11-13"
        intermediate["forecast_evidence"]["currencies"]["USD"]["forecast"]["nextChange"]=999.0
        first=self.seen(17060,day="2026-11-14")
        later=self.seen(18000,day="2026-11-15")
        outcomes=evaluate([later,intermediate,first,self.issue])
        self.assertEqual(len(outcomes),1)
        o=outcomes[0]
        self.assertEqual(o["schema"],SCHEMA)
        self.assertEqual(o["currency"],"USD")
        self.assertEqual(o["target_observation_period"],"2026-10")
        self.assertEqual(o["first_seen_in_fx_quant_at_utc"],"2026-11-14T10:00:00Z")
        self.assertAlmostEqual(o["forecast_change"],
             self.issue["forecast_evidence"]["currencies"]["USD"]["forecast"]["nextChange"])
        self.assertAlmostEqual(o["observed_change_first_seen"],
             (17060.0/self.issue["selected_macro_vintage"]["USD"]["observations"][-1]["value"]-1)*100)
        self.assertEqual(o["model_absolute_error"],abs(o["forecast_change"]-o["observed_change_first_seen"]))
        self.assertEqual(o["baseline_absolute_error"],abs(o["observed_change_first_seen"]))
        self.assertFalse(o["issuer_first_release_verified"])
        self.assertFalse(o["fx_signal_generated"])

    def test_record_revision_of_the_earlier_baseline(self):
        outcome=score_pair(self.issue,self.seen(baseline_revision=-20.0),"USD")
        self.assertIsNotNone(outcome)
        self.assertLess(outcome["baseline_revision_during_window"],0)
        self.assertNotEqual(outcome["prior_baseline_value_at_forecast"],
                            outcome["prior_baseline_value_at_first_seen"])

    def test_no_hindsight_or_same_day_settlement(self):
        self.assertEqual(evaluate([self.issue]),[])
        self.assertIsNone(score_pair(self.issue,self.issue,"USD"))
        before=copy.deepcopy(self.issue)
        before["captured_at_utc"]="2026-11-11T08:00:00Z"
        self.assertIsNone(score_pair(self.issue,before,"USD"))
        future=copy.deepcopy(self.seen())
        future["issuer_release_vintage_verified"]=True
        self.assertFalse(valid_receipt(future))
        self.assertIsNone(score_pair(self.issue,future,"USD"))
        never=copy.deepcopy(self.issue)
        never["selected_macro_vintage"]["USD"]["observations"].append({"period":"2026-10","value":18000.0})
        never["selected_macro_vintage"]["USD"]["latest_observation_period"]="2026-10"
        self.assertIsNone(score_pair(never,self.seen(),"USD"))

    def test_append_only_outcome_path(self):
        item=score_pair(self.issue,self.seen(),"USD")
        with patch("validation.macro.score_g8_prospective_v1.github_json",
                   return_value=(200,{"sha":"immutable"})) as g:
            result=publish_outcome(item,"token","owner/repo")
        self.assertEqual(result["status"],"ALREADY_SETTLED_IMMUTABLE")
        self.assertFalse(result["wrote"])
        self.assertEqual(g.call_count,1)
        with patch("validation.macro.score_g8_prospective_v1.github_json",
                   side_effect=[(404,{}),(201,{"content":{"sha":"new"}})]) as g:
            result=publish_outcome(item,"token","owner/repo")
        self.assertEqual(result["status"],"CREATED_IMMUTABLE")
        self.assertTrue(result["wrote"])
        self.assertNotIn("sha",g.call_args_list[1].args[3],
                         "PUT must never overwrite a prior outcome")

    def test_no_promoted_claim(self):
        item=score_pair(self.issue,self.seen(),"USD")
        item["issuer_first_release_verified"]=True
        with self.assertRaises(ValueError):
            publish_outcome(item,"token","owner/repo")


if __name__=="__main__":
    unittest.main()
