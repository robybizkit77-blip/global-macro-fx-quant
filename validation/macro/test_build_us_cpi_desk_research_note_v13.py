"""CPI V13 research note: exact issuer record, no false market-reaction proof."""
from __future__ import annotations

import copy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest

from validation.macro import build_us_cpi_desk_research_note_v13 as v13
from validation.macro import capture_us_cpi_exact_actuals_v10 as v10
from validation.macro import preflight_us_cpi_official_actual_v8 as bls
from validation.macro.freeze_exact_metric_forecasts_v9 import read_rows
from validation.macro.test_g8_metric_issuer_readiness_v8 import mock_bls
from validation.macro.test_capture_us_cpi_exact_actuals_v10 import PARTIAL

BEFORE = datetime(2026, 11, 9, 19, 5, tzinfo=timezone.utc)
AFTER = datetime(2026, 11, 10, 13, 34, tzinfo=timezone.utc)
SEEN = AFTER + timedelta(seconds=13)
RATES = {
    "USD": {"date": "2026-11-06", "2Y": 4.51, "10Y": 4.86,
            "quality": "FULL_CURRENT_OFFICIAL", "source": "Treasury EOD"}
}
FX = {"base": "EUR", "source": "ECB daily reference",
      "rows": [{"Date": "2026-11-09", "USD": 1.1193}]}
OIS = {"currencies": {"USD": {
    "operational_status": "WITHHELD", "quality": "ESTIMATED_INFORMATIONAL",
    "as_of": "2026-11-06",
}}}


class CPIDeskNoteV13(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forecasts = read_rows(v10.FORECAST_LEDGER)

    def official(self, hm=0.4, cm=0.3, hy=3.4, cy=2.7):
        raw = mock_bls(
            "October", "Tuesday, November 10, 2026",
            hmo=f"increased {hm}", cmo=f"rose {cm}",
            hyo=f"increased {hy}", cyo=f"rose {cy}")
        rows, receipt = v10.capture(
            self.forecasts, [], AFTER,
            fetch=lambda url, host: (raw, url),
            observed_clock=lambda: SEEN,
        )
        self.assertEqual(receipt["new_metrics_archived"], 4)
        return rows

    def note(self, rows, now=None, **overrides):
        return v13.build(
            self.forecasts, rows, rates=overrides.get("rates", RATES),
            fx=overrides.get("fx", FX), ois=overrides.get("ois", OIS),
            now=now or SEEN
        )

    def test_before_issuer_release_no_actual_and_no_synthetic_surprise(self):
        x = self.note([], now=BEFORE)
        self.assertEqual(x["status"], "AWAITING_BLS_RELEASE_NO_ACTUAL")
        self.assertEqual(x["metric_count"], 0)
        self.assertEqual([m["metric_id"] for m in x["metrics"]],
                         list(bls.KEYS))
        self.assertTrue(all(m["actual_percent"] is None for m in x["metrics"]))
        self.assertEqual(sum(m["secondary_forecast_percent"] is not None
                             for m in x["metrics"]), 2)
        self.assertIsNone(x["actual_source_url"])
        self.assertIsNone(x["FX_signal"])
        self.assertFalse(x["writes_live_data"])
        self.assertNotIn("futures change", v13.markdown(x).lower())

    def test_after_release_without_archived_issuer_data_remains_pending(self):
        x = self.note([], now=AFTER)
        self.assertEqual(x["status"], "AWAITING_VALIDATED_V10_ACTUAL_OR_ARCHIVE")
        self.assertIn("non risulta ancora acquisito", v13.markdown(x))
        self.assertEqual(x["metric_count"], 0)

    def test_shutdown_gap_has_two_real_monthly_and_explicit_absent_annual(self):
        rows, receipt = v10.capture(
            self.forecasts, [], AFTER,
            fetch=lambda url, host: (PARTIAL, url),
            observed_clock=lambda: SEEN)
        self.assertEqual(receipt["new_metrics_archived"], 2)
        x = self.note(rows)
        self.assertEqual(x["status"], "TWO_OFFICIAL_MONTHLY_METRICS_ANNUAL_UNAVAILABLE")
        self.assertEqual(x["metric_count"], 2)
        byid = {m["metric_id"]: m for m in x["metrics"]}
        self.assertAlmostEqual(byid["US_CPI_U_HEADLINE_MOM_SA"]["actual_percent"], 0.4)
        self.assertAlmostEqual(byid["US_CPI_U_CORE_MOM_SA"]["actual_percent"], 0.3)
        for mid in v10.ANNUAL:
            self.assertIsNone(byid[mid]["actual_percent"])
            self.assertEqual(byid[mid]["officially_unavailable_reason"],
                             "OCT_2025_BASE_NOT_COLLECTED")
        self.assertIn("non pubblicati", x["desk_observation"])
        self.assertIn("base 2025 mancante", v13.markdown(x))
        self.assertFalse(x["market_context"]["market_causality_established"])
        self.assertIsNone(x["FX_signal"])

    def test_four_official_metrics_and_secondary_forecast_deltas_only(self):
        x = self.note(self.official())
        self.assertEqual(x["status"], "FOUR_OFFICIAL_METRICS_VALIDATED_RESEARCH_ONLY")
        self.assertEqual(x["metric_count"], 4)
        self.assertEqual(x["actual_source_url"], bls.SOURCE)
        self.assertEqual(x["first_runner_observed_at_utc"], "2026-11-10T13:34:13Z")
        byid = {m["metric_id"]: m for m in x["metrics"]}
        self.assertAlmostEqual(byid["US_CPI_U_HEADLINE_MOM_SA"]
                               ["delta_vs_secondary_forecast_pp"], 0.1)
        self.assertAlmostEqual(byid["US_CPI_U_CORE_MOM_SA"]
                               ["delta_vs_secondary_forecast_pp"], 0.1)
        self.assertIsNone(byid["US_CPI_U_HEADLINE_YOY_NSA"]
                          ["secondary_forecast_percent"])
        self.assertIsNone(byid["US_CPI_U_CORE_YOY_NSA"]
                          ["delta_vs_secondary_forecast_pp"])
        self.assertTrue(all(m["delta_is_market_surprise_certified"] is False
                            for m in x["metrics"]))
        self.assertIn("Entrambe le letture mensili superano", x["economic_hypothesis"])
        m = v13.markdown(x)
        self.assertIn("Forecast secondario", m)
        self.assertIn("0,10 pp", m)
        self.assertIn("non reazione intraday al CPI", m)
        self.assertIn("nessuno", m.lower())

    def test_both_monthly_below_secondary_forecasts(self):
        x = self.note(self.official(hm=0.1, cm=0.1))
        self.assertIn("inferiori ai forecast", x["economic_hypothesis"])
        self.assertTrue(x["market_context"]["synchronized_release_window_quotes_verified"] == 0)

    def test_mixed_secondary_forecast_comparison_not_force_policy_story(self):
        x = self.note(self.official(hm=0.4, cm=0.1))
        self.assertIn("misto", x["economic_hypothesis"])
        self.assertEqual(x["trade_attractiveness"],
                         "NOT_ASSESSED_NO_VERIFIED_EVENT_WINDOW")

    def test_no_forged_actual_partial_snapshot_or_edited_forecast(self):
        rows = self.official()
        for invalid in (rows[:3], rows + rows[:1]):
            with self.subTest(size=len(invalid)), self.assertRaises(ValueError):
                self.note(invalid)
        changed = copy.deepcopy(rows)
        changed[0]["actual_percent"] = 19
        with self.assertRaises(ValueError):
            self.note(changed)
        bad = copy.deepcopy(self.forecasts)
        bad[-1]["forecast_value_percent"] = 99
        with self.assertRaises(ValueError):
            v13.build(bad, rows, now=SEEN)

    def test_no_future_first_observed_actual(self):
        with self.assertRaisesRegex(ValueError, "before observation"):
            self.note(self.official(), now=AFTER)

    def test_market_daily_snapshots_remain_context_even_post_release(self):
        x = self.note(self.official(), now=SEEN + timedelta(hours=5))
        mr = x["market_context"]
        self.assertEqual(mr["treasury"]["as_of_date"], "2026-11-06")
        self.assertEqual(mr["ecb_eurusd_fixing"]["as_of_date"], "2026-11-09")
        self.assertEqual(mr["fed_pricing"]["status"], "WITHHELD")
        self.assertFalse(mr["fed_pricing"]["intraday_policy_repricing_certified"])
        self.assertFalse(mr["market_causality_established"])
        self.assertEqual(mr["equity_gold_event_reaction"], "NOT_MEASURED")
        self.assertFalse(x["eligible_for_Core_Beta_Forward"])

    def test_future_dated_rates_or_fx_excluded_not_used_for_repricing(self):
        bad_rates = copy.deepcopy(RATES)
        bad_rates["USD"]["date"] = "2026-11-13"
        bad_fx = copy.deepcopy(FX)
        bad_fx["rows"].append({"Date": "2026-11-14", "USD": 1.1})
        x = self.note(self.official(), rates=bad_rates, fx=bad_fx)
        self.assertIsNone(x["market_context"]["treasury"])
        self.assertEqual(x["market_context"]["ecb_eurusd_fixing"]["as_of_date"],
                         "2026-11-09")
        self.assertFalse(x["market_context"]["market_causality_established"])

    def test_no_market_snapshots_still_renders_complete_safe_note(self):
        x = self.note(self.official(), rates={}, fx={}, ois={})
        m = v13.markdown(x)
        self.assertIn("nessun snapshot", m)
        self.assertIn("non disponibile", m)
        self.assertIn("NOT_AVAILABLE", m)
        self.assertIn("nessuno", m.lower())

    def test_strict_aware_time(self):
        with self.assertRaisesRegex(ValueError, "UTC-aware"):
            v13.build(self.forecasts, [], now=datetime(2026, 11, 10, 14, 0))

if __name__ == "__main__":
    unittest.main()
