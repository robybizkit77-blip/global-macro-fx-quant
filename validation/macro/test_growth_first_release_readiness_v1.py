#!/usr/bin/env python3
"""Real-source G8 Growth first-release evidence tests, including NZ GDP metric."""
import copy
import json
import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from validation.macro.growth_first_release_readiness_v1 import (
    ROOT, ATTESTATIONS, build, validate_series,
)

TODAY = datetime.now(ZoneInfo('Europe/Rome')).date()


class GrowthReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.attestations = json.loads(ATTESTATIONS.read_text(encoding="utf-8"))

    def run_gate(self, edit=None, feeds=None):
        att = copy.deepcopy(self.attestations)
        if edit:
            edit(att)
        return build(ROOT, TODAY, attestations=att, feeds=feeds)

    def test_21_source_inventory_and_blocked_score(self):
        result = self.run_gate()
        self.assertEqual(result["growth_country_count"], 8)
        self.assertEqual(result["growth_series_count"], 21)
        self.assertEqual(result["counts"]["official_latest_value_date_match"], 2)
        self.assertEqual(result["counts"]["no_first_release_evidence"], 19)
        self.assertEqual(result["counts"]["missing_frequency_declared"], 4)
        self.assertEqual(result["counts"]["missing_unit_declared"], 4)
        self.assertEqual(result["counts"]["archival_first_release_vintage_certified"], 0)
        self.assertEqual(result["unresolved_core_latest_release_target_count"], 0)
        self.assertEqual(result["unresolved_core_latest_release_targets"], [])
        self.assertFalse(result["safe_to_refresh_growth_score"])
        self.assertFalse(result["safe_to_refresh_qualitative_macro_labels"])
        self.assertFalse(result["safe_to_publish_D"])
        self.assertFalse(result["historical_value_vintages_certified"])

    def test_aud_official_first_release_timestamp(self):
        result = self.run_gate()
        row = result["growth"]["AU_REAL_GDP_QOQ_ABS_history_value"]
        self.assertEqual(row["latest_value"], 0.4)
        self.assertEqual(row["latest_period"], "2026-06")
        self.assertEqual(row["official_release"]["release_date"], "2026-09-02")
        self.assertEqual(row["official_release"]["release_instant_utc"],
                         "2026-09-02T01:30:00+00:00")
        self.assertFalse(row["official_release"]["full_historical_PIT_vintage"])

    def test_nzd_yoy_26_is_not_annual_average_17(self):
        row = self.run_gate()["growth"]["NZ_REAL_GDP_Q_history_value"]
        self.assertEqual(row["latest_value"], 2.6)
        self.assertEqual(row["official_release"]["separate_metric_not_to_conflate"]["value"], 1.7)
        self.assertIn("SAME quarter", row["official_release"]["official_metric_definition"])
        self.assertIsNone(row["official_release"]["release_instant_utc"])

    def test_explicit_wrong_annual_average_as_first_release_is_rejected(self):
        def edit(a):
            a["attestations"][1]["first_release_value"] = 1.7
        with self.assertRaisesRegex(ValueError, "OFFICIAL_FIRST_RELEASE_VALUE_DISAGREES"):
            self.run_gate(edit)

    def test_removing_required_metric_disambiguation_is_rejected(self):
        def edit(a):
            a["attestations"][1].pop("comparison_must_not_use")
        with self.assertRaisesRegex(ValueError, "YoY/annual-average distinction"):
            self.run_gate(edit)

    def test_aud_quarterly_growth_cannot_substitute_annual_unit(self):
        def edit(a):
            a["attestations"][0]["units"] = "% YoY"
        with self.assertRaisesRegex(ValueError, "metric unit not locked"):
            self.run_gate(edit)

    def test_attestation_wrong_period_not_repurposed(self):
        def edit(a):
            a["attestations"][0]["observation_period"] = "2026-03"
        with self.assertRaisesRegex(ValueError, "not for latest observation"):
            self.run_gate(edit)

    def test_forged_publisher_domain_fails_closed(self):
        def edit(a):
            a["attestations"][0]["official_source_url"] = "https://abs.gov.au.evil.example/gdp"
        with self.assertRaisesRegex(ValueError, "publisher mismatch"):
            self.run_gate(edit)

    def test_future_first_release_date_is_rejected(self):
        def edit(a):
            a["attestations"][0]["release_date"] = (TODAY + timedelta(days=45)).isoformat()
        with self.assertRaisesRegex(ValueError, "future release date"):
            self.run_gate(edit)

    def test_naive_official_timestamp_is_rejected(self):
        def edit(a):
            a["attestations"][0]["release_timestamp_local"] = "2026-09-02T11:30:00"
        with self.assertRaisesRegex(ValueError, "naive clock"):
            self.run_gate(edit)

    def test_forged_source_sha_not_accepted(self):
        def edit(a):
            a["attestations"][0]["source_artifact_sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "unchecked source artifact hash"):
            self.run_gate(edit)

    def test_duplicate_first_release_attestation_rejected(self):
        def edit(a):
            a["attestations"].append(copy.deepcopy(a["attestations"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate official Growth"):
            self.run_gate(edit)

    def test_unregistered_source_attestation_rejected(self):
        def edit(a):
            a["attestations"][0]["series_id"] = "FAKE_GDP"
        with self.assertRaisesRegex(ValueError, "nonexistent/deleted Growth"):
            self.run_gate(edit)

    def test_missing_frequency_in_us_history_not_silently_certified(self):
        row = {
            "id": "US_TEST", "dates": ["2026-05-01", "2026-06-01"],
            "values": [2., 3.], "last_date": "2026-06-01", "last_value": 3.,
            "frequency": "", "unit": ""
        }
        v = validate_series(row, TODAY)
        self.assertFalse(v["frequency_declared"])
        self.assertFalse(v["unit_declared"])

    def test_unsorted_growth_dates_rejected(self):
        row = {
            "id": "US_TEST", "dates": ["2026-06-01", "2026-05-01"],
            "values": [2., 3.], "last_date": "2026-05-01", "last_value": 3.,
            "frequency": "M", "unit": "index"
        }
        with self.assertRaisesRegex(ValueError, "unsorted/duplicate"):
            validate_series(row, TODAY)

    def test_future_growth_observation_rejected(self):
        row = {
            "id": "US_TEST", "dates": ["2026-06-01", (TODAY + timedelta(days=90)).isoformat()],
            "values": [2., 3.], "last_date": (TODAY + timedelta(days=90)).isoformat(), "last_value": 3.,
            "frequency": "M", "unit": "index"
        }
        with self.assertRaisesRegex(ValueError, "future Growth"):
            validate_series(row, TODAY)


if __name__ == "__main__":
    unittest.main()
