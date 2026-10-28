"""Regression and adversarial gates for G8 macro-event dated market context."""
from __future__ import annotations
import copy
import json
import unittest
from datetime import datetime,timezone
from pathlib import Path

from validation.macro.freeze_pre_release_consensus_v1 import LEDGER, read_existing
from validation.macro.capture_official_postrelease_actuals_v1 import (
    ECI,GDP,capture as capture_actuals
)
from validation.macro.build_macro_event_market_context_v1 import (
    ROOT,ANCHORS,FX,OIS,RATES,SCHEMA,MONITOR_SCHEMA,
    capture_anchors,validate_anchors,build_context,run
)

BEFORE=datetime(2026,10,28,9,5,tzinfo=timezone.utc)
AFTER=datetime(2026,11,3,10,0,tzinfo=timezone.utc)
BLS=b"""<html><h1>Employment Cost Index News Release</h1>
Transmission of material in this release is embargoed until
8:30 a.m. (ET) Friday, October 30, 2026
<h2>EMPLOYMENT COST INDEX - SEPTEMBER 2026</h2>
<p>Compensation costs for civilian workers increased 0.7 percent,
seasonally adjusted, for the 3-month period ending in September 2026.</p></html>"""
CAD=b"""<html><h1>Gross domestic product by industry, August 2026</h1>
<p>Released: 2026-10-30</p>
<p>Real gross domestic product (GDP) grew 0.3% in August.</p></html>"""

def official_mock(url,host):
    return (BLS if host=="www.bls.gov" else CAD),url

class EventMarketContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forecasts=read_existing(LEDGER)
        cls.rates=json.loads(RATES.read_text(encoding="utf-8"))
        cls.ois=json.loads(OIS.read_text(encoding="utf-8"))
        cls.fx=json.loads(FX.read_text(encoding="utf-8"))
        cls.anchors,cls.receipt=capture_anchors(
            cls.forecasts,[],cls.rates,cls.ois,cls.fx,BEFORE)
        cls.signed_actuals,_=capture_actuals(cls.forecasts,[],AFTER,official_mock)

    def test_source_receipts_captured_without_lookahead_or_fake_OIS(self):
        self.assertEqual(len(self.anchors),2)
        self.assertEqual(self.receipt["added_anchors"],2)
        self.assertEqual({a["event_key"] for a in self.anchors},{ECI,GDP})
        for a in self.anchors:
            self.assertEqual(a["schema"],SCHEMA)
            self.assertTrue(a["no_intraday_event_reaction_claim"])
            self.assertFalse(a["PIT_first_publication_certified"])
            self.assertFalse(a["eligible_for_D_Beta_Forward"])
            self.assertLess(a["2Y"]["date"],"2026-10-30")
            self.assertLess(a["fx"]["date"],"2026-10-30")
            self.assertEqual(a["fx"]["pair"],"EUR/"+a["currency"])
        usd=next(x for x in self.anchors if x["currency"]=="USD")
        cad=next(x for x in self.anchors if x["currency"]=="CAD")
        self.assertEqual(usd["2Y"]["date"],"2026-10-27")
        self.assertEqual(cad["2Y"]["date"],"2026-10-26")
        self.assertIsNone(usd["six_month"]) # USD TradingView estimate is NOT OIS.
        self.assertEqual(cad["six_month"]["date"],"2026-10-27")
        self.assertEqual(cad["six_month"]["quality"],"OFFICIAL_EXCHANGE_FUTURES_NOT_OIS")
        self.assertEqual(cad["fx"]["pair"],"EUR/CAD")
        self.assertEqual(usd["fx"]["pair"],"EUR/USD")
        validate_anchors(self.anchors,self.forecasts)

    def test_before_release_all_events_wait_without_claiming_impact(self):
        r=build_context(self.forecasts,self.anchors,[],self.rates,self.ois,self.fx,BEFORE)
        self.assertEqual(r["schema"],MONITOR_SCHEMA)
        self.assertEqual(r["summary"]["awaiting_release"],2)
        self.assertEqual(r["summary"]["FX_signals"],0)
        self.assertEqual(r["summary"]["issuer_event_intraday_reactions_certified"],0)
        for x in r["events"]:
            self.assertEqual(x["state"],"PENDING_OFFICIAL_RELEASE")
            self.assertIsNone(x["official_actual_percent"])
            self.assertIsNone(x["post_event_daily_comparison"])
            self.assertFalse(x["event_causality_verified"])

    def test_after_release_without_actual_does_not_infer_surprise_from_yields(self):
        r=build_context(self.forecasts,self.anchors,[],self.rates,self.ois,self.fx,AFTER)
        self.assertEqual(r["summary"]["awaiting_actual"],2)
        for x in r["events"]:
            self.assertEqual(x["state"],"PENDING_OFFICIAL_ACTUAL_ISSUER_VERIFICATION")
            self.assertIsNone(x["post_event_daily_comparison"])

    def append_post_source_observations(self):
        rates=copy.deepcopy(self.rates)
        ois=copy.deepcopy(self.ois)
        fx=copy.deepcopy(self.fx)
        for c in ("USD","CAD"):
            row=rates[c]
            row["date"]="2026-11-02"
            for tenor,hname,step in (("2Y","history2",0.02),("10Y","history10",0.04)):
                val=float(row[hname]["values"][-1])+step
                row[hname]["dates"].append("2026-11-02")
                row[hname]["values"].append(val)
                row[hname]["last_date"]="2026-11-02"
                row[hname]["last_value"]=val
                row[tenor]=val
        last=fx["rows"][-1]
        x=dict(last)
        x.update(Date="2026-11-02",USD=last["USD"]+0.005,CAD=last["CAD"]+0.007)
        fx["rows"].append(x)
        cad=ois["currencies"]["CAD"]
        cad["as_of"]="2026-11-02"
        cad["provenance"]["observations"]["current"]["date"]="2026-11-02"
        cad["provenance"]["observations"]["current"]["6m"]=3.025
        cad["horizons"]["6m"]["rate"]=3.025
        return rates,ois,fx

    def test_actual_to_post_daily_context_never_infers_causality(self):
        rates,ois,fx=self.append_post_source_observations()
        result=build_context(self.forecasts,self.anchors,self.signed_actuals,
                             rates,ois,fx,AFTER)
        self.assertEqual(result["summary"]["observed_daily_context"],2)
        self.assertEqual(result["summary"]["issuer_event_intraday_reactions_certified"],0)
        for item in result["events"]:
            self.assertEqual(item["state"],"DAILY_CONTEXT_ONLY_NO_EVENT_CAUSALITY")
            self.assertFalse(item["event_causality_verified"])
            self.assertIsNone(item["FX_trade_signal"])
            self.assertIsNone(item["CB_Want_Can_from_official_statements"])
            self.assertFalse(item["eligible_for_Core_Beta_Forward"])
            p=item["post_event_daily_comparison"]
            self.assertEqual(p["2Y"]["to"],"2026-11-02")
            self.assertEqual(p["2Y"]["status"],"DESCRIPTIVE_MULTIDAY_CHANGE_NOT_EVENT_CAUSAL")
            self.assertEqual(p["ECB_FX"]["to"],"2026-11-02")
        lookup={x["currency"]:x for x in result["events"]}
        self.assertEqual(lookup["USD"]["post_event_daily_comparison"]["SIX_MONTH"]["status"],
                         "NO_OFFICIAL_PRERELEASE_SOURCE")
        self.assertEqual(lookup["CAD"]["post_event_daily_comparison"]["SIX_MONTH"]["to"],
                         "2026-11-02")
        self.assertEqual(lookup["CAD"]["official_actual_percent"],0.3)
        self.assertAlmostEqual(lookup["USD"]["actual_minus_frozen_consensus_pp"],-0.1)

    def test_same_release_day_only_cannot_be_called_post_event_daily(self):
        rates,ois,fx=self.append_post_source_observations()
        for c in ("USD","CAD"):
            r=rates[c];r["date"]="2026-10-30"
            for key in ("history2","history10"):
                r[key]["dates"][-1]="2026-10-30"
                r[key]["last_date"]="2026-10-30"
        fx["rows"][-1]["Date"]="2026-10-30"
        cad=ois["currencies"]["CAD"]
        cad["as_of"]="2026-10-30"
        cad["provenance"]["observations"]["current"]["date"]="2026-10-30"
        result=build_context(self.forecasts,self.anchors,self.signed_actuals,
                             rates,ois,fx,AFTER)
        for item in result["events"]:
            self.assertEqual(item["state"],"PENDING_POST_RELEASE_DAILY_OBSERVATIONS")

    def test_futures_roll_or_unverified_mapping_does_not_report_six_month_move(self):
        rates,ois,fx=self.append_post_source_observations()
        cad=ois["currencies"]["CAD"]
        cad["source_meta"]["horizon_mapping"]="DIFFERENT_MARCH_CONTRACT"
        result=build_context(self.forecasts,self.anchors,self.signed_actuals,
                             rates,ois,fx,AFTER)
        row=next(x for x in result["events"] if x["currency"]=="CAD")
        self.assertEqual(row["post_event_daily_comparison"]["SIX_MONTH"]["status"],
                         "NO_MATCHED_POST_EVENT_SOURCE")
        self.assertEqual(row["state"],"DAILY_CONTEXT_ONLY_NO_EVENT_CAUSALITY")

    def test_anchor_chain_and_first_record_immutability(self):
        corrupt=copy.deepcopy(self.anchors);corrupt[0]["2Y"]["yield_pct"]+=10
        with self.assertRaises(ValueError):validate_anchors(corrupt,self.forecasts)
        corrupt=copy.deepcopy(self.anchors);corrupt.reverse()
        with self.assertRaises(ValueError):validate_anchors(corrupt,self.forecasts)
        again,receipt=capture_anchors(self.forecasts,self.anchors,self.rates,self.ois,self.fx,BEFORE)
        self.assertEqual(again,self.anchors)
        self.assertEqual(receipt["added_anchors"],0)

    def test_read_only_preview_does_not_write_live_or_journal(self):
        before={
          "forecast":LEDGER.read_bytes(),
          "anchors":ANCHORS.read_bytes(),
          "actual":(ROOT/"validation/macro/MACRO_OFFICIAL_ACTUAL_FIRST_SEEN_V1.jsonl").read_bytes(),
          "news":(ROOT/"live_data/sections/NEWS_PULSE_OPERATIONAL.json").read_bytes()
        }
        receipt,context=run(now=BEFORE,freeze=False)
        self.assertEqual(context["summary"]["events"],2)
        self.assertEqual(receipt["status"],"MACRO_PRE_RELEASE_MARKET_ANCHOR_CHECK")
        self.assertEqual(before["forecast"],LEDGER.read_bytes())
        self.assertEqual(before["anchors"],ANCHORS.read_bytes())
        self.assertEqual(before["actual"],(ROOT/"validation/macro/MACRO_OFFICIAL_ACTUAL_FIRST_SEEN_V1.jsonl").read_bytes())
        self.assertEqual(before["news"],(ROOT/"live_data/sections/NEWS_PULSE_OPERATIONAL.json").read_bytes())

if __name__=="__main__":
    unittest.main()
