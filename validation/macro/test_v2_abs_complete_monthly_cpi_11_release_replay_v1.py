import copy
import json
import unittest

from validation.macro.v2_abs_complete_monthly_cpi_11_release_replay_v1 import (
    SOURCE, audit_ledger, replay,
)


class ABSCompleteMonthly11ReleasesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_eleven_source_release_events_and_regime_boundary(self):
        rows = audit_ledger(self.manifest)
        self.assertEqual(len(rows), 11)
        self.assertEqual([e["period"] for e in rows][0], "2025-10")
        self.assertEqual([e["period"] for e in rows][-1], "2026-08")
        self.assertEqual(rows[0]["publication_at_utc"], "2025-11-26T00:30:00+00:00")
        self.assertEqual(rows[-1]["publication_at_utc"], "2026-09-30T01:30:00+00:00")
        self.assertEqual(rows[4]["publication_at_utc"], "2026-03-25T00:30:00+00:00")
        self.assertEqual(rows[5]["publication_at_utc"], "2026-04-29T01:30:00+00:00")
        self.assertTrue(all(e["original_release_day_bytes_archived"] is False for e in rows))

    def test_no_2024_first_monthly_releases_from_backcast(self):
        before = replay("2025-11-26T00:29:59Z", self.manifest)
        self.assertEqual(before["source_publication_events_known_at_cutoff"], 0)
        self.assertEqual(before["first_visible_reference_period"], None)
        self.assertEqual(before["latest_headline_annual_percent"], None)
        self.assertTrue(before["monthly_backcast_not_counted_as_historical_first_releases"])
        self.assertFalse(before["allow_cross_regime_2024_backcast_as_earlier_release_events"])
        after = replay("2025-11-26T00:30:00Z", self.manifest)
        self.assertEqual(after["source_publication_events_known_at_cutoff"], 1)
        self.assertEqual(after["first_visible_reference_period"], "2025-10")
        self.assertEqual(after["latest_headline_annual_percent"], 3.8)
        self.assertEqual(after["additional_first_releases_needed_at_this_cutoff"], 24)

    def test_january_first_release_not_overwritten_by_february_reference(self):
        jan = replay("2026-02-25T00:30:00Z", self.manifest)
        before_feb = replay("2026-03-25T00:29:59Z", self.manifest)
        after_feb = replay("2026-03-25T00:30:00Z", self.manifest)
        self.assertEqual(jan["january_original_first_web_report_trimmed_mean_percent"], 3.4)
        self.assertFalse(jan["january_trimmed_cross_publication_discrepancy_known"])
        self.assertFalse(before_feb["january_trimmed_cross_publication_discrepancy_known"])
        self.assertTrue(after_feb["january_trimmed_cross_publication_discrepancy_known"])
        self.assertEqual(after_feb["january_original_first_web_report_trimmed_mean_percent"], 3.4)
        self.assertEqual(after_feb["january_later_february_reported_reference_percent"], 3.3)
        self.assertFalse(after_feb["january_revision_confirmed"])

    def test_11_observations_are_not_25_complete_training_releases(self):
        last = replay("2026-10-24T00:00:00Z", self.manifest)
        self.assertEqual(last["source_publication_events_known_at_cutoff"], 11)
        self.assertEqual(last["last_visible_reference_period"], "2026-08")
        self.assertEqual(last["latest_headline_annual_percent"], 4.0)
        self.assertEqual(last["latest_trimmed_mean_annual_percent"], 3.6)
        self.assertEqual(last["minimum_prior_first_release_training_plus_oos"], 25)
        self.assertEqual(last["additional_first_releases_needed_at_this_cutoff"], 14)
        self.assertFalse(last["training_requirement_met"])
        self.assertFalse(last["revision_lineage_complete"])
        self.assertFalse(last["original_release_day_source_bytes_hashed"])
        for field in ("macro_score_computed", "eligible_for_backtest",
                      "safe_to_publish_new_D", "safe_to_update_pair_theses", "writes_live_data"):
            self.assertFalse(last[field])

    def test_no_future_release_leak_or_clock_drift(self):
        # At 00:30 UTC the March 2026 AEDT release is visible, while after
        # Sydney DST ended the April AEST release only becomes visible at 01:30.
        pre = replay("2026-04-29T01:29:59Z", self.manifest)
        post = replay("2026-04-29T01:30:00Z", self.manifest)
        self.assertEqual(pre["last_visible_reference_period"], "2026-02")
        self.assertEqual(post["last_visible_reference_period"], "2026-03")
        self.assertEqual(post["latest_headline_annual_percent"], 4.6)

    def test_drift_rejected(self):
        for idx, key, value in (
            (3, "trimmed_mean_annual_percent", 3.3),
            (4, "reference_period", "2026-03"),
            (7, "source_url", "https://example.com/may-2026"),
            (0, "release_timestamp_local", "2025-11-26T11:30:00+10:00"),
            (6, "immutable_original_release_html_bytes_preserved", True),
            (0, "headline_annual_percent", float("nan")),
        ):
            with self.subTest(idx=idx, key=key):
                changed = copy.deepcopy(self.manifest)
                changed["ledger"][idx][key] = value
                with self.assertRaises((ValueError, TypeError)):
                    audit_ledger(changed)
        for field in ("sufficient_first_releases_for_25_month_training",
                      "eligible_for_backtest", "safe_to_publish_new_D"):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.manifest)
                changed[field] = True
                with self.assertRaises((ValueError, TypeError)):
                    audit_ledger(changed)
        changed = copy.deepcopy(self.manifest)
        changed["first_full_monthly_period"] = "2024-04"
        with self.assertRaises((ValueError, TypeError)):
            audit_ledger(changed)

    def test_input_purity_and_replay_repeatability(self):
        manifest = copy.deepcopy(self.manifest)
        a = replay("2026-09-30T01:30:00Z", manifest)
        b = replay("2026-09-30T01:30:00Z", manifest)
        self.assertEqual(a, b)
        self.assertEqual(manifest, self.manifest)


if __name__ == "__main__":
    unittest.main()
