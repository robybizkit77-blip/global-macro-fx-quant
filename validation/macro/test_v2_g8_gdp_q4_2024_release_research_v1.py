"""Retrospectively verified 2024 Q4 GDP vintage chronology (research only)."""
import copy
import json
import unittest
from pathlib import Path

from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot

FIX = Path(__file__).parent / "fixtures"
FILES = (
    "v2_g8_gdp_q4_2024_official_web_release_research_v1.json",
    "v2_g8_gdp_q1_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q2_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q3_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q4_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_multiquarter_partial_official_research_v1.json",
)

class GDP2024Q4ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((FIX / FILES[0]).read_text(encoding="utf-8"))
        cls.rows = validate(cls.data["records"])

    def test_8_first_7_followups_research_only(self):
        self.assertEqual(len(self.rows), 15)
        self.assertEqual(self.data["first_releases_expected"], 8)
        self.assertEqual(self.data["subsequent_statements_documented"], 7)
        initial = [r for r in self.rows if r["stage_order"] == 0]
        self.assertEqual({r["currency"] for r in initial},
                         {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"})
        self.assertTrue(all(r["reference_quarter"] == "2024Q4" for r in self.rows))
        self.assertTrue(all(r["PIT_training_vintage_certified"] is False and
                            r["eligible_for_macro_scoring"] is False for r in self.rows))
        for field in ("eligible_for_macro_scoring", "eligible_for_beta",
                      "eligible_for_forward", "may_rewrite_D_json"):
            self.assertIs(self.data[field], False)

    def test_us_not_yet_known_revision(self):
        self.assertNotIn("USD:2024Q4",
            snapshot(self.rows, "2025-01-30T23:59:59Z")["visible_vintages"])
        for at, expected, stage in (
            ("2025-01-31T00:00:00Z", 2.3, 0),
            ("2025-02-28T00:00:00Z", 2.3, 1),
            ("2025-03-28T00:00:00Z", 2.4, 2)):
            with self.subTest(at=at):
                r = snapshot(self.rows, at)["visible_vintages"]["USD:2024Q4"]
                self.assertEqual((r["reported_value"], r["stage_order"]), (expected, stage))
                self.assertEqual(r["reported_unit"], "PERCENT_SAAR_ANNUALIZED")

    def test_eurozone_revision_stages_are_not_overwritten(self):
        for at, value in (
            ("2025-01-31T00:00:00Z", 0.0),
            ("2025-02-15T00:00:00Z", 0.1),
            ("2025-03-08T00:00:00Z", 0.2)):
            with self.subTest(at=at):
                r = snapshot(self.rows, at)["visible_vintages"]["EUR:2024Q4"]
                self.assertEqual(r["reported_value"], value)
                self.assertEqual(r["population_reference"], "EA20")

    def test_japan_and_swiss_vintage_and_methodological_tags(self):
        early = snapshot(self.rows, "2025-02-18T00:00:00Z")["visible_vintages"]
        self.assertEqual(early["JPY:2024Q4"]["reported_value"], 0.7)
        self.assertEqual(early["JPY:2024Q4"]["reference_base_year"], 2015)
        self.assertEqual(early["CHF:2024Q4"]["reported_value"], 0.4)
        self.assertEqual(early["CHF:2024Q4"]["reported_unit"],
                         "PERCENT_QOQ_SA_CALENDAR_SPORTS")
        later = snapshot(self.rows, "2025-03-12T00:00:00Z")["visible_vintages"]
        self.assertEqual(later["JPY:2024Q4"]["reported_value"], 0.6)
        self.assertEqual(later["CHF:2024Q4"]["reported_value"], 0.5)
        self.assertEqual(later["GBP:2024Q4"]["reported_value"], 0.1)
        self.assertEqual(later["CAD:2024Q4"]["reported_value"], 0.6)
        self.assertEqual(later["AUD:2024Q4"]["reported_value"], 0.6)
        self.assertNotIn("NZD:2024Q4", later)
        after_nz = snapshot(self.rows, "2025-03-21T00:00:00Z")["visible_vintages"]
        self.assertEqual(after_nz["NZD:2024Q4"]["reported_value"], 0.7)

    def test_seven_consecutive_quarters_and_no_live_promotion(self):
        rows = []
        for name in FILES:
            rows.extend(json.loads((FIX / name).read_text(encoding="utf-8"))["records"])
        rows = validate(rows)
        self.assertEqual({r["reference_quarter"] for r in rows},
                         {"2024Q4","2025Q1","2025Q2","2025Q3","2025Q4","2026Q1","2026Q2"})
        cutoff = snapshot(rows, "2025-02-28T00:00:00Z")
        self.assertIn("USD:2024Q4", cutoff["visible_vintages"])
        self.assertNotIn("USD:2025Q1", cutoff["visible_vintages"])
        self.assertNotIn("GBP:2025Q2", cutoff["visible_vintages"])
        for flag in ("safe_to_update_live_macro_D", "safe_to_change_28_pairs",
                     "safe_to_use_for_beta", "safe_to_use_for_forward"):
            self.assertIs(cutoff[flag], False)

    def test_forged_publisher_and_wrong_order_fail_closed(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["source_url"] = "https://not-bea.example/news/gdp"
        rows[0]["verified_publisher_host"] = "not-bea.example"
        with self.assertRaises(ValueError):
            validate(rows)
        rows = copy.deepcopy(self.rows)
        rows[1]["stage_order"] = 4
        with self.assertRaises(ValueError):
            validate(rows)
        rows = copy.deepcopy(self.rows)
        rows[1]["PIT_training_vintage_certified"] = True
        with self.assertRaises(ValueError):
            validate(rows)

if __name__ == "__main__":
    unittest.main()
