"""Adversarial daily observation tests: no intraday reactions or model updates."""
from __future__ import annotations

import copy
import json
import unittest
from validation.news_market_daily_proxy_v1 import (
    REG_PATH, FX_PATH, RATES_PATH, OIS_PATH, build,
)


def fixtures():
    return tuple(json.loads(p.read_text(encoding="utf-8")) for p in (
        REG_PATH, FX_PATH, RATES_PATH, OIS_PATH
    ))


class DailyPublicSourceProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.event, cls.fx, cls.rates, cls.ois = fixtures()

    def run_audit(self, *, as_of="2026-10-26", event=None, fx=None, rates=None, ois=None):
        return build(event or self.event, fx or self.fx, rates or self.rates,
                     ois or self.ois, as_of=as_of)

    def test_observed_fixes_around_bls_are_daily_not_intraday(self):
        result = self.run_audit()
        self.assertEqual(result["status"], "DAILY_REFERENCE_MOVEMENT_OBSERVED_NOT_INTRADAY")
        fx = result["observed_daily_fx_reference"]
        self.assertEqual(fx["previous_fixing_date"], "2026-10-01")
        self.assertEqual(fx["event_day_fixing_date"], "2026-10-02")
        self.assertEqual(fx["next_fixing_date"], "2026-10-05")
        self.assertEqual(fx["previous_fixing"], 1.1298)
        self.assertEqual(fx["event_day_fixing"], 1.1225)
        self.assertEqual(fx["next_fixing"], 1.1204)
        self.assertAlmostEqual(fx["previous_to_event_day_pips"], -73)
        self.assertAlmostEqual(fx["event_day_to_next_fixing_pips"], -21)
        self.assertEqual(fx["post_fixing_calendar_gap_days"], 3)
        self.assertFalse(fx["event_window_proof"])
        self.assertFalse(fx["fixing_time_verified_for_individual_day"])
        self.assertIsNone(result["estimated_intraday_reaction"])
        self.assertEqual(result["causal_attribution"], "NOT_ESTABLISHED")
        self.assertFalse(result["eligible_for_backtest"])
        self.assertFalse(result["safe_to_publish_live_data"])

    def test_treasury_daily_gap_refuses_fake_adjacent_change(self):
        usd = self.run_audit()["daily_us_2y_reference"]
        self.assertEqual(usd["status"], "DAILY_2Y_REFERENCE_ONLY")
        self.assertEqual(usd["event_date"], "2026-10-02")
        self.assertEqual(usd["event_date_yield_pct"], 4.83)
        self.assertEqual(usd["previous_observation_date"], "2026-09-28")
        self.assertEqual(usd["previous_observation_calendar_gap_days"], 4)
        self.assertFalse(usd["valid_adjacent_comparison"])
        self.assertIsNone(usd["daily_2y_change_bp"])
        self.assertFalse(usd["event_reaction_proof"])

    def test_futures_quote_from_three_weeks_later_is_excluded(self):
        self.assertEqual(self.run_audit()["event_date_ois_futures"]["status"],
                         "NOT_EVENT_DATE_ALIGNED")
        self.assertIsNone(self.run_audit()["event_date_ois_futures"]["estimated_6m_event_repricing_bp"])

    def test_point_in_time_cutoff_does_not_see_monday_future_fixing(self):
        result = self.run_audit(as_of="2026-10-02")
        self.assertEqual(result["status"], "INCOMPLETE_ADJACENT_ECB_FIXINGS")
        self.assertIsNone(result["observed_daily_fx_reference"])

    def test_no_observation_before_event(self):
        with self.assertRaisesRegex(ValueError,"as_of cannot precede"):
            self.run_audit(as_of="2026-10-01")

    def test_bad_fx_series_provenance_blocked(self):
        x = copy.deepcopy(self.fx)
        x["source_url"] = "https://example.com/fake"
        with self.assertRaisesRegex(ValueError, "ECB provenance"):
            self.run_audit(fx=x)

    def test_event_clock_mismatch_blocked(self):
        x = copy.deepcopy(self.event)
        x["event"]["expected_scheduled_utc"] = "2026-10-02T16:30:00Z"
        with self.assertRaisesRegex(ValueError, "unexpected scheduled"):
            self.run_audit(event=x)

    def test_negative_fixing_rejected(self):
        x = copy.deepcopy(self.fx)
        row = next(r for r in x["rows"] if r["Date"] == "2026-10-02")
        row["USD"] = -1.0
        with self.assertRaisesRegex(ValueError, "invalid EURUSD"):
            self.run_audit(fx=x)

    def test_duplicate_fixing_rejected(self):
        x = copy.deepcopy(self.fx)
        pos = next(i for i,r in enumerate(x["rows"]) if r["Date"]=="2026-10-02")
        x["rows"].insert(pos,dict(x["rows"][pos]))
        with self.assertRaisesRegex(ValueError, "unordered/duplicate"):
            self.run_audit(fx=x)

    def test_no_false_2y_if_source_quality_unverified(self):
        x = copy.deepcopy(self.rates)
        x["USD"]["quality"] = "WITHHELD"
        self.assertEqual(self.run_audit(rates=x)["daily_us_2y_reference"]["status"],
                         "SOURCE_QUALITY_NOT_ACCEPTED")

    def test_missing_event_day_ecb_fixing(self):
        x = copy.deepcopy(self.fx)
        x["rows"] = [r for r in x["rows"] if r["Date"] != "2026-10-02"]
        z=self.run_audit(fx=x)
        self.assertIsNone(z["observed_daily_fx_reference"])
        self.assertEqual(z["status"], "NO_EVENT_DATE_ECB_FIXING")

    def test_do_not_map_latest_ois_proxy_back_to_event_day(self):
        x = copy.deepcopy(self.ois)
        x["currencies"]["USD"]["as_of"] = "2026-10-02"
        z = self.run_audit(ois=x)["event_date_ois_futures"]
        self.assertEqual(z["status"], "DAILY_CONTEXT_NOT_EVENT_REPRICING")
        self.assertIsNone(z["estimated_6m_event_repricing_bp"])

    def test_missing_2y_history_rejected_as_context(self):
        x = copy.deepcopy(self.rates)
        x["USD"]["history2"]["values"].pop()
        self.assertEqual(self.run_audit(rates=x)["daily_us_2y_reference"]["status"],
                         "INCONSISTENT_2Y_HISTORY")


if __name__ == "__main__":
    unittest.main()
