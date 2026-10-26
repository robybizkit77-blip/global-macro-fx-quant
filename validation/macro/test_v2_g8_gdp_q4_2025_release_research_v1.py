"""Q4 2025 first-release and revision chronology: source statements, NOT PIT training."""
import json
import unittest
from pathlib import Path

from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot

HERE = Path(__file__).parent
Q4 = HERE / "fixtures/v2_g8_gdp_q4_2025_official_web_release_research_v1.json"
Q1Q2 = HERE / "fixtures/v2_g8_gdp_multiquarter_partial_official_research_v1.json"


class GDP2025Q4ReleaseResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(Q4.read_text(encoding="utf-8"))
        cls.rows = validate(cls.data["records"])

    def test_eight_first_publications_and_six_separate_followups(self):
        self.assertEqual(self.data["first_releases_expected"], 8)
        self.assertEqual(self.data["subsequent_statements_documented"], 6)
        self.assertEqual(len(self.rows), 14)
        first = [r for r in self.rows if r["stage_order"] == 0]
        self.assertEqual({r["currency"] for r in first},
                         {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"})
        self.assertTrue(all(r["reference_quarter"] == "2025Q4" for r in self.rows))
        self.assertTrue(all(r["eligible_for_macro_scoring"] is False and
                            r["PIT_training_vintage_certified"] is False for r in self.rows))
        self.assertFalse(self.data["eligible_for_macro_scoring"])
        self.assertFalse(self.data["eligible_for_beta"])
        self.assertFalse(self.data["eligible_for_forward"])
        self.assertFalse(self.data["may_rewrite_D_json"])

    def test_us_gdp_future_revisions_absent_asof_release_days(self):
        before = snapshot(self.rows, "2026-02-20T23:59:59Z")
        self.assertNotIn("USD:2025Q4", before["visible_vintages"])
        first = snapshot(self.rows, "2026-02-21T00:00:00Z")
        self.assertEqual(first["visible_vintages"]["USD:2025Q4"]["reported_value"], 1.4)
        second = snapshot(self.rows, "2026-03-14T00:00:00Z")
        self.assertEqual(second["visible_vintages"]["USD:2025Q4"]["reported_value"], 0.7)
        third = snapshot(self.rows, "2026-04-10T00:00:00Z")
        self.assertEqual(third["visible_vintages"]["USD:2025Q4"]["reported_value"], 0.5)
        self.assertFalse(third["safe_to_use_for_beta"])
        self.assertFalse(third["safe_to_use_for_forward"])
        self.assertFalse(third["safe_to_change_28_pairs"])

    def test_japan_swiss_uk_and_eurozone_releases_preserved(self):
        early = snapshot(self.rows, "2026-02-17T00:00:00Z")["visible_vintages"]
        self.assertEqual(early["JPY:2025Q4"]["reported_value"], 0.1)
        self.assertEqual(early["CHF:2025Q4"]["reported_value"], 0.2)
        self.assertEqual(early["GBP:2025Q4"]["reported_value"], 0.1)
        self.assertEqual(early["EUR:2025Q4"]["reported_value"], 0.3)
        later = snapshot(self.rows, "2026-04-01T00:00:00Z")["visible_vintages"]
        self.assertEqual(later["JPY:2025Q4"]["reported_value"], 0.3)
        self.assertEqual(later["JPY:2025Q4"]["publisher_release_day"], "2026-03-10")
        self.assertEqual(later["CHF:2025Q4"]["reported_value"], 0.2)
        self.assertEqual(later["GBP:2025Q4"]["reported_value"], 0.1)

    def test_source_domain_not_self_certifying(self):
        from copy import deepcopy
        rows = deepcopy(self.rows)
        fake = next(r for r in rows if r["currency"] == "USD")
        fake["source_url"] = "https://fake-bea.example/news/gdp"
        fake["verified_publisher_host"] = "fake-bea.example"
        with self.assertRaises(ValueError):
            validate(rows)

    def test_cross_year_multiquarter_not_same_vintage(self):
        other = json.loads(Q1Q2.read_text(encoding="utf-8"))["records"]
        combined = validate(self.rows + other)
        feb = snapshot(combined, "2026-02-28T00:00:00Z")["visible_vintages"]
        self.assertIn("USD:2025Q4", feb)
        self.assertNotIn("USD:2026Q1", feb)
        september = snapshot(combined, "2026-09-18T00:00:00Z")["visible_vintages"]
        self.assertEqual(september["USD:2025Q4"]["reported_value"], 0.5)
        self.assertEqual(september["USD:2026Q1"]["reported_value"], 1.6)
        self.assertEqual(september["USD:2026Q2"]["reported_value"], 1.5)

if __name__ == "__main__":
    unittest.main()
