import copy
import json
import unittest

from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_abs_eurostat_publication_event_replay_v1 import (
    AUD_H, AUD_T, EUR_H, MANIFEST, replay, validate,
)


class OfficialPublicationEventReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def selected(self, result, sid):
        return next(s for s in result["latest_visible_per_series"]
                    if s["series_id"] == sid)

    def test_before_first_abs_publication_unknown(self):
        r = replay("2026-08-26T01:29:59Z", self.manifest)
        self.assertEqual(r["visible_metric_publication_records"], 0)
        self.assertFalse(self.selected(r, AUD_H)["known"])
        self.assertFalse(self.selected(r, AUD_T)["known"])
        self.assertFalse(self.selected(r, EUR_H)["known"])

    def test_abs_release_clock_exact_second_no_lookahead(self):
        r = replay("2026-08-26T01:30:00Z", self.manifest)
        self.assertEqual(r["visible_metric_publication_records"], 2)
        self.assertEqual(self.selected(r, AUD_H)["value"], 3.5)
        self.assertEqual(self.selected(r, AUD_H)["reference_period"], "2026-07")
        self.assertEqual(self.selected(r, AUD_T)["value"], 3.6)
        self.assertFalse(self.selected(r, EUR_H)["known"])
        self.assertEqual(self.selected(r, AUD_H)["visible_from_utc"],
                         "2026-08-26T01:30:00+00:00")

    def test_august_abs_only_known_at_september_release(self):
        before = replay("2026-09-30T01:29:59Z", self.manifest)
        after = replay("2026-09-30T01:30:00Z", self.manifest)
        self.assertEqual(self.selected(before, AUD_H)["reference_period"], "2026-07")
        self.assertEqual(self.selected(before, AUD_H)["value"], 3.5)
        self.assertEqual(self.selected(after, AUD_H)["reference_period"], "2026-08")
        self.assertEqual(self.selected(after, AUD_H)["value"], 4.0)
        self.assertEqual(self.selected(after, AUD_T)["value"], 3.6)
        self.assertEqual(after["visible_initial_metric_releases"], 4)

    def test_eurostat_official_date_without_clock_is_conservative(self):
        during_release_day = replay("2026-10-02T23:59:59Z", self.manifest)
        next_utc_day = replay("2026-10-03T00:00:00Z", self.manifest)
        self.assertFalse(self.selected(during_release_day, EUR_H)["known"])
        self.assertEqual(self.selected(next_utc_day, EUR_H)["value"], 3.8)
        self.assertEqual(self.selected(next_utc_day, EUR_H)["publication_stage"],
                         "FLASH_INITIAL_ESTIMATE")
        self.assertFalse(next_utc_day["intraday_eurostat_release_timing_verified"])
        self.assertEqual(next_utc_day["visible_metric_publication_records"], 5)

    def test_detailed_publication_not_called_numerical_revision(self):
        prior = replay("2026-10-16T23:59:59Z", self.manifest)
        later = replay("2026-10-17T00:00:00Z", self.manifest)
        self.assertEqual(self.selected(prior, EUR_H)["publication_stage"],
                         "FLASH_INITIAL_ESTIMATE")
        self.assertEqual(self.selected(later, EUR_H)["publication_stage"],
                         "DETAILED_PUBLICATION")
        self.assertEqual(later["visible_later_detailed_metric_publications"], 1)
        self.assertEqual(later["visible_metric_publication_records"], 6)
        self.assertTrue(later["eurostat_unchanged_flash_to_detailed_not_numerical_revision"])
        self.assertEqual(self.selected(prior, EUR_H)["value"],
                         self.selected(later, EUR_H)["value"])

    def test_no_live_or_backtest_promotion(self):
        for cutoff in ("2026-08-26T01:29:59Z", "2026-09-30T01:30:00Z",
                       "2026-10-03T00:00:00Z", "2026-10-24T00:00:00Z"):
            with self.subTest(cutoff=cutoff):
                r = replay(cutoff, self.manifest)
                self.assertEqual(r["scope"]["series"], 3)
                self.assertFalse(r["historical_macro_score_computed"])
                self.assertFalse(r["source_archival_bytes_verified"])
                self.assertFalse(r["complete_revision_history_certified"])
                for key in ("eligible_for_backtest", "safe_to_publish_new_D",
                            "safe_to_update_pair_theses", "writes_live_data"):
                    self.assertFalse(r[key])

    def test_fail_closed_on_tampered_evidence(self):
        edits = [
            (0, "value", 3.7), (2, "value", 3.5),
            (4, "value", 4.1), (5, "publication_stage", "REVISION"),
            (0, "official_release_at_local", "2026-08-26T11:29:00+10:00"),
            (0, "official_release_at_local", "2026-08-26T11:30:00Z"),
            (4, "conservative_visibility_from_utc", "2026-10-02T08:00:00Z"),
            (5, "conservative_visibility_from_utc", "2026-10-18T00:00:00Z"),
            (4, "official_release_at_local", "2026-10-02T11:00:00+02:00"),
            (3, "source_url", "https://example.com/aug-2026"),
            (0, "source_page_bytes_at_original_release_archived", True),
        ]
        for idx, field, value in edits:
            with self.subTest(idx=idx, field=field):
                manifest = copy.deepcopy(self.manifest)
                manifest["events"][idx][field] = value
                with self.assertRaises((ValueError, TypeError)):
                    validate(manifest)
        for flag in ("historical_full_pit_certified", "eligible_for_backtest",
                     "safe_to_publish_new_D"):
            with self.subTest(flag=flag):
                manifest = copy.deepcopy(self.manifest)
                manifest[flag] = True
                with self.assertRaises((ValueError, TypeError)):
                    validate(manifest)

    def test_naive_timestamp_rejected(self):
        with self.assertRaises((ValueError, TypeError)):
            replay("2026-10-02T12:00:00", self.manifest)

    def test_no_mutation_repeatable_fingerprint(self):
        manifest = copy.deepcopy(self.manifest)
        a = replay("2026-10-24T00:00:00Z", manifest)
        b = replay("2026-10-24T00:00:00Z", manifest)
        self.assertEqual(a, b)
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(a["visible_initial_metric_releases"], 5)
        self.assertEqual(a["visible_later_detailed_metric_publications"], 1)


if __name__ == "__main__":
    unittest.main()
