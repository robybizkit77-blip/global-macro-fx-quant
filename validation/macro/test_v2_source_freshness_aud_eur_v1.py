import copy
import json
import unittest
from datetime import date

from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_source_freshness_aud_eur_v1 import EVIDENCE, SOURCE, audit


class OfficialFreshnessGapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = json.loads((ROOT / SOURCE).read_text(encoding="utf-8"))
        cls.evidence = json.loads((ROOT / EVIDENCE).read_text(encoding="utf-8"))
        # Explicitly synthetic historical review fixture, never an archived PIT snapshot.
        cls.series = copy.deepcopy(cls.current)
        for event in cls.evidence["events"]:
            row = next(x for x in cls.series[event["currency"]] if x["id"] == event["series_id"])
            row["last_date"] = event["series_reference_period_expected"]
            row["last_value"] = event["series_value_expected"]

    def test_advanced_current_snapshot_remains_non_pit(self):
        result = audit(self.current, self.evidence)
        for row in result["rows"]:
            if row["observed_period"] > row["official_reference_period"]:
                self.assertEqual(row["source_freshness"], "CURRENT_OBSERVATION_NEWER_THAN_ARCHIVED_RELEASE_NOT_PIT")
                self.assertTrue(row["review_snapshot_superseded"])
            self.assertFalse(row["eligible_for_new_macro_score"])
        self.assertFalse(result["current_series_snapshot_reconstructed_at_cutoff"])

    def test_expected_three_source_lags_and_no_promotion(self):
        result = audit(self.series, self.evidence)
        stats = result["summary"]
        self.assertEqual(stats["series_examined"], 3)
        self.assertEqual(stats["distinct_documented_official_release_events"], 2)
        self.assertEqual(stats["events_visible_by_requested_cutoff"], 2)
        self.assertEqual(stats["lagging_series_where_release_visible"], 3)
        self.assertEqual(stats["values_requiring_source_metric_reconciliation"], 1)
        self.assertEqual(stats["full_historical_pit_vintages_certified"], 0)
        for key in ("safe_to_update_macro_series", "safe_to_publish_new_D",
                    "safe_to_update_pair_theses", "eligible_for_backtest",
                    "current_series_snapshot_reconstructed_at_cutoff", "writes_live_data"):
            self.assertFalse(result[key])
        self.assertEqual(result["planned_abs_september_release_not_observed"],
                         "2026-10-28T11:30:00+11:00")

    def test_headline_accelerates_but_trimmed_mean_flat(self):
        result = audit(self.series, self.evidence)
        headline = next(x for x in result["rows"] if "HEADLINE_M" in x["series_id"])
        trimmed = next(x for x in result["rows"] if "TRIMMED_MEAN_M" in x["series_id"])
        self.assertEqual(headline["observed_period"], "2026-07")
        self.assertEqual(headline["official_reference_period"], "2026-08")
        self.assertEqual(headline["official_metric_value"], 4.0)
        self.assertEqual(headline["official_change_in_annual_rate_pp"], 0.5)
        self.assertEqual(trimmed["official_change_in_annual_rate_pp"], 0.0)
        self.assertTrue(headline["observed_value_matches_pinned_review_snapshot"])
        self.assertTrue(trimmed["observed_value_matches_pinned_review_snapshot"])
        self.assertEqual(headline["official_release_at_local_verified_when_provided"],
                         "2026-09-30T11:30:00+10:00")

    def test_eurostat_mom_rate_not_substituted_for_index_level(self):
        result = audit(self.series, self.evidence)
        eur = next(x for x in result["rows"] if x["currency"] == "EUR")
        self.assertEqual(eur["observed_value"], 98.3)
        self.assertEqual(eur["observed_unit"], "Index 2021=100")
        self.assertEqual(eur["official_metric_value"], -0.5)
        self.assertEqual(eur["official_metric_unit"], "percent MoM")
        self.assertIsNone(eur["matching_official_new_index_level"])
        self.assertIsNone(eur["official_change_in_annual_rate_pp"])
        self.assertIsNone(eur["official_release_at_local_verified_when_provided"])
        self.assertEqual(eur["source_freshness"],
                         "LAGGING_SERIES_REQUIRES_SAME_DEFINITION_OFFICIAL_INDEX_LEVEL")

    def test_no_future_event_visibility_or_pit_leakage(self):
        before = audit(self.series, self.evidence, as_of=date(2026, 9, 29))
        self.assertEqual(before["summary"]["events_visible_by_requested_cutoff"], 0)
        self.assertTrue(all(x["official_metric_value"] is None for x in before["rows"]))
        oct_first = audit(self.series, self.evidence, as_of=date(2026, 10, 1))
        self.assertEqual(oct_first["summary"]["events_visible_by_requested_cutoff"], 1)
        self.assertFalse(next(x for x in oct_first["rows"] if x["currency"] == "EUR")
                         ["official_event_visible_at_cutoff"])
        self.assertFalse(oct_first["current_series_snapshot_reconstructed_at_cutoff"])

    def test_revisions_and_snapshot_drift_are_flags_not_mutations(self):
        source = copy.deepcopy(self.series)
        row = next(x for x in source["AUD"] if "HEADLINE_M" in x["id"])
        row["last_value"] = 3.9
        receipt = audit(source, self.evidence)
        headline = next(x for x in receipt["rows"] if x["series_id"] == row["id"])
        self.assertTrue(headline["review_snapshot_drift_requires_investigation"])
        self.assertEqual(row["last_value"], 3.9)
        self.assertEqual(next(x for x in self.series["AUD"] if x["id"] == row["id"])["last_value"], 3.5)

    def test_reject_fake_future_release_and_wrong_source(self):
        for update in (
            {"official_release_date": "2026-11-01"},
            {"official_source_url": "https://example.com/cpi"},
            {"official_metric_unit": "Index 2021=100"},
            {"full_pit_vintage_chain_certified": True},
            {"official_release_at_local": "2026-09-30T11:30:00"},
        ):
            with self.subTest(update=update):
                evidence = copy.deepcopy(self.evidence)
                evidence["events"][0].update(update)
                with self.assertRaises((ValueError, TypeError)):
                    audit(self.series, evidence)

    def test_no_input_mutation(self):
        inputs = copy.deepcopy((self.series, self.evidence))
        audit(self.series, self.evidence)
        self.assertEqual((self.series, self.evidence), inputs)


if __name__ == "__main__":
    unittest.main()
