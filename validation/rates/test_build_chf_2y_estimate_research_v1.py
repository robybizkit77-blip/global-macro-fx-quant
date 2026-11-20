import json
from datetime import date, timedelta
from math import sin
import unittest

from build_chf_2y_estimate_research_v1 import KEYS, SCHEMA, SNB_10Y_SOURCE, calibrate, update, weekdays


def spot(day, value):
    return {
        "schema": "GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1",
        "status": "OFFICIAL_PUBLISHED_10Y_INFORMATIONAL",
        "source_url": SNB_10Y_SOURCE, "currency": "CHF", "tenor": "10Y",
        "yield_type": "SWISS_CONFEDERATION_ZERO_COUPON_SPOT",
        "provenance": "SNB_PUBLIC_PAGE_DATED_EXACT_10Y",
        "has_current_2y": False, "eligible_for_backtests": False,
        "as_of": day, "value_percent": value, "source_html_sha256": "e" * 64,
    }


class ChfEstimateEvidence(unittest.TestCase):
    def test_calendar_horizons(self):
        self.assertEqual(weekdays(date(2026, 11, 9), date(2026, 11, 18)), 7)
        self.assertEqual(weekdays(date(2026, 11, 6), date(2026, 11, 9)), 1)

    def test_dates_roll_forward_without_revising_previous_observations(self):
        now = date(2026, 11, 20)
        initial = {"schema": SCHEMA, "research_only": True, "observations": []}
        seeded = update(initial, [spot("2026-11-18", 0.609)], now)
        merged = update(seeded, [spot("2026-11-19", 0.614)], now)
        self.assertEqual([x["date"] for x in merged["observations"]], ["2026-11-18", "2026-11-19"])
        self.assertEqual(merged, update(merged, [spot("2026-11-19", 0.614)], now))
        with self.assertRaisesRegex(ValueError, "revision"):
            update(merged, [spot("2026-11-19", 0.604)], now)
        with self.assertRaisesRegex(ValueError, "provenance"):
            update(merged, [spot("2026-11-23", 0.614)], now)
        with self.assertRaisesRegex(ValueError, "provenance"):
            update(merged, [{**spot("2026-11-20", 0.614), "tenor": "2Y"}], now)

    def test_calibration_separates_fit_and_holdout(self):
        days = []
        day = date(2022, 1, 3)
        while day <= date(2026, 11, 19):
            if day.weekday() < 5:
                days.append(day.isoformat())
            day += timedelta(days=1)
        # Deliberately generated test-only observations.
        ten = [0.6 + 0.35 * sin(i / 11) for i in range(len(days))]
        two = [0.75 * x + 0.004 * sin(i / 3) for i, x in enumerate(ten)]
        raw = json.dumps({"timeseries": [
            {"metadata": {"key": KEYS[tenor], "unit": "Percent", "frequency": "P1D"},
             "values": [{"date": d, "value": v} for d, v in zip(days, values)]}
            for tenor, values in (("2Y", two), ("10Y", ten))
        ]}).encode()
        anchor = {"date": days[0], "2Y": two[0], "10Y": ten[0]}
        calibration = calibrate(raw, anchor, date(2026, 11, 20))
        self.assertEqual(calibration["train_before"], "2026-01-01")
        self.assertEqual(calibration["holdout_through"], "2026-11-19")
        self.assertTrue(calibration["holdout_nonoverlapping"])
        fit = calibration["horizons"]["7"]
        self.assertAlmostEqual(fit["beta"], 0.75, places=2)
        self.assertGreaterEqual(fit["holdout_count"], 20)
        self.assertLess(fit["mae_bp"], fit["flat_mae_bp"])


if __name__ == "__main__":
    unittest.main()
