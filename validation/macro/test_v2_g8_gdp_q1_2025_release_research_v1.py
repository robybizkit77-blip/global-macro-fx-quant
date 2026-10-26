"""Q1 2025 eight-country official GDP publisher statement chronology: research only."""
import copy
import json
import unittest
from pathlib import Path

from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot

FIX = Path(__file__).parent / "fixtures"
SOURCES = (
    "v2_g8_gdp_q1_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q2_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q3_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q4_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_multiquarter_partial_official_research_v1.json",
)

class GDP2025Q1ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((FIX / SOURCES[0]).read_text(encoding="utf-8"))
        cls.rows = validate(cls.source["records"])

    def test_eight_first_release_seven_followups(self):
        self.assertEqual(len(self.rows), 15)
        initial = [r for r in self.rows if r["stage_order"] == 0]
        self.assertEqual({r["currency"] for r in initial},
                         {"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"})
        self.assertEqual(len(initial), 8)
        self.assertEqual(len(self.rows) - len(initial), 7)
        self.assertTrue(all(r["reference_quarter"] == "2025Q1" for r in self.rows))
        self.assertTrue(all(r["PIT_training_vintage_certified"] is False and
                            r["eligible_for_macro_scoring"] is False for r in self.rows))
        for name in ("eligible_for_macro_scoring", "eligible_for_beta",
                     "eligible_for_forward", "may_rewrite_D_json"):
            self.assertIs(self.source[name], False)

    def test_us_release_revision_snapshots_do_not_use_future(self):
        self.assertNotIn("USD:2025Q1",
                         snapshot(self.rows, "2025-04-30T23:59:59Z")["visible_vintages"])
        seq = (("2025-05-01T00:00:00Z", -0.3),
               ("2025-05-30T00:00:00Z", -0.2),
               ("2025-06-27T00:00:00Z", -0.5))
        for cutoff, expected in seq:
            with self.subTest(cutoff=cutoff):
                row = snapshot(self.rows, cutoff)["visible_vintages"]["USD:2025Q1"]
                self.assertEqual(row["reported_value"], expected)
                self.assertEqual(row["reported_unit"], "PERCENT_SAAR_ANNUALIZED")

    def test_eurozone_flash_and_regular_revision_separate(self):
        for cutoff, value in (("2025-05-01T00:00:00Z",0.4),
                              ("2025-05-16T00:00:00Z",0.3),
                              ("2025-06-07T00:00:00Z",0.6)):
            with self.subTest(cutoff=cutoff):
                self.assertEqual(
                    snapshot(self.rows,cutoff)["visible_vintages"]["EUR:2025Q1"]["reported_value"],
                    value)

    def test_uk_japan_swiss_different_stage_and_definition(self):
        early = snapshot(self.rows,"2025-05-17T00:00:00Z")["visible_vintages"]
        self.assertEqual(early["GBP:2025Q1"]["reported_value"],0.7)
        self.assertEqual(early["JPY:2025Q1"]["reported_value"],-0.2)
        self.assertEqual(early["JPY:2025Q1"]["reference_base_year"],2015)
        self.assertEqual(early["CHF:2025Q1"]["reported_value"],0.7)
        late = snapshot(self.rows,"2025-07-01T00:00:00Z")["visible_vintages"]
        self.assertEqual(late["GBP:2025Q1"]["reported_value"],0.7)
        self.assertEqual(late["JPY:2025Q1"]["reported_value"],0)
        self.assertIn("-0.0",late["JPY:2025Q1"]["publisher_display_rounding"])
        self.assertEqual(late["CHF:2025Q1"]["reported_value"],0.8)
        self.assertEqual(late["CHF:2025Q1"]["reported_unit"],
                         "PERCENT_QOQ_SA_CALENDAR_SPORTS")
        self.assertEqual(late["AUD:2025Q1"]["reported_value"],0.2)
        self.assertEqual(late["CAD:2025Q1"]["reported_value"],0.5)
        self.assertEqual(late["NZD:2025Q1"]["reported_value"],0.8)

    def test_combined_six_quarters_pit_and_no_live_promotion(self):
        all_rows = []
        for file in SOURCES:
            all_rows.extend(json.loads((FIX / file).read_text(encoding="utf-8"))["records"])
        all_rows = validate(all_rows)
        self.assertEqual({row["reference_quarter"] for row in all_rows},
                         {"2025Q1","2025Q2","2025Q3","2025Q4","2026Q1","2026Q2"})
        march = snapshot(all_rows, "2025-05-31T00:00:00Z")
        self.assertIn("USD:2025Q1", march["visible_vintages"])
        self.assertNotIn("USD:2025Q2", march["visible_vintages"])
        self.assertNotIn("GBP:2026Q1", march["visible_vintages"])
        for flag in ("safe_to_update_live_macro_D", "safe_to_change_28_pairs",
                     "safe_to_use_for_beta", "safe_to_use_for_forward"):
            self.assertIs(march[flag], False)

    def test_reject_unsafe_backdated_or_forged_publication(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["publisher_release_day"] = "2025-03-31"
        with self.assertRaises(ValueError): validate(rows)
        rows = copy.deepcopy(self.rows)
        rows[0]["verified_publisher_host"] = "fake.example"
        rows[0]["source_url"] = "https://fake.example/pretend-gdp"
        with self.assertRaises(ValueError): validate(rows)
        rows = copy.deepcopy(self.rows)
        rows[0]["PIT_training_vintage_certified"] = True
        with self.assertRaises(ValueError): validate(rows)

if __name__ == "__main__":
    unittest.main()
