"""GDP 2024 Q2 publisher statement chronology — research only, not PIT-certified training."""
import copy
import json
import unittest
from pathlib import Path
from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot

FIX = Path(__file__).parent / "fixtures"
FILES = (
    "v2_g8_gdp_q2_2024_official_web_release_research_v1.json",
    "v2_g8_gdp_q3_2024_official_web_release_research_v1.json",
    "v2_g8_gdp_q4_2024_official_web_release_research_v1.json",
    "v2_g8_gdp_q1_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q2_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q3_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_q4_2025_official_web_release_research_v1.json",
    "v2_g8_gdp_multiquarter_partial_official_research_v1.json",
)

class GDP2024Q2ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((FIX / FILES[0]).read_text(encoding="utf-8"))
        cls.rows = validate(cls.data["records"])

    def test_all_eight_first_and_seven_followups_not_approved(self):
        self.assertEqual(len(self.rows), 15)
        first = [r for r in self.rows if r["stage_order"] == 0]
        self.assertEqual({r["currency"] for r in first},
                         {"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"})
        self.assertEqual(len(first), 8)
        self.assertEqual(len(self.rows)-len(first),7)
        self.assertTrue(all(r["reference_quarter"] == "2024Q2" for r in self.rows))
        self.assertTrue(all(r["PIT_training_vintage_certified"] is False
                            and r["eligible_for_macro_scoring"] is False for r in self.rows))
        for key in ("eligible_for_macro_scoring", "eligible_for_beta",
                    "eligible_for_forward", "may_rewrite_D_json"):
            self.assertIs(self.data[key],False)

    def test_us_releases_and_annual_update_do_not_leak(self):
        self.assertNotIn("USD:2024Q2",snapshot(self.rows,"2024-07-25T23:59:59Z")["visible_vintages"])
        for asof, value, stage in (
            ("2024-07-26T00:00:00Z",2.8,0),
            ("2024-08-30T00:00:00Z",3.0,1),
            ("2024-09-27T00:00:00Z",3.0,2)):
            with self.subTest(asof=asof):
                r=snapshot(self.rows,asof)["visible_vintages"]["USD:2024Q2"]
                self.assertEqual((r["reported_value"],r["stage_order"]),(value,stage))
                self.assertEqual(r["reported_unit"],"PERCENT_SAAR_ANNUALIZED")

    def test_eurostat_regular_estimate_not_seen_at_flash(self):
        for asof, value in (("2024-07-31T00:00:00Z",0.3),
                            ("2024-08-15T00:00:00Z",0.3),
                            ("2024-09-07T00:00:00Z",0.2)):
            r=snapshot(self.rows,asof)["visible_vintages"]["EUR:2024Q2"]
            self.assertEqual(r["reported_value"],value)
            self.assertEqual(r["population_reference"],"EA20")

    def test_uk_blue_book_change_must_be_marked(self):
        early=snapshot(self.rows,"2024-08-16T00:00:00Z")["visible_vintages"]["GBP:2024Q2"]
        later=snapshot(self.rows,"2024-10-01T00:00:00Z")["visible_vintages"]["GBP:2024Q2"]
        self.assertEqual((early["reported_value"],early["reference_base_year"]),(0.6,2019))
        self.assertEqual((later["reported_value"],later["reference_base_year"]),(0.5,2022))
        self.assertTrue(later["methodology_break_acknowledged"])
        self.assertIn("BLUE_BOOK_2024",later["methodology_update"])
        bad=copy.deepcopy(self.rows)
        for r in bad:
            if r["currency"]=="GBP" and r["stage_order"]==1:
                r["methodology_break_acknowledged"]=False
        with self.assertRaises(ValueError):
            validate(bad)

    def test_jpy_second_swiss_sports_nz_negative(self):
        early=snapshot(self.rows,"2024-08-16T00:00:00Z")["visible_vintages"]
        self.assertEqual(early["JPY:2024Q2"]["reported_value"],0.8)
        self.assertEqual(early["CHF:2024Q2"]["reported_value"],0.5)
        self.assertEqual(early["CHF:2024Q2"]["reported_unit"],
                         "PERCENT_QOQ_SA_CALENDAR_SPORTS")
        revised=snapshot(self.rows,"2024-09-10T00:00:00Z")["visible_vintages"]
        self.assertEqual(revised["JPY:2024Q2"]["reported_value"],0.7)
        after_nz=snapshot(self.rows,"2024-09-20T00:00:00Z")["visible_vintages"]
        self.assertEqual(after_nz["NZD:2024Q2"]["reported_value"],-0.2)
        self.assertEqual(after_nz["CAD:2024Q2"]["reported_value"],0.5)
        self.assertEqual(after_nz["AUD:2024Q2"]["reported_value"],0.2)

    def test_cross_nine_quarter_history_and_operational_exclusion(self):
        rows=[]
        for file in FILES:
            rows.extend(json.loads((FIX/file).read_text(encoding="utf-8"))["records"])
        all_rows=validate(rows)
        quarters={r["reference_quarter"] for r in all_rows}
        self.assertEqual(quarters,{"2024Q2","2024Q3","2024Q4","2025Q1","2025Q2",
                                   "2025Q3","2025Q4","2026Q1","2026Q2"})
        first={(r["currency"],r["reference_quarter"]) for r in all_rows if r["stage_order"]==0}
        self.assertEqual(len(first),72)
        asof=snapshot(all_rows,"2024-09-20T00:00:00Z")
        self.assertIn("NZD:2024Q2",asof["visible_vintages"])
        self.assertNotIn("USD:2024Q3",asof["visible_vintages"])
        for flag in ("safe_to_update_live_macro_D", "safe_to_change_28_pairs",
                     "safe_to_use_for_beta", "safe_to_use_for_forward"):
            self.assertIs(asof[flag],False)

    def test_forged_publisher_backdated_or_pit_promoted_fails(self):
        for field,value in (("source_url","https://fake.example/gdp"),
                            ("publisher_release_day","2024-06-30"),
                            ("PIT_training_vintage_certified",True)):
            bad=copy.deepcopy(self.rows)
            bad[0][field]=value
            if field=="source_url":
                bad[0]["verified_publisher_host"]="fake.example"
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(bad)

if __name__=="__main__":
    unittest.main()
