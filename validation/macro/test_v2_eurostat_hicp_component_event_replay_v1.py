import copy
import json
import unittest

from validation.macro.v2_eurostat_hicp_component_event_replay_v1 import (
    PATH, PREVIOUS, replay, validate,
)


class EurostatHICPComponentsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(PATH.read_text(encoding="utf-8"))
        cls.previous = json.loads(PREVIOUS.read_text(encoding="utf-8"))

    def component(self, response, component):
        return next(x for x in response["components"] if x["component_id"] == component)

    def test_cutoff_before_flash_no_data_visible(self):
        result = replay("2026-10-02T23:59:59Z", self.fixture, self.previous)
        self.assertFalse(result["flash_visible"])
        self.assertEqual(result["source_publications_visible"], 0)
        self.assertTrue(all(x["value_known_at_cutoff"] is None for x in result["components"]))
        self.assertEqual(result["final_only_contributions_known"], [])

    def test_flash_next_day_visible_but_no_final_or_diff(self):
        result = replay("2026-10-03T00:00:00Z", self.fixture, self.previous)
        self.assertTrue(result["flash_visible"])
        self.assertFalse(result["detailed_visible"])
        self.assertEqual(result["source_publications_visible"], 1)
        self.assertEqual(self.component(result, "ENERGY")["value_known_at_cutoff"], 18.8)
        self.assertEqual(self.component(result, "FOOD_ALCOHOL_TOBACCO")["value_known_at_cutoff"], 1.4)
        self.assertEqual(self.component(result, "ALL_ITEMS_HICP")["value_known_at_cutoff"], 3.8)
        self.assertIsNone(self.component(result, "ENERGY")["flash_to_detailed_difference_pp"])
        self.assertEqual(result["final_only_contributions_known"], [])
        self.assertIsNone(result["comparable_components_with_changed_reported_annual_rate"])

    def test_detailed_not_leaked_on_original_calendar_date(self):
        before = replay("2026-10-16T23:59:59Z", self.fixture, self.previous)
        after = replay("2026-10-17T00:00:00Z", self.fixture, self.previous)
        self.assertFalse(before["detailed_visible"])
        self.assertTrue(after["detailed_visible"])
        self.assertEqual(after["latest_publication_stage"], "DETAILED_PUBLICATION")
        self.assertEqual(after["source_publications_visible"], 2)

    def test_two_component_differences_headline_and_core_unchanged(self):
        result = replay("2026-10-24T00:00:00Z", self.fixture, self.previous)
        self.assertEqual(len(result["components"]), 10)
        self.assertEqual(result["comparable_components_with_changed_reported_annual_rate"], 2)
        changes = {row["component_id"]: row["flash_to_detailed_difference_pp"]
                   for row in result["components"]
                   if row["flash_to_detailed_difference_pp"] != 0}
        self.assertEqual(changes, {"ENERGY": 0.1, "FOOD_ALCOHOL_TOBACCO": -0.1})
        self.assertFalse(result["headline_changed_between_flash_and_detailed"])
        for key in ("ALL_ITEMS_HICP", "EX_ENERGY_FOOD_ALCOHOL_TOBACCO",
                    "SERVICES", "NON_ENERGY_INDUSTRIAL_GOODS"):
            self.assertEqual(self.component(result, key)["flash_to_detailed_difference_pp"], 0.0)

    def test_contributions_only_after_detailed_release_and_units_not_confused(self):
        result = replay("2026-10-17T00:00:00Z", self.fixture, self.previous)
        self.assertEqual({x["component_id"]: x["value_pp"]
                          for x in result["final_only_contributions_known"]},
                         {"ENERGY": 1.71, "SERVICES": 1.52,
                          "NON_ENERGY_INDUSTRIAL_GOODS": 0.29,
                          "FOOD_ALCOHOL_TOBACCO": 0.25})
        self.assertTrue(all(x["unit"].startswith("percentage points contribution")
                            for x in result["final_only_contributions_known"]))
        self.assertEqual(self.component(result, "ENERGY")["value_known_at_cutoff"], 18.9)

    def test_fail_closed_on_source_numbers_and_artificial_clock(self):
        cases = (
            ("components", 0, "flash_percent_yoy", 3.7),
            ("components", 7, "detailed_percent_yoy", 18.8),
            ("components", 4, "detailed_percent_yoy", 1.4),
            ("final_only_contributions", 0, "value_pp", 18.9),
            ("final_only_contributions", 2, "metric", "percent YoY"),
        )
        for group, index, field, value in cases:
            with self.subTest(group=group, index=index, field=field):
                changed = copy.deepcopy(self.fixture)
                changed[group][index][field] = value
                with self.assertRaises(ValueError):
                    validate(changed, self.previous)
        for path, field, value in (
            ("flash", "published_at_local_verified", "2026-10-02T11:00:00+02:00"),
            ("flash", "conservative_visible_from_utc", "2026-10-02T10:00:00Z"),
            ("detailed", "source_url", "https://example.com/release"),
        ):
            changed = copy.deepcopy(self.fixture)
            changed[path][field] = value
            with self.assertRaises(ValueError):
                validate(changed, self.previous)

    def test_fail_closed_if_underlying_headline_event_contract_changes(self):
        changed = copy.deepcopy(self.previous)
        changed["observations"][1]["value"] = 3.7
        with self.assertRaises(ValueError):
            validate(self.fixture, changed)

    def test_no_model_promotion_or_input_mutation(self):
        fixture = copy.deepcopy(self.fixture)
        previous = copy.deepcopy(self.previous)
        for cutoff in ("2026-10-02T23:59:59Z", "2026-10-03T00:00:00Z",
                       "2026-10-16T23:59:59Z", "2026-10-24T00:00:00Z"):
            result = replay(cutoff, fixture, previous)
            self.assertEqual(result["scope"]["distinct_official_publications"], 2)
            self.assertEqual(result["scope"]["reference_periods"], 1)
            self.assertFalse(result["official_intraday_release_timestamp_certified"])
            for key in ("eligible_for_macro_score", "eligible_for_backtest",
                        "safe_to_publish_new_D", "safe_to_update_pair_theses",
                        "writes_live_data"):
                self.assertIs(result[key], False)
        self.assertEqual(fixture, self.fixture)
        self.assertEqual(previous, self.previous)


if __name__ == "__main__":
    unittest.main()
