"""Q3 2025 eight-country GDP first-release and revision research checks."""
import copy
import json
import unittest
from pathlib import Path

from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot

HERE = Path(__file__).parent / "fixtures"
Q3 = HERE / "v2_g8_gdp_q3_2025_official_web_release_research_v1.json"
Q4 = HERE / "v2_g8_gdp_q4_2025_official_web_release_research_v1.json"
Q1Q2 = HERE / "v2_g8_gdp_multiquarter_partial_official_research_v1.json"


class GDP2025Q3ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(Q3.read_text(encoding="utf-8"))
        cls.rows = validate(cls.data["records"])

    def test_first_publication_coverage_and_followup_count(self):
        self.assertEqual(len(self.rows), 14)
        first = [r for r in self.rows if r["stage_order"] == 0]
        self.assertEqual({r["currency"] for r in first},
                         {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"})
        self.assertEqual(len(first), 8)
        self.assertEqual(len(self.rows)-len(first), 6)
        self.assertTrue(all(r["reference_quarter"] == "2025Q3" for r in self.rows))
        for flag in ("eligible_for_macro_scoring", "eligible_for_beta",
                     "eligible_for_forward", "may_rewrite_D_json"):
            self.assertIs(self.data[flag], False)

    def test_delayed_us_release_no_lookahead(self):
        before = snapshot(self.rows, "2025-12-23T23:59:59Z")
        self.assertNotIn("USD:2025Q3", before["visible_vintages"])
        first = snapshot(self.rows, "2025-12-24T00:00:00Z")
        self.assertEqual(first["visible_vintages"]["USD:2025Q3"]["reported_value"], 4.3)
        next_vintage = snapshot(self.rows, "2026-01-23T00:00:00Z")
        self.assertEqual(next_vintage["visible_vintages"]["USD:2025Q3"]["reported_value"], 4.4)
        self.assertFalse(next_vintage["safe_to_use_for_beta"])
        self.assertFalse(next_vintage["safe_to_use_for_forward"])
        self.assertFalse(next_vintage["safe_to_change_28_pairs"])

    def test_eur_jpy_and_swiss_revision_stages(self):
        earlier = snapshot(self.rows, "2025-11-19T00:00:00Z")["visible_vintages"]
        self.assertEqual(earlier["EUR:2025Q3"]["reported_value"], 0.2)
        self.assertEqual(earlier["JPY:2025Q3"]["reported_value"], -0.4)
        self.assertEqual(earlier["JPY:2025Q3"]["reference_base_year"], 2015)
        self.assertEqual(earlier["CHF:2025Q3"]["reported_value"], -0.5)
        late = snapshot(self.rows, "2025-12-09T00:00:00Z")["visible_vintages"]
        self.assertEqual(late["EUR:2025Q3"]["reported_value"], 0.3)
        self.assertEqual(late["JPY:2025Q3"]["reported_value"], -0.6)
        self.assertEqual(late["JPY:2025Q3"]["reference_base_year"], 2020)
        self.assertTrue(late["JPY:2025Q3"]["methodology_break_acknowledged"])
        self.assertEqual(late["CHF:2025Q3"]["reported_value"], -0.5)

    def test_must_record_japan_rebenchmark_as_definition_break(self):
        r = copy.deepcopy(self.rows)
        for item in r:
            if item["currency"] == "JPY" and item["stage_order"] == 1:
                item.pop("methodology_break_acknowledged")
                break
        with self.assertRaises(ValueError):
            validate(r)
        r = copy.deepcopy(self.rows)
        for item in r:
            if item["currency"] == "JPY" and item["stage_order"] == 1:
                item["reference_base_year"] = 2015
                break
        with self.assertRaises(ValueError):
            validate(r)

    def test_combined_g8_across_four_quarters_remains_research_only(self):
        other = json.loads(Q4.read_text(encoding="utf-8"))["records"]
        newer = json.loads(Q1Q2.read_text(encoding="utf-8"))["records"]
        all_vintages = validate(self.rows + other + newer)
        self.assertEqual(
            {r["reference_quarter"] for r in all_vintages},
            {"2025Q3", "2025Q4", "2026Q1", "2026Q2"})
        dec = snapshot(all_vintages, "2025-12-19T00:00:00Z")["visible_vintages"]
        self.assertNotIn("USD:2025Q3", dec)
        self.assertIn("NZD:2025Q3", dec)
        self.assertNotIn("USD:2025Q4", dec)
        self.assertNotIn("USD:2026Q1", dec)
        self.assertNotIn("USD:2026Q2", dec)
        self.assertFalse(snapshot(all_vintages, "2026-10-26T00:00:00Z")["safe_to_update_live_macro_D"])


if __name__ == "__main__":
    unittest.main()
