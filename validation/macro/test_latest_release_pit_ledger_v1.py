#!/usr/bin/env python3
"""PIT-date evidence negative tests from pinned official G8 source records."""
import copy
import unittest
from datetime import date

from validation.macro.latest_release_pit_ledger_v1 import (
    ROOT, build_ledger, collect_candidates, resolved_time, iso_day,
)

TODAY = date(2026, 10, 20)


class LatestReleaseLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.anchors = collect_candidates(ROOT / "validation/macro")

    def run_receipt(self, records=None):
        return build_ledger(ROOT, TODAY, self.anchors if records is None else records)

    def test_strict_latest_period_evidence_and_withheld(self):
        out = self.run_receipt()
        self.assertEqual(out["source_lineage"], "PASS")
        self.assertEqual(out["observations_checked"], 16)
        self.assertEqual(sum(out["counts"].values()), 16)
        self.assertEqual(out["counts"]["FULL_RELEASE_INSTANT"], 4)
        self.assertEqual(out["counts"]["WITHHELD_EXACT_PERIOD_EVIDENCE"], 0)
        self.assertEqual(out["counts"]["WITHHELD_OFFICIAL_SOURCE_VALUE_CONFLICT"], 1)
        self.assertEqual(out["counts"]["DATE_ONLY"], 11)
        self.assertFalse(out["safe_to_promote_macro_labels"])
        self.assertFalse(out["safe_to_publish_new_D"])
        self.assertFalse(out["historical_vintage_series_available"])

    def test_new_latest_official_web_anchors_are_current_period_specific(self):
        out = self.run_receipt()
        usd = out["observations"]["USD.inflation"]
        self.assertEqual(usd["current_observation_period"], "2026-09")
        self.assertEqual(usd["release"]["first_release_date"], "2026-10-14")
        self.assertEqual(usd["release"]["first_release_timestamp_utc"],
                         "2026-10-14T12:30:00+00:00")
        self.assertTrue(usd["release"]["latest_web_release_unhashed"])
        self.assertEqual(out["observations"]["CAD.labour"]["release"]["first_release_date"],
                         "2026-10-09")
        self.assertEqual(out["observations"]["AUD.labour"]["release"]["first_release_timestamp_utc"],
                         "2026-10-15T00:30:00+00:00")
        self.assertEqual(out["observations"]["CAD.inflation"]["release"]["first_release_date"],
                         "2026-10-19")
        self.assertEqual(out["observations"]["JPY.labour"]["release"]["first_release_date"],
                         "2026-10-02")

    def test_gbp_rolling_three_month_vintage_conflict_stays_withheld(self):
        r = self.run_receipt()["observations"]["GBP.labour"]
        self.assertEqual(r["current_observation_period"], "2026-07-01")
        self.assertEqual(r["latest_transformed_observation"], 4.7)
        self.assertEqual(r["release"]["status"], "WITHHELD_OFFICIAL_SOURCE_VALUE_CONFLICT")
        self.assertEqual(r["release"]["source_disagreement"]["official_first_release_value"], 4.9)
        self.assertEqual(r["release"]["source_disagreement"]["period"], "2026-07")
        self.assertFalse(r["release"]["historical_backtest_safe_for_all_periods"])

    def test_date_only_is_never_intraday_eligible(self):
        out = self.run_receipt()
        eur = out["observations"]["EUR.inflation"]["release"]
        self.assertEqual(eur["first_release_date"], "2026-10-02")
        self.assertIsNone(eur["first_release_timestamp_utc"])
        self.assertTrue(eur["date_only_not_eligible_for_intraday_PIT"])

    def test_chf_archival_utc_instant_is_properly_converted(self):
        chf = self.run_receipt()["observations"]["CHF.inflation"]["release"]
        self.assertEqual(chf["status"], "FULL_RELEASE_INSTANT")
        self.assertEqual(chf["first_release_timestamp_utc"], "2026-10-01T06:30:00+00:00")

    def test_jpy_release_jst_crosses_previous_utc_day(self):
        jpy = self.run_receipt()["observations"]["JPY.inflation"]["release"]
        self.assertEqual(jpy["status"], "FULL_RELEASE_INSTANT")
        self.assertEqual(jpy["first_release_timestamp_utc"], "2026-09-17T23:30:00+00:00")

    def test_future_release_in_evidence_fails_closed(self):
        data = copy.deepcopy(self.anchors)
        row = data[("EUR.inflation", "2026-09")][0]
        row["date"] = "2026-10-21"
        with self.assertRaisesRegex(ValueError, "future official release metadata"):
            self.run_receipt(data)

    def test_same_period_wrong_value_fails_closed(self):
        data = copy.deepcopy(self.anchors)
        row = data[("EUR.inflation", "2026-09")][0]
        row["value"] = 99.5
        # The other anchored sources for the same period still agree; test
        # that a single inconsistent official source cannot be silently used.
        with self.assertRaisesRegex(ValueError, "conflicting current-period pinned official value"):
            self.run_receipt(data)

    def test_inconsistent_same_period_official_dates_fail_closed(self):
        data = copy.deepcopy(self.anchors)
        row = copy.deepcopy(data[("EUR.inflation", "2026-09")][0])
        row["date"] = "2026-10-03"
        data[("EUR.inflation", "2026-09")].append(row)
        with self.assertRaisesRegex(ValueError, "incompatible official first-release"):
            self.run_receipt(data)

    def test_pre_observation_release_date_fails_closed(self):
        data = copy.deepcopy(self.anchors)
        for row in data[("EUR.inflation", "2026-09")]:
            row["date"] = "2026-08-29"
        with self.assertRaisesRegex(ValueError, "publication before reference month"):
            self.run_receipt(data)

    def test_missing_release_time_does_not_become_midnight(self):
        rec = {"date": "2026-10-02", "release_time_utc": None, "release_time_jst": None}
        self.assertIsNone(resolved_time(rec))

    def test_utc_clock_and_jst_clock_simultaneously_rejected(self):
        rec = {"date": "2026-10-02", "release_time_utc": "06:00",
               "release_time_jst": "09:00"}
        with self.assertRaisesRegex(ValueError, "conflicting time zones"):
            resolved_time(rec)

    def test_malformed_date_rejected(self):
        with self.assertRaises(ValueError):
            iso_day("2026-13-01", "test")


if __name__ == "__main__":
    unittest.main()
