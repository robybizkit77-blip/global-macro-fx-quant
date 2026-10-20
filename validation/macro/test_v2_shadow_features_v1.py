#!/usr/bin/env python3
"""Deterministic and negative PIT tests; fixtures are NOT economic source data."""
from __future__ import annotations

import copy
import unittest

from validation.macro.v2_shadow_features_v1 import (
    SCHEMA, audit_current_inventory, build_features,
)


def fixture():
    rows = [
        ("2026-01", "2026-02-02T09:00:00+00:00", 1.0),
        ("2026-02", "2026-03-02T09:00:00+00:00", 2.0),
        ("2026-03", "2026-04-02T09:00:00+00:00", 4.0),
        ("2026-04", "2026-05-02T09:00:00+00:00", 3.0),
    ]
    return {
        "schema": SCHEMA,
        "as_of": "2026-05-05T12:00:00+00:00",
        "currency": "USD",
        "pillar": "growth",
        "series_id": "SYNTHETIC_GROWTH_TEST",
        "frequency": "M", "unit": "index", "max_lag_periods": 1,
        "source": {"authority": "TEST_ONLY", "source_id": "TEST_V1",
                   "transport": "SYNTHETIC_FIXTURE"},
        "vintages": [
            {"observation_period": p, "released_at": t, "value": v,
             "kind": "FIRST", "evidence_ref": "FIXTURE_" + p}
            for p, t, v in rows
        ],
    }


class MacroV2ShadowFeatureTests(unittest.TestCase):
    def test_pit_raw_level_direction_velocity_acceleration_turn(self):
        out = build_features(fixture())
        self.assertEqual(out["level"], 3)
        self.assertEqual(out["direction"], "DOWN")
        self.assertEqual(out["velocity_per_period"], -1)
        self.assertEqual(out["acceleration_per_period_squared"], -3)
        self.assertEqual(out["turning_point"], "UP_TO_DOWN")
        self.assertEqual(out["selected_observations"], 4)
        self.assertFalse(out["ready_for_scoring"])
        self.assertFalse(out["safe_to_publish_new_D"])
        self.assertFalse(out["safe_to_update_pair_theses"])
        self.assertIsNone(out["numeric_pillar_score"])
        self.assertIsNone(out["economic_cycle"])

    def test_future_revision_never_leaks_into_earlier_cutoff(self):
        m = fixture()
        m["vintages"].append({
            "observation_period": "2026-03",
            "released_at": "2026-05-08T09:00:00+00:00",
            "value": 1.0, "kind": "REVISION", "evidence_ref": "TEST_REVISION",
        })
        early = build_features(m)
        self.assertEqual(early["velocity_per_period"], -1)
        self.assertEqual(early["acceleration_per_period_squared"], -3)
        m["as_of"] = "2026-05-09T12:00:00+00:00"
        later = build_features(m)
        self.assertEqual(later["velocity_per_period"], 2)
        self.assertEqual(later["acceleration_per_period_squared"], 3)
        self.assertEqual(later["turning_point"], "DOWN_TO_UP")
        self.assertNotEqual(early["feature_fingerprint_sha256"],
                            later["feature_fingerprint_sha256"])

    def test_latest_release_after_cutoff_excluded(self):
        m = fixture()
        m["as_of"] = "2026-05-01T12:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "four point-in-time"):
            build_features(m)

    def test_naive_release_clock_is_rejected(self):
        m = fixture()
        m["vintages"][0]["released_at"] = "2026-02-02T09:00:00"
        with self.assertRaisesRegex(ValueError, "offset-aware"):
            build_features(m)

    def test_naive_asof_clock_is_rejected(self):
        m = fixture()
        m["as_of"] = "2026-05-05T12:00:00"
        with self.assertRaisesRegex(ValueError, "offset-aware"):
            build_features(m)

    def test_missing_first_release_fails_closed(self):
        m = fixture()
        m["vintages"][0]["kind"] = "REVISION"
        with self.assertRaisesRegex(ValueError, "exactly one first"):
            build_features(m)

    def test_duplicate_first_release_fails_closed(self):
        m = fixture()
        row = copy.deepcopy(m["vintages"][0])
        row["released_at"] = "2026-02-03T09:00:00+00:00"
        m["vintages"].append(row)
        with self.assertRaisesRegex(ValueError, "exactly one first"):
            build_features(m)

    def test_revision_before_first_release_fails_closed(self):
        m = fixture()
        m["vintages"].append({
            "observation_period": "2026-02",
            "released_at": "2026-02-15T09:00:00+00:00",
            "value": 5.0, "kind": "REVISION", "evidence_ref": "IMPOSSIBLE",
        })
        with self.assertRaisesRegex(ValueError, "revision before first"):
            build_features(m)

    def test_duplicate_vintage_timestamp_fails_closed(self):
        m = fixture()
        row = copy.deepcopy(m["vintages"][0])
        row["kind"] = "REVISION"
        m["vintages"].append(row)
        with self.assertRaisesRegex(ValueError, "duplicate release timestamp"):
            build_features(m)

    def test_no_invented_calendar_periods(self):
        m = fixture()
        m["vintages"][1]["observation_period"] = "2025-12"
        with self.assertRaisesRegex(ValueError, "missing observation interval"):
            build_features(m)

    def test_stale_series_rejected(self):
        m = fixture()
        m["as_of"] = "2026-08-03T12:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "staleness tolerance"):
            build_features(m)

    def test_secondary_transport_rejected(self):
        m = fixture()
        m["source"]["transport"] = "SECONDARY_MIRROR"
        with self.assertRaisesRegex(ValueError, "secondary transport"):
            build_features(m)

    def test_evidence_required_even_for_synthetic(self):
        m = fixture()
        m["vintages"][1]["evidence_ref"] = ""
        with self.assertRaisesRegex(ValueError, "evidence reference"):
            build_features(m)

    def test_nonfinite_and_bool_are_not_observations(self):
        for value in (float("nan"), float("inf"), True, None):
            with self.subTest(value=repr(value)):
                m = fixture()
                m["vintages"][0]["value"] = value
                with self.assertRaisesRegex(ValueError, "finite observation"):
                    build_features(m)

    def test_future_period_with_premature_release_fails(self):
        m = fixture()
        m["vintages"][0]["released_at"] = "2025-12-31T09:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "precedes its observation"):
            build_features(m)

    def test_quarterly_calendar_and_mixed_frequency_guard(self):
        m = fixture()
        m["frequency"] = "Q"
        m["max_lag_periods"] = 1
        for row, period, when in zip(m["vintages"],
                                      ("2025Q3", "2025Q4", "2026Q1", "2026Q2"),
                                      ("2025-11-02T09:00:00Z", "2026-02-02T09:00:00Z",
                                       "2026-05-02T09:00:00Z", "2026-08-02T09:00:00Z")):
            row["observation_period"] = period
            row["released_at"] = when
        m["as_of"] = "2026-08-04T12:00:00Z"
        out = build_features(m)
        self.assertEqual(out["frequency"], "Q")
        self.assertEqual(out["latest_period"], "2026Q2")
        self.assertEqual(out["velocity_per_period"], -1)
        m["vintages"][0]["observation_period"] = "2025-07"
        with self.assertRaisesRegex(ValueError, "quarterly period"):
            build_features(m)

    def test_computation_does_not_mutate_source_input(self):
        m = fixture()
        before = copy.deepcopy(m)
        a, b = build_features(m), build_features(m)
        self.assertEqual(m, before)
        self.assertEqual(a, b)

    def test_live_inventory_only_never_certifies_score_pit(self):
        report = audit_current_inventory()
        self.assertEqual(report["currency_count"], 8)
        self.assertEqual(report["inflation_labour_registered"], 16)
        self.assertGreater(report["growth_observation_series_total"], 0)
        self.assertFalse(report["ready_for_live_feature_replay"])
        self.assertFalse(report["ready_for_scoring"])
        self.assertFalse(report["safe_to_publish_new_D"])
        self.assertFalse(report["writes_live_data"])


if __name__ == "__main__":
    unittest.main()
