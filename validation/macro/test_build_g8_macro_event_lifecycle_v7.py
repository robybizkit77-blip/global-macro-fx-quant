"""V7 evidence readiness: official G8 calendar, time/PIT and live-source absence."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import unittest
from zoneinfo import ZoneInfo

from validation.macro import build_g8_macro_event_lifecycle_v7 as m

NOW=datetime(2026,11,9,15,10,tzinfo=timezone.utc)


class G8MacroEventLifecycleV7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources,_=m.load()
        cls.book=m.build(now=NOW,inputs=copy.deepcopy(cls.sources))

    def test_20_g8_official_seed_events_not_20_false_surprises(self):
        b=self.book
        c=b["coverage"]
        self.assertEqual(b["schema"],m.SCHEMA)
        self.assertEqual(c["currencies_in_historical_calendar"],8)
        self.assertEqual(c["issuer_calendar_events"],20)
        self.assertEqual(c["events_with_genuine_frozen_consensus_and_issuer_actual"],2)
        self.assertEqual(c["unverified_intraday_event_reactions"],20)
        self.assertEqual(c["new_trading_signals"],0)
        self.assertFalse(b["ready_for_live_28_pair_signals"])
        self.assertFalse(b["ready_for_automatic_market_attribution"])
        self.assertFalse(b["ready_for_historical_PIT_backtest"])
        self.assertFalse(b["writes_market_model"])
        self.assertTrue(b["reuses_existing_calendar_news_schedule"])
        self.assertFalse(b["new_cron_added"])
        self.assertEqual(len({x["event_key"] for x in b["events"]}),20)

    def test_upcoming_us_cpi_uk_gdp_ch_gdp_have_no_frozen_forecast(self):
        b=self.book
        q=b["priority_queue"]
        self.assertEqual(len(q),3)
        self.assertEqual([x["ccy"] for x in q],["USD","GBP","CHF"])
        self.assertEqual([x["issuer_date"] for x in q],
                         ["2026-11-10","2026-11-12","2026-11-16"])
        self.assertEqual(b["coverage"]["upcoming_35d_with_frozen_consensus"],0)
        self.assertEqual(b["coverage"]["upcoming_35d_with_approved_actual_parser"],0)
        self.assertEqual(b["coverage"]["currencies_with_upcoming_35d"],3)
        self.assertIn("NZD",b["coverage"]["countries_without_upcoming_35d"])
        self.assertIn("EUR",b["coverage"]["countries_without_upcoming_35d"])
        for e in q:
            self.assertEqual(e["status"],"UPCOMING_NO_VERIFIED_EXACT_CONSENSUS")
            self.assertIsNone(e["frozen_consensus_pct"])
            self.assertIsNone(e["actual_minus_frozen_consensus_pp"])
            self.assertIsNone(e["issuer_actual_pct"])
            self.assertIsNone(e["actual_metric_unit"])
            self.assertFalse(e["official_issuer_parser_supported"])
            self.assertIn("NON ancora validato",e["next_action_it"])
            self.assertEqual(e["currency_pair_count"],7)
            self.assertIsNotNone(e["scheduled_release_utc"])
        self.assertEqual(q[0]["scheduled_release_utc"],"2026-11-10T13:30:00Z")
        self.assertEqual(q[1]["scheduled_release_utc"],"2026-11-12T07:00:00Z")
        self.assertEqual(q[2]["scheduled_release_utc"],"2026-11-16T08:00:00Z")

    def test_frozen_real_30_oct_receipts_are_0_and_minus_02_pp(self):
        b=self.book
        complete=[x for x in b["events"]
                  if x["actual_minus_frozen_consensus_pp"] is not None]
        self.assertEqual({x["ccy"] for x in complete},{"USD","CAD"})
        by={x["ccy"]:x for x in complete}
        self.assertEqual(by["USD"]["frozen_consensus_pct"],.8)
        self.assertEqual(by["USD"]["issuer_actual_pct"],.8)
        self.assertEqual(by["USD"]["actual_minus_frozen_consensus_pp"],0)
        self.assertEqual(by["CAD"]["frozen_consensus_pct"],.2)
        self.assertEqual(by["CAD"]["issuer_actual_pct"],0)
        self.assertEqual(by["CAD"]["actual_minus_frozen_consensus_pp"],-.2)
        for e in complete:
            self.assertEqual(
                e["status"],"FROZEN_FORECAST_AND_FIRST_SEEN_OFFICIAL_ACTUAL")
            self.assertTrue(e["has_frozen_market_anchor"])
            self.assertFalse(e["release_intraday_market_response_verified"])
            self.assertFalse(e["source_is_first_release_pit_certified"])
            self.assertFalse(e["policy_repricing_verified"])
            self.assertEqual(e["fx_signals"],0)

    def test_past_event_without_pre_release_consensus_is_irrecoverable(self):
        gb=next(x for x in self.book["events"] if
                x["ccy"]=="GBP" and x["issuer_date"]=="2026-10-21")
        self.assertEqual(gb["status"],"PAST_EVENT_NO_FROZEN_CONSENSUS")
        self.assertIn("Non ricostruire",gb["next_action_it"])
        self.assertIsNone(gb["actual_minus_frozen_consensus_pp"])

    def test_provider_candidate_not_locked_forecast_or_overwrite(self):
        s=copy.deepcopy(self.sources)
        us=next(x for x in s["official_calendar"]["events"] if
                x["ccy"]=="USD" and x["date"]=="2026-11-10")
        key=m.exact_event_key(us)
        c={"event_key":key,"status":"AVAILABLE","consensus":"0.4%",
           "provider_event":"Consumer Price Index","confidence_grade":"B",
           "date_match_gap_days":0}
        # A matching generic provider title may be a candidate but it is NOT
        # an admissible frozen metric-specific CPI YoY/MoM consensus.
        s["secondary_consensus"]["events"]=[c]
        b=m.build(now=NOW,inputs=s)
        e=next(x for x in b["events"] if x["event_key"]==key)
        self.assertIsNone(e["frozen_consensus_pct"])
        self.assertIsNone(e["actual_minus_frozen_consensus_pp"])
        self.assertEqual(e["provider_candidate_status"],
                         "CANDIDATE_AVAILABLE_NOT_YET_FROZEN")
        self.assertEqual(e["status"],"READY_TO_FREEZE_FUTURE_CONSENSUS")
        # Actual freeze pipeline additionally refuses an unspecified CPI
        # economic rate: V7 does not misreport that this candidate was frozen.
        self.assertFalse(e["official_issuer_parser_supported"])

    def test_non_equivalent_cpi_subseries_candidate_blocked(self):
        us=next(x for x in self.sources["official_calendar"]["events"] if
                x["ccy"]=="USD" and x["date"]=="2026-11-10")
        cand={"event_key":m.exact_event_key(us),"status":"AVAILABLE",
              "consensus":"0.3%","provider_event":"CPI m/m",
              "confidence_grade":"B","date_match_gap_days":0}
        self.assertEqual(m.candidate_ready(us,cand,NOW),
                         "PROVIDER_SERIES_NOT_EXACT_ISSUER_METRIC")
        # Gross product vs rate of growth likewise cannot silently match.
        ch=next(x for x in self.sources["official_calendar"]["events"] if
                x["ccy"]=="CHF" and x["date"]=="2026-11-16")
        c={"event_key":m.exact_event_key(ch),"status":"AVAILABLE",
           "consensus":"0.2%","provider_event":"GDP q/q",
           "confidence_grade":"B","date_match_gap_days":0}
        self.assertIn(m.candidate_ready(ch,c,NOW),(
            "PROVIDER_SERIES_NOT_EXACT_ISSUER_METRIC",
            "CANDIDATE_AVAILABLE_NOT_YET_FROZEN"))

    def test_unknown_official_release_clock_disables_freeze(self):
        s=copy.deepcopy(self.sources)
        new={"ccy":"NZD","date":"2026-11-18",
             "time_local":None,"timezone":"Pacific/Auckland",
             "event_type":"INFLATION","title":"Consumers price index",
             "reference_period":"October 2026",
             "importance":"HIGH","quality":"OFFICIAL_PROVISIONAL",
             "source_family":"Stats NZ"}
        s["official_calendar"]["events"].append(new)
        b=m.build(now=NOW,inputs=s)
        e=next(x for x in b["events"] if x["event_key"]==m.exact_event_key(new))
        self.assertEqual(e["status"],"MISSING_OFFICIAL_INTRADAY_RELEASE_TIME")
        self.assertIsNone(e["scheduled_release_utc"])
        self.assertFalse(e["official_issuer_parser_supported"])
        self.assertIsNone(e["actual_minus_frozen_consensus_pp"])

    def test_reject_unsigned_changed_actual_and_changed_event_roster(self):
        s=copy.deepcopy(self.sources)
        s["first_seen_actual"][0]["actual_percent"]=10
        with self.assertRaises(ValueError):
            m.build(now=NOW,inputs=s)
        s=copy.deepcopy(self.sources)
        s["official_calendar"]["events"]=[
            x for x in s["official_calendar"]["events"]
            if not (x["ccy"]=="USD" and x["date"]=="2026-10-30")]
        with self.assertRaises(ValueError):
            m.build(now=NOW,inputs=s)

    def test_due_day_utc_clock_pre_and_post_not_calendar_guess(self):
        s=copy.deepcopy(self.sources)
        before=m.build(now=datetime(2026,11,10,13,29,tzinfo=timezone.utc),inputs=s)
        after=m.build(now=datetime(2026,11,10,13,31,tzinfo=timezone.utc),inputs=s)
        def find(book):
            return next(x for x in book["events"] if
                        x["ccy"]=="USD" and x["date"]=="2026-11-10") # date via issuer_date
        us_pre=next(x for x in before["events"] if x["ccy"]=="USD" and x["issuer_date"]=="2026-11-10")
        us_post=next(x for x in after["events"] if x["ccy"]=="USD" and x["issuer_date"]=="2026-11-10")
        self.assertEqual(us_pre["status"],"UPCOMING_NO_VERIFIED_EXACT_CONSENSUS")
        self.assertEqual(us_post["status"],"PAST_EVENT_NO_FROZEN_CONSENSUS")
        self.assertIsNone(us_post["issuer_actual_pct"])

    def test_separate_economic_event_from_28_pair_exposure(self):
        b=self.book
        self.assertEqual(len(b["events"]),20)
        for event in b["events"]:
            self.assertEqual(len(event["affected_pair_references"]),7)
            self.assertEqual(len(set(event["affected_pair_references"])),7)
            self.assertIsNone(event["actual_minus_frozen_consensus_pp"]) if \
                 event["ccy"] not in ("USD","CAD") else None
            self.assertEqual(event["fx_signals"],0)
        text=m.markdown(b)
        self.assertIn("Sorprese archiviate",text)
        self.assertIn("Nessun",text)
        self.assertIn("2026-11-10",text)
        self.assertIn("0.00",text)

    def test_forecast_timestamp_requires_aware_utc_and_dst_correct(self):
        with self.assertRaises(ValueError):
            m.build(now=datetime(2026,11,9,10,0),inputs=self.sources)
        e=next(x for x in self.sources["official_calendar"]["events"]
               if x["ccy"]=="USD" and x["date"]=="2026-11-10")
        self.assertEqual(m.scheduled(e).isoformat(),"2026-11-10T13:30:00+00:00")


if __name__=="__main__":
    unittest.main()
