import copy
import json
import unittest
from datetime import date

from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_growth_inflation_g8_desk_inventory_v1 import inspect, parse_reference_period


class G8GrowthInflationInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "live_data/sections/MACRO_SERIES.json").read_text())

    def row(self, result, currency, pillar):
        return next(r for r in result["rows"] if r["currency"] == currency and r["pillar"] == pillar)

    def test_all_eight_by_two_without_scoring(self):
        result = inspect(self.data)
        self.assertEqual(len(result["rows"]), 16)
        self.assertEqual({r["currency"] for r in result["rows"]}, set(self.data))
        # Fixed-format parser formerly dropped 11/16 slots; never assume monthly
        # or quarterly labels are invalid just because they are not full ISO dates.
        self.assertEqual(result["missing_valid_dated_value_slots"], 0)
        self.assertEqual(result["certified_first_release_slots"], 0)
        for key in ("economic_score_computed", "eligible_for_backtest",
                    "safe_to_publish_new_D", "safe_to_update_pair_theses", "writes_live_data"):
            self.assertFalse(result[key])
        for row in result["rows"]:
            self.assertFalse(row["release_timestamp_first_vintage_verified"])
            self.assertIsNone(row["growth_or_inflation_macro_score"])
            self.assertIsNone(row["release_age_days"])
            self.assertEqual(row["release_freshness"], "UNKNOWN_NO_RELEASE_TIMESTAMP")
            self.assertIsNotNone(row["reference_period_end"])
            self.assertGreaterEqual(row["reference_period_age_days"], 0)

    def test_monthly_eur_growth_is_observed_not_missing(self):
        row = self.row(inspect(self.data), "EUR", "growth")
        self.assertEqual(row["reference_period_raw"], "2026-07")
        self.assertEqual(row["reference_period_end"], "2026-07-31")
        self.assertEqual(row["reference_period_granularity"], "month")
        self.assertIsNone(row["latest_observed_on"])  # no invented precise day
        self.assertEqual(row["reference_period_age_days"], 84)
        self.assertEqual(row["research_freshness"], "REFERENCE_PERIOD_OLDER_THAN_EXPECTED_CADENCE")

    def test_quarterly_growth_is_not_mislabeled_stale_at_60_days(self):
        row = self.row(inspect(self.data), "NZD", "growth")
        self.assertEqual(row["reference_period_raw"], "2026-06")
        self.assertEqual(row["reference_period_end"], "2026-06-30")
        self.assertEqual(row["reference_period_granularity"], "quarter")
        self.assertEqual(row["reference_period_age_days"], 115)
        self.assertEqual(row["expected_cadence_heuristic_days"], 135)
        self.assertEqual(row["research_freshness"], "REFERENCE_PERIOD_WITHIN_EXPECTED_CADENCE")
        self.assertEqual(row["release_freshness"], "UNKNOWN_NO_RELEASE_TIMESTAMP")

    def test_quarter_and_month_formats_and_invalid_dates(self):
        self.assertEqual(parse_reference_period("2026Q2", "Q"), (date(2026, 6, 30), "quarter"))
        self.assertEqual(parse_reference_period("2026-09", "M"), (date(2026, 9, 30), "month"))
        self.assertEqual(parse_reference_period("2026-09-01", "M"), (date(2026, 9, 30), "month"))
        self.assertEqual(parse_reference_period("2026-09-01", "Q"), (date(2026, 9, 30), "quarter"))
        self.assertEqual(parse_reference_period("2026-09-15", "D"), (date(2026, 9, 15), "day"))
        for raw, frequency in (("2026-13", "M"), ("2026Q5", "Q"), ("2026Q2", "M"),
                               ("2026-07", "Q"), ("2026-02-30", "M"),
                               ("2026-09", "D"), ("2026-09-01junk", "M"),
                               ("", "M"), (None, "Q")):
            with self.subTest(raw=raw, frequency=frequency):
                self.assertIsNone(parse_reference_period(raw, frequency))

    def test_do_not_mutate_original_data(self):
        data = copy.deepcopy(self.data)
        self.assertEqual(inspect(data), inspect(data))
        self.assertEqual(data, self.data)

    def test_no_future_period_leakage(self):
        for future in ("2099-01-01", "2026-11", "2026Q4"):
            data = copy.deepcopy(self.data)
            for series in data["USD"]:
                if series.get("category") == "Crescita":
                    series["last_date"] = future
            result = inspect(data)
            row = self.row(result, "USD", "growth")
            self.assertEqual(row["research_freshness"], "NO_VALID_DATED_VALUE")
            self.assertIsNone(row["latest_observed_value"])
            self.assertGreaterEqual(result["missing_valid_dated_value_slots"], 1)

    def test_incomplete_current_month_excluded_without_inventing_release(self):
        data = copy.deepcopy(self.data)
        for series in data["EUR"]:
            if series.get("category") == "Crescita":
                series["last_date"] = "2026-10"
        result = inspect(data, as_of=date(2026, 10, 23))
        self.assertEqual(self.row(result, "EUR", "growth")["research_freshness"], "NO_VALID_DATED_VALUE")


if __name__ == "__main__":
    unittest.main()
