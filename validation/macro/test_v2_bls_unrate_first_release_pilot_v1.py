#!/usr/bin/env python3
"""BLS page-anchored pilot tests. Replay is research-only, not a strategy."""
import copy
import json
import math
import unittest

from validation.macro.v2_bls_unrate_first_release_pilot_v1 import (
    MANIFEST, PINNED_RELEASES, replay, validate_official_attestations,
)


def data():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class BLSUnrateHistoricalPITPilotTests(unittest.TestCase):
    def test_five_release_web_attestations_pinned(self):
        m = data()
        validate_official_attestations(m)
        self.assertEqual(len(m["vintages"]), 5)
        self.assertEqual(len(PINNED_RELEASES), 5)

    def test_just_before_march_release_does_not_invent_fourth_value(self):
        with self.assertRaisesRegex(ValueError, "four point-in-time"):
            replay("2024-04-05T12:29:59Z")

    def test_at_march_release_four_values_now_observable(self):
        out = replay("2024-04-05T12:30:00Z")
        f = out["raw_features"]
        self.assertEqual(f["latest_period"], "2024-03")
        self.assertEqual(f["level"], 3.8)
        self.assertAlmostEqual(f["velocity_per_period"], -0.1)
        self.assertAlmostEqual(f["acceleration_per_period_squared"], -0.3)
        self.assertEqual(f["turning_point"], "UP_TO_DOWN")
        n = out["illustrative_normalization"]
        self.assertEqual(n["status"], "WITHHELD_INSUFFICIENT_PRIOR_RELEASES")
        self.assertIsNone(n["value"])

    def test_just_before_april_release_normalization_stays_withheld(self):
        out = replay("2024-05-03T12:29:59Z")
        self.assertEqual(out["raw_features"]["latest_period"], "2024-03")
        self.assertEqual(out["raw_features"]["level"], 3.8)
        self.assertIsNone(out["illustrative_normalization"]["value"])

    def test_exact_april_release_is_observable_including_dst_change(self):
        out = replay("2024-05-03T12:30:00Z")
        f = out["raw_features"]
        self.assertEqual(f["latest_period"], "2024-04")
        self.assertEqual(f["level"], 3.9)
        self.assertAlmostEqual(f["velocity_per_period"], 0.1)
        self.assertAlmostEqual(f["acceleration_per_period_squared"], 0.2)
        self.assertEqual(f["turning_point"], "DOWN_TO_UP")
        n = out["illustrative_normalization"]
        self.assertEqual(n["training_periods"],
                         ["2023-12", "2024-01", "2024-02", "2024-03"])
        self.assertEqual(n["training_observations"], 4)
        self.assertAlmostEqual(n["training_mean"], 3.775)
        self.assertAlmostEqual(n["training_population_sd"], math.sqrt(0.006875))
        self.assertAlmostEqual(n["value"],
                               (3.9 - 3.775) / math.sqrt(0.006875))

    def test_pilot_does_not_claim_source_archive_byte_certification(self):
        out = replay("2024-05-03T12:30:00Z")
        for key in ("archival_source_bytes_hashed",
                    "official_archive_rechecked_at_ci_runtime",
                    "complete_revision_history_available",
                    "full_historical_pit_certified",
                    "ready_for_macro_scoring", "ready_for_live_feature_replay",
                    "safe_to_publish_new_D", "safe_to_update_pair_theses",
                    "writes_live_data"):
            self.assertIs(out[key], False, key)
        self.assertIs(out["raw_features"]["numeric_pillar_score"], None)
        self.assertIs(out["illustrative_normalization"]["ready_for_scoring"], False)

    def test_finite_value_tamper_fails(self):
        m = data()
        m["vintages"][3]["value"] = 3.7
        with self.assertRaisesRegex(ValueError, "first-release value mismatch"):
            replay("2024-05-03T12:30:00Z", m)

    def test_official_release_time_shift_fails(self):
        m = data()
        m["vintages"][4]["released_at"] = "2024-05-03T08:31:00-04:00"
        with self.assertRaisesRegex(ValueError, "embargo lift timestamp"):
            replay("2024-05-03T12:30:00Z", m)

    def test_wrong_dst_offset_fails(self):
        m = data()
        m["vintages"][4]["released_at"] = "2024-05-03T08:30:00-05:00"
        with self.assertRaisesRegex(ValueError, "embargo lift timestamp"):
            replay("2024-05-03T12:30:00Z", m)

    def test_nonofficial_source_host_rejected(self):
        m = data()
        m["vintages"][4]["evidence_ref"] = (
            "https://www.example.com/news.release/archives/empsit_05032024.htm")
        with self.assertRaisesRegex(ValueError, "archival source URL"):
            replay("2024-05-03T12:30:00Z", m)

    def test_source_url_wrong_vintage_rejected(self):
        m = data()
        m["vintages"][3]["evidence_ref"] = m["vintages"][4]["evidence_ref"]
        with self.assertRaisesRegex(ValueError, "archival source URL"):
            replay("2024-05-03T12:30:00Z", m)

    def test_ambiguous_extra_revised_value_fails(self):
        m = data()
        revised = copy.deepcopy(m["vintages"][3])
        revised["kind"] = "REVISION"
        revised["value"] = 3.9
        revised["released_at"] = "2024-05-03T08:30:00-04:00"
        m["vintages"].append(revised)
        with self.assertRaisesRegex(ValueError, "five unique official first releases"):
            replay("2024-05-03T12:30:00Z", m)

    def test_duplicated_period_fails(self):
        m = data()
        m["vintages"][3] = copy.deepcopy(m["vintages"][2])
        with self.assertRaisesRegex(ValueError, "observation period mismatch"):
            replay("2024-05-03T12:30:00Z", m)

    def test_quietly_changed_transport_fails(self):
        m = data()
        m["source"]["transport"] = "SECONDARY_MIRROR"
        with self.assertRaisesRegex(ValueError, "declared authority changed"):
            replay("2024-05-03T12:30:00Z", m)

    def test_replay_is_deterministic_and_does_not_mutate_input(self):
        m = data()
        before = copy.deepcopy(m)
        a = replay("2024-05-03T12:30:00Z", m)
        b = replay("2024-05-03T12:30:00Z", m)
        self.assertEqual(a, b)
        self.assertEqual(m, before)

    def test_cutoff_without_timezone_fails(self):
        with self.assertRaisesRegex(ValueError, "offset-aware"):
            replay("2024-05-03T12:30:00")

    def test_no_invented_legacy_score(self):
        out = replay("2024-05-03T12:30:00Z")
        self.assertNotIn("USD_growth", out)
        self.assertNotIn("fx_direction", out)
        self.assertIsNone(out["raw_features"]["economic_cycle"])


if __name__ == "__main__":
    unittest.main()
