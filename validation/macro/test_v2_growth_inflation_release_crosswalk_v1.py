import copy
import json
import unittest
from datetime import date

from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_growth_inflation_release_crosswalk_v1 import (
    CORE, EUR, GROWTH, SERIES, build, read_json,
)


class GrowthInflationReleaseCrosswalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = [read_json(ROOT, path) for path in (SERIES, CORE, GROWTH, EUR)]

    def test_research_only_source_reconciliation(self):
        result = build(*self.inputs)
        self.assertEqual(len(result["rows"]), 16)
        self.assertEqual(result["summary"]["observed_research_slots"], 16)
        self.assertEqual(result["summary"]["slots_with_limited_official_web_anchor"], 7)
        self.assertEqual(result["summary"]["slots_without_official_web_anchor"], 9)
        self.assertEqual(result["summary"]["distinct_release_events"], 8)
        self.assertEqual(result["summary"]["historical_full_pit_certified_slots"], 0)
        self.assertEqual(result["summary"]["new_live_score_eligible_slots"], 0)
        for key in ("safe_to_publish_new_D", "safe_to_update_pair_theses",
                    "eligible_for_backtest", "writes_live_data"):
            self.assertIs(result[key], False)
        for row in result["rows"]:
            self.assertFalse(row["new_macro_score_allowed"])
            self.assertFalse(row["historical_pit_full_chain_certified"])
            self.assertFalse(row["release_timestamp_first_vintage_verified"])

    def test_distinct_eurostat_flash_and_detailed_release(self):
        result = build(*self.inputs)
        eur = next(row for row in result["rows"] if row["currency"] == "EUR"
                   and row["pillar"] == "inflation")
        self.assertEqual(eur["web_anchor_event_count"], 2)
        self.assertEqual([r["event_type"] for r in eur["official_web_anchor_events"]],
                         ["FLASH_ESTIMATE", "DETAILED_RELEASE"])
        self.assertEqual([r["published_on"] for r in eur["official_web_anchor_events"]],
                         ["2026-10-02", "2026-10-16"])
        self.assertEqual([r["published_value_for_metric"] for r in eur["official_web_anchor_events"]],
                         [3.8, 3.8])
        self.assertTrue(eur["selected_series_has_an_anchor"])

    def test_aud_latest_spending_not_automatically_selected_gdp(self):
        result = build(*self.inputs)
        aud = next(row for row in result["rows"] if row["currency"] == "AUD"
                   and row["pillar"] == "growth")
        self.assertTrue(aud["has_official_web_anchor"])
        self.assertFalse(aud["selected_series_has_an_anchor"])
        self.assertEqual(aud["official_web_anchor_events"][0]["series_id"],
                         "AU_REAL_GDP_QOQ_ABS_history_value")
        self.assertEqual(aud["official_web_anchor_events"][0]["published_on"], "2026-09-02")

    def test_nzd_gdp_same_quarter_yoy_not_annual_average(self):
        result = build(*self.inputs)
        nzd = next(row for row in result["rows"] if row["currency"] == "NZD"
                   and row["pillar"] == "growth")
        self.assertEqual(nzd["official_web_anchor_events"][0]["published_value_for_metric"], 2.6)
        self.assertTrue(nzd["selected_series_has_an_anchor"])

    def test_revision_mismatch_flagged_not_overwritten(self):
        data = copy.deepcopy(self.inputs)
        dataset = data[0]
        for x in dataset["GBP"]:
            if x["id"] == "UK_CPI_HEADLINE_YOY_history_value":
                x["last_value"] = 3.9
        out = build(*data)
        gbp = next(r for r in out["rows"] if r["currency"] == "GBP" and r["pillar"] == "inflation")
        evidence = gbp["official_web_anchor_events"][0]
        self.assertFalse(evidence["candidate_value_matches_web_anchor"])
        self.assertEqual(evidence["source_event_historical_or_revision_warning"],
                         "SAME_PERIOD_DIFFERENT_VALUE_REVIEW_REVISION")
        self.assertEqual(dataset["GBP"][-1]["last_value"], data[0]["GBP"][-1]["last_value"])

    def test_future_official_release_rejected(self):
        data = copy.deepcopy(self.inputs)
        data[3]["observations"][1]["published_on"] = "2099-10-16"
        with self.assertRaises(ValueError):
            build(*data, as_of=date(2026, 10, 24))

    def test_no_mutation(self):
        data = copy.deepcopy(self.inputs)
        build(*data)
        self.assertEqual(data, self.inputs)


if __name__ == "__main__":
    unittest.main()
