#!/usr/bin/env python3
"""Negative/positive tests: stale statistical history is not a live CHF quote."""
import copy
import unittest
from datetime import date
from build_fxv2_chf_snb_history_feed_v1 import build, EVIDENCE_SCHEMA, SCHEMA, SOURCE


def item(day, two, ten):
    return {"date": day, "2Y": two, "10Y": ten,
            "curve_bp": round((ten - two) * 100, 3)}


ROWS = [item("2026-09-30", .287, .586),
        item("2026-10-29", .240, .503),
        item("2026-10-30", .238, .505)]
EVIDENCE = {
    "schema": EVIDENCE_SCHEMA, "status": "OFFICIAL_PAIRED_HISTORY_NOT_CURRENT",
    "source": SOURCE, "source_response_sha256": "a" * 64,
    "paired_source_ready_for_historical_review": True,
    "writes_operational_rates": False,
    "eligible_for_automatic_promotion": False,
    "eligible_for_core_signals": False,
    "eligible_for_backtests": False,
    "current_session_government_rates_certified": False,
    "source_latest_vintage_not_first_release_pit": True,
    "historic_gap_backfilled_from_observations_not_interpolated": True,
    "unmatched_or_weekend_dates_fabricated": False,
    "base_date": "2026-09-30", "last_common_date": "2026-10-30",
    "last_common_2Y": .238, "last_common_10Y": .505,
    "paired_source_rows": ROWS, "matched_paired_rows": 3, "new_paired_rows": 2
}


class CHFHistoryFeed(unittest.TestCase):
    def setUp(self):
        self.e = copy.deepcopy(EVIDENCE)

    def check(self, previous=None, today=date(2026, 11, 5)):
        return build(self.e, previous, today)

    def test_stale_live_rate_is_valid_historical_series(self):
        report = self.check()
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["observation_count"], 3)
        self.assertEqual(report["last_observation_date"], "2026-10-30")
        self.assertFalse(report["eligible_for_core"])
        self.assertFalse(report["eligible_for_fx_engine"])
        self.assertFalse(report["eligible_for_backtests"])
        self.assertFalse(report["current_session_government_rates_certified"])

    def test_duplicate_source_is_noop(self):
        first = self.check()
        self.assertEqual(self.check(first), first)

    def test_add_new_observation_preserves_older(self):
        first = self.check()
        self.e["status"] = "PAIRED_OFFICIAL_HISTORY_READY_FOR_REVIEW"
        last = item("2026-11-03", .230, .520)
        self.e["paired_source_rows"].append(last)
        self.e["last_common_date"] = last["date"]
        self.e["last_common_2Y"] = last["2Y"]
        self.e["last_common_10Y"] = last["10Y"]
        self.e["matched_paired_rows"] = 4
        self.e["new_paired_rows"] = 3
        newer = self.check(first)
        self.assertEqual(newer["observation_count"], 4)

    def test_reject_unverified_or_old(self):
        for field, value in [
            ("paired_source_ready_for_historical_review", False),
            ("current_session_government_rates_certified", True),
            ("eligible_for_backtests", True),
            ("source", "https://invalid.example"),
            ("source_response_sha256", ""),
            ("matched_paired_rows", 27),
            ("historic_gap_backfilled_from_observations_not_interpolated", False),
        ]:
            with self.subTest(field=field):
                candidate = copy.deepcopy(self.e)
                candidate[field] = value
                with self.assertRaises(ValueError):
                    build(candidate, today=date(2026, 11, 5))
        with self.assertRaises(ValueError):
            self.check(today=date(2026, 12, 16))

    def test_reject_source_revisions_weekends_and_unit_errors(self):
        first = self.check()
        self.e["paired_source_rows"][1]["2Y"] = .290
        with self.assertRaises(ValueError):
            self.check(first)
        self.e = copy.deepcopy(EVIDENCE)
        self.e["paired_source_rows"][1]["date"] = "2026-10-31"
        with self.assertRaises(ValueError):
            self.check()
        self.e = copy.deepcopy(EVIDENCE)
        self.e["paired_source_rows"][1]["10Y"] = 5.03
        with self.assertRaises(ValueError):
            self.check()


if __name__ == "__main__":
    unittest.main(verbosity=2)
