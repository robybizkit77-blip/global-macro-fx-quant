"""Official publisher statement chronology for 2024Q3, research only."""
import copy
import json
import unittest
from pathlib import Path
from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot

FIX = Path(__file__).parent / "fixtures"
FILES = (
    "v2_g8_gdp_q3_2024_official_web_release_research_v1.json",
    "v2_g8_gdp_q4_2024_official_web_release_research_v1.json",
    "v2_g8_gdp_q1_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q2_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q3_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q4_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_multiquarter_partial_official_research_v1.json",
)

class GDP2024Q3PublisherResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = json.loads((FIX / FILES[0]).read_text(encoding="utf-8"))
        cls.rows = validate(cls.ledger["records"])

    def test_all_eight_first_and_seven_subsequent_statements(self):
        self.assertEqual(len(self.rows), 15)
        first = [r for r in self.rows if r["stage_order"] == 0]
        self.assertEqual(len(first), 8)
        self.assertEqual({r["currency"] for r in first},
                         {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"})
        self.assertEqual(len(self.rows)-len(first), 7)
        self.assertTrue(all(r["reference_quarter"] == "2024Q3" for r in self.rows))
        self.assertTrue(all(r["PIT_training_vintage_certified"] is False
                            and r["eligible_for_macro_scoring"] is False for r in self.rows))
        for flag in ("eligible_for_macro_scoring", "eligible_for_beta",
                     "eligible_for_forward", "may_rewrite_D_json"):
            self.assertIs(self.ledger[flag], False)

    def test_us_advance_second_third_version_history(self):
        self.assertNotIn("USD:2024Q3", snapshot(self.rows, "2024-10-30T23:59:59Z")["visible_vintages"])
        for day,value,stage in (("2024-10-31",2.8,0),("2024-11-28",2.8,1),
                                ("2024-12-20",3.1,2)):
            with self.subTest(day=day):
                actual = snapshot(self.rows, day+"T00:00:00Z")["visible_vintages"]["USD:2024Q3"]
                self.assertEqual((actual["reported_value"],actual["stage_order"]), (value,stage))
                self.assertEqual(actual["reported_unit"], "PERCENT_SAAR_ANNUALIZED")

    def test_uk_and_japan_revisions_late_only(self):
        first = snapshot(self.rows, "2024-11-16T00:00:00Z")["visible_vintages"]
        self.assertEqual(first["GBP:2024Q3"]["reported_value"],0.1)
        self.assertEqual(first["JPY:2024Q3"]["reported_value"],0.2)
        self.assertEqual(first["JPY:2024Q3"]["reference_base_year"],2015)
        after_jp = snapshot(self.rows, "2024-12-10T00:00:00Z")["visible_vintages"]
        self.assertEqual(after_jp["JPY:2024Q3"]["reported_value"],0.3)
        self.assertEqual(after_jp["GBP:2024Q3"]["reported_value"],0.1)
        after_uk = snapshot(self.rows, "2024-12-24T00:00:00Z")["visible_vintages"]
        self.assertEqual(after_uk["GBP:2024Q3"]["reported_value"],0.0)

    def test_euro_and_swiss_unchanged_while_nz_first_negative(self):
        early = snapshot(self.rows, "2024-12-01T00:00:00Z")["visible_vintages"]
        self.assertEqual(early["EUR:2024Q3"]["reported_value"],0.4)
        self.assertEqual(early["EUR:2024Q3"]["population_reference"],"EA20")
        self.assertEqual(early["CHF:2024Q3"]["reported_value"],0.2)
        self.assertEqual(early["CHF:2024Q3"]["reported_unit"],
                         "PERCENT_QOQ_SA_CALENDAR_SPORTS")
        self.assertNotIn("NZD:2024Q3", early)
        nz = snapshot(self.rows, "2024-12-20T00:00:00Z")["visible_vintages"]
        self.assertEqual(nz["NZD:2024Q3"]["reported_value"],-1.0)
        self.assertEqual(nz["AUD:2024Q3"]["reported_value"],0.3)
        self.assertEqual(nz["CAD:2024Q3"]["reported_value"],0.3)

    def test_eight_quarters_safely_reconstructed(self):
        all_rows = []
        for file in FILES:
            all_rows.extend(json.loads((FIX/file).read_text(encoding="utf-8"))["records"])
        all_rows = validate(all_rows)
        self.assertEqual({x["reference_quarter"] for x in all_rows},
                         {"2024Q3","2024Q4","2025Q1","2025Q2",
                          "2025Q3","2025Q4","2026Q1","2026Q2"})
        historic = snapshot(all_rows, "2024-12-01T00:00:00Z")
        self.assertIn("GBP:2024Q3", historic["visible_vintages"])
        self.assertNotIn("GBP:2024Q4", historic["visible_vintages"])
        for flag in ("safe_to_update_live_macro_D", "safe_to_change_28_pairs",
                     "safe_to_use_for_beta", "safe_to_use_for_forward"):
            self.assertIs(historic[flag],False)

    def test_reject_forgery_and_backdating(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["source_url"] = "https://example.invalid/fake"
        rows[0]["verified_publisher_host"] = "example.invalid"
        with self.assertRaises(ValueError): validate(rows)
        rows = copy.deepcopy(self.rows)
        rows[0]["publisher_release_day"] = "2024-09-30"
        with self.assertRaises(ValueError): validate(rows)
        rows = copy.deepcopy(self.rows)
        rows[0]["PIT_training_vintage_certified"] = True
        with self.assertRaises(ValueError): validate(rows)

if __name__ == "__main__":
    unittest.main()
