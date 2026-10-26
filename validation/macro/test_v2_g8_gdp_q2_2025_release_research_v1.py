"""Quarter-2 2025 G8 original publisher statement chronology — research only."""
import copy
import json
import unittest
from pathlib import Path

from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot

F = Path(__file__).parent / "fixtures"
NAMES = [
    "v2_g8_gdp_q2_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q3_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q4_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_multiquarter_partial_official_research_v1.json",
]

class GDP2025Q2ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((F / NAMES[0]).read_text(encoding="utf-8"))
        cls.rows = validate(cls.data["records"])

    def test_eight_first_eight_followups_no_promotion(self):
        self.assertEqual(len(self.rows), 16)
        initial = [r for r in self.rows if r["stage_order"] == 0]
        self.assertEqual({r["currency"] for r in initial},
                         {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"})
        self.assertEqual(len(initial), 8)
        self.assertEqual(len(self.rows)-len(initial), 8)
        self.assertTrue(all(r["reference_quarter"] == "2025Q2" for r in self.rows))
        self.assertTrue(all(not r["PIT_training_vintage_certified"] and
                            not r["eligible_for_macro_scoring"] for r in self.rows))
        for flag in ("eligible_for_macro_scoring","eligible_for_beta",
                     "eligible_for_forward","may_rewrite_D_json"):
            self.assertIs(self.data[flag], False)

    def test_us_three_separate_releases_and_later_annual_update(self):
        first = snapshot(self.rows, "2025-07-31T00:00:00Z")["visible_vintages"]["USD:2025Q2"]
        second = snapshot(self.rows, "2025-08-29T00:00:00Z")["visible_vintages"]["USD:2025Q2"]
        third = snapshot(self.rows, "2025-09-26T00:00:00Z")["visible_vintages"]["USD:2025Q2"]
        self.assertEqual([first["reported_value"],second["reported_value"],third["reported_value"]],
                         [3.0,3.3,3.8])
        self.assertEqual(third["methodology_update"],"US_ANNUAL_NATIONAL_ACCOUNTS_UPDATE_2025")
        self.assertNotIn("USD:2025Q2", snapshot(self.rows,"2025-07-30T23:59:59Z")["visible_vintages"])
        self.assertIsNone(first.get("research_nonannualized_qoq_publisher_value"))

    def test_swiss_benchmark_and_japan_revision_not_seen_early(self):
        before = snapshot(self.rows,"2025-08-16T00:00:00Z")["visible_vintages"]
        self.assertEqual(before["CHF:2025Q2"]["reported_value"],0.1)
        self.assertEqual(before["JPY:2025Q2"]["reported_value"],0.3)
        after = snapshot(self.rows,"2025-09-30T00:00:00Z")["visible_vintages"]
        self.assertEqual(after["CHF:2025Q2"]["reported_value"],0.2)
        self.assertEqual(after["CHF:2025Q2"]["methodology_update"],
                         "SWISS_NATIONAL_ACCOUNTS_BENCHMARK_REVISION_2025")
        self.assertEqual(after["JPY:2025Q2"]["reported_value"],0.5)
        self.assertEqual(after["JPY:2025Q2"]["reference_base_year"],2015)
        self.assertEqual(before["CHF:2025Q2"]["reported_unit"],
                         "PERCENT_QOQ_SA_CALENDAR_SPORTS")

    def test_eurozone_and_uk_confirmation_not_incorrect_revision(self):
        final = snapshot(self.rows,"2025-10-01T00:00:00Z")["visible_vintages"]
        self.assertEqual(final["EUR:2025Q2"]["reported_value"],0.1)
        self.assertEqual(final["EUR:2025Q2"]["stage_order"],2)
        self.assertEqual(final["GBP:2025Q2"]["reported_value"],0.3)
        self.assertEqual(final["GBP:2025Q2"]["stage_order"],1)

    def test_cross_five_quarters_and_protection(self):
        all_rows=[]
        for name in NAMES:
            all_rows += json.loads((F/name).read_text(encoding="utf-8"))["records"]
        full=validate(all_rows)
        self.assertEqual({r["reference_quarter"] for r in full},
                         {"2025Q2","2025Q3","2025Q4","2026Q1","2026Q2"})
        at_aug=snapshot(full,"2025-08-16T00:00:00Z")
        self.assertNotIn("USD:2025Q3",at_aug["visible_vintages"])
        self.assertNotIn("USD:2025Q4",at_aug["visible_vintages"])
        self.assertNotIn("USD:2026Q1",at_aug["visible_vintages"])
        self.assertIs(at_aug["safe_to_update_live_macro_D"],False)
        self.assertIs(at_aug["safe_to_change_28_pairs"],False)
        self.assertIs(at_aug["safe_to_use_for_beta"],False)
        self.assertIs(at_aug["safe_to_use_for_forward"],False)

    def test_invalid_duplicate_or_early_future_vintage_rejected(self):
        r=copy.deepcopy(self.rows)
        r[1]["stage_order"]=0
        with self.assertRaises(ValueError): validate(r)
        r=copy.deepcopy(self.rows)
        r[2]["publisher_release_day"]="2025-06-30"
        with self.assertRaises(ValueError): validate(r)
        r=copy.deepcopy(self.rows)
        r[0]["verified_publisher_host"]="fake-bea.gov"
        with self.assertRaises(ValueError): validate(r)


if __name__=="__main__":
    unittest.main()
