"""V6: true frozen event surprise, date-scoped ECB/yields and no fake FX cause."""
from __future__ import annotations
import copy
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
import json
import unittest

from validation.macro import build_g8_event_surprise_relative_pairs_v6 as m


class G8EventSurpriseRelativeV6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.today=datetime.now(ZoneInfo("Europe/Rome")).date()
        cls.book=m.build(today=cls.today)
        cls.forecasts=m.read_existing(m.LEDGER)
        cls.actuals=m.read_existing(m.ACTUAL_LEDGER)
        cls.anchors=m.read_existing(m.ANCHORS)
        cls.fx=json.loads((m.ROOT/m.v5.PRICE_FILE).read_text())
        cls.rates=json.loads((m.ROOT/m.v5.RATE_FILE).read_text())

    def test_v6_complete_28_pairs_but_only_two_real_frozen_events(self):
        b=self.book
        self.assertEqual(b["schema"],m.SCHEMA)
        self.assertEqual(b["coverage"]["canonical_fx_pairs"],28)
        self.assertEqual(b["coverage"]["g8_currencies"],8)
        self.assertEqual(b["coverage"]["frozen_consensus_actual_events"],2)
        self.assertEqual(b["coverage"]["pairs_exposed_to_frozen_events"],13)
        self.assertEqual(b["coverage"]["pair_event_exposures"],14)
        self.assertEqual(set(b["pairs"]),set(m.v5.build(today=self.today)["pairs"]))
        self.assertEqual(b["coverage"]["policy_repricing_confirmed"],0)
        self.assertEqual(b["coverage"]["proven_intraday_market_responses"],0)
        self.assertEqual(b["coverage"]["proven_macro_causality"],0)
        self.assertEqual(b["coverage"]["fx_signals"],0)
        self.assertFalse(b["ready_for_site"])
        self.assertFalse(b["ready_for_reports"])
        self.assertFalse(b["eligible_for_fx_core"])
        self.assertFalse(b["eligible_for_forecasting_backtest"])
        self.assertEqual(len(b["source_sha256"]),6)
        for pair,x in b["pairs"].items():
            with self.subTest(pair=pair):
                self.assertEqual(x["pair"],pair)
                self.assertIsNone(x["trade_attractiveness"])
                self.assertIsNone(x["thesis_strength"])
                self.assertIsNone(x["fx_signal"])
                self.assertIsNone(x["validated_impact"])
                for exposure in x["events"]:
                    self.assertIsNone(exposure["event_causal_fx_repricing_bp"])
                    self.assertIsNone(exposure["relative_6m_policy_path_change_bp"])
                    self.assertIsNone(exposure["verified_cb_want_can_from_release"])
                    self.assertTrue(exposure["no_intraday_causal_inference"])
                    self.assertFalse(
                        exposure["ecb_fx_daily_context"]["intraday_event_response_verified"])
                    self.assertFalse(
                        exposure["government_2y_relative_daily_context"]["intraday_event_repricing_verified"])

    def test_events_are_real_not_fixture_or_posthoc_consensus(self):
        events={e["currency"]:e for e in self.book["events"]}
        self.assertEqual(set(events),{"USD","CAD"})
        self.assertEqual(events["USD"]["secondary_consensus_pct"],.8)
        self.assertEqual(events["USD"]["actual_pct"],.8)
        self.assertEqual(events["USD"]["surprise_pp"],0)
        self.assertEqual(events["CAD"]["secondary_consensus_pct"],.2)
        self.assertEqual(events["CAD"]["actual_pct"],0)
        self.assertAlmostEqual(events["CAD"]["surprise_pp"],-.2)
        for e in events.values():
            self.assertLess(m.iso(e["consensus_captured_at_utc"]),
                            m.iso(e["release_scheduled_utc"]))
            self.assertLess(m.iso(e["anchor_captured_at_utc"]),
                            m.iso(e["release_scheduled_utc"]))
            self.assertGreaterEqual(m.iso(e["issuer_actual_first_observed_at_utc"]),
                                    m.iso(e["release_scheduled_utc"]))
            self.assertFalse(e["issuer_first_publication_PIT_verified"])
            self.assertTrue(e["market_baseline_early_not_last_tick"])
            self.assertEqual(len(e["other_same_instant_events"]),1)
            self.assertTrue(e["issuer_url"].startswith("https://"))

    def test_simultaneous_us_cad_no_isolated_fx_attribution(self):
        both=self.book["pairs"]["USD/CAD"]
        self.assertTrue(both["both_legs_same_release_time_confounder"])
        self.assertEqual(len(both["events"]),2)
        self.assertEqual({x["event_leg"] for x in both["events"]},{"BASE","QUOTE"})
        for e in both["events"]:
            self.assertEqual(len(e["confounding_same_instant_events"]),1)
            self.assertIsNone(e["event_causal_fx_repricing_bp"])
            self.assertIn("CONTESTO MULTIGIORNO",e["analyst_reading_it"])

    def test_all_7_pair_exposures_per_event_and_unexposed_15(self):
        counts={"USD":0,"CAD":0}
        unexposed=0
        for row in self.book["pairs"].values():
            if not row["events"]:
                unexposed+=1
            for event in row["events"]:
                counts[event["event_currency"]]+=1
        self.assertEqual(counts,{"USD":7,"CAD":7})
        self.assertEqual(unexposed,15)

    def test_ecb_fixing_exact_frozen_pre_reference_and_first_post_strict(self):
        pair="EUR/USD"
        x=next(e for e in self.book["pairs"][pair]["events"]
               if e["event_currency"]=="USD")["ecb_fx_daily_context"]
        self.assertEqual(x["base_date"],"2026-10-27")
        self.assertGreater(x["post_date"],"2026-10-30")
        self.assertEqual(x["post_date"],"2026-11-02")
        self.assertAlmostEqual(x["base_price_quote_per_base"],1.115)
        self.assertIsNotNone(x["return_pct"])
        self.assertTrue(x["not_trade_execution_price"])
        for pair,row in self.book["pairs"].items():
            for ev in row["events"]:
                q=ev["ecb_fx_daily_context"]
                if q["post_date"]:
                    self.assertGreater(q["post_date"],"2026-10-30")

    def test_false_frozen_ecb_quote_refused(self):
        anchor=copy.deepcopy(next(x for x in self.anchors if x["currency"]=="USD"))
        anchor["fx"]["quote_per_euro"]+=.2
        with self.assertRaisesRegex(ValueError,"archived and live ECB pre-reference conflict"):
            m.fx_multiday("EUR/USD",self.fx,anchor,date(2026,10,30),self.today)

    def test_gov_yield_spread_has_same_start_end_dates_for_each_leg(self):
        for p,row in self.book["pairs"].items():
            for exp in row["events"]:
                r=exp["government_2y_relative_daily_context"]
                self.assertIsNone(r.get("policy_rate_event_repricing_bp"))
                if r["relative_spread_change_bp"] is not None:
                    self.assertTrue(r["same_start_day_for_both_legs"])
                    self.assertTrue(r["same_end_day_for_both_legs"])
                    self.assertLess(r["start"],"2026-10-30")
                    self.assertGreater(r["end"],"2026-10-30")
                    self.assertTrue(r["first_release_market_timestamp_not_certified"])
                else:
                    self.assertEqual(r["status"],"NO_PAIRED_PRE_POST_SAME_DATES")

    def test_lack_of_post_release_dates_is_null_not_zero(self):
        ev=next(x for x in self.anchors if x["currency"]=="USD")
        q=m.fx_multiday("EUR/USD",self.fx,ev,date(2026,10,30),date(2026,10,30))
        self.assertIsNone(q["return_pct"])
        self.assertEqual(q["status"],"NO_FIRST_POST_RELEASE_DAILY_ECB_FIXING")
        r=m.relative_2y_multiday("EUR/USD",self.rates,ev,date(2026,10,30),date(2026,10,30))
        self.assertIsNone(r["relative_spread_change_bp"])

    def test_late_or_edited_consensus_fails_closed(self):
        late=copy.deepcopy(self.forecasts)
        late[0]["captured_at_utc"]="2026-10-30T12:34:00Z"
        with self.assertRaises(ValueError):
            m.validate_event_ledgers(late,self.actuals,self.anchors,self.today)
        fake=copy.deepcopy(self.actuals)
        fake[0]["actual_minus_frozen_consensus_pp"]=42
        with self.assertRaises(ValueError):
            m.validate_event_ledgers(self.forecasts,fake,self.anchors,self.today)
        no_actual=self.actuals[:1]
        with self.assertRaises(ValueError):
            m.validate_event_ledgers(self.forecasts,no_actual,self.anchors,self.today)

    def test_no_causality_in_rendered_readable_report(self):
        s=m.markdown(self.book)
        self.assertIn("## USD",s)
        self.assertIn("## CAD",s)
        self.assertIn("### USD/CAD",s)
        self.assertIn("EVENTI CONCORRENTI",s)
        self.assertIn("nessun segnale FX",s)
        self.assertNotIn("DOLLARO LONG CONFERMATO",s)


if __name__=="__main__":
    unittest.main()
