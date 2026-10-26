"""G8 GDP Q3 2022 historical publisher-release vintages: research only."""
import copy
import json
import unittest
from pathlib import Path

from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot
from validation.macro.v2_g8_gdp_unified_web_research_v1 import research_receipt, unified_research_rows

FIX=Path(__file__).parent/"fixtures"/"v2_g8_gdp_q3_2022_official_web_release_research_v1.json"

class GDP2022Q3ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document=json.loads(FIX.read_text(encoding="utf-8"))
        cls.rows=validate(cls.document["records"])

    def test_eight_original_first_located_six_followups_no_promotion(self):
        first=[r for r in self.rows if r["stage_order"]==0]
        self.assertEqual(len(first),8)
        self.assertEqual(len(self.rows),14)
        self.assertEqual(len(self.rows)-len(first),6)
        self.assertEqual({r["currency"] for r in first},
                         {"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"})
        self.assertTrue(all(r["reference_quarter"]=="2022Q3" for r in self.rows))
        for flag in ("eligible_for_macro_scoring","eligible_for_beta",
                     "eligible_for_forward","may_rewrite_D_json"):
            self.assertIs(self.document[flag],False)
        self.assertTrue(all(r["PIT_training_vintage_certified"] is False for r in self.rows))

    def test_us_first_second_third_with_original_saar(self):
        self.assertNotIn("USD:2022Q3",snapshot(self.rows,"2022-10-27T23:59:59Z")["visible_vintages"])
        for at,value,stage in (
            ("2022-10-28T00:00:00Z",2.6,0),
            ("2022-12-01T00:00:00Z",2.9,1),
            ("2022-12-23T00:00:00Z",3.2,2),
        ):
            with self.subTest(at=at):
                row=snapshot(self.rows,at)["visible_vintages"]["USD:2022Q3"]
                self.assertEqual((row["reported_value"],row["stage_order"]),(value,stage))
                self.assertEqual(row["reported_unit"],"PERCENT_SAAR_ANNUALIZED")

    def test_euro_original_nineteen_members_and_december_revision(self):
        for at,value,stage in (
            ("2022-11-01T00:00:00Z",0.2,0),
            ("2022-11-16T00:00:00Z",0.2,1),
            ("2022-12-08T00:00:00Z",0.3,2),
        ):
            with self.subTest(at=at):
                row=snapshot(self.rows,at)["visible_vintages"]["EUR:2022Q3"]
                self.assertEqual((row["reported_value"],row["stage_order"]),(value,stage))
                self.assertEqual(row["population_reference"],"EA19")
                self.assertEqual(row["reported_unit"],"PERCENT_QOQ_SA_CALENDAR")

    def test_gbp_september_bank_holiday_and_december_lower_revision(self):
        first=snapshot(self.rows,"2022-11-12T00:00:00Z")["visible_vintages"]
        self.assertEqual(first["GBP:2022Q3"]["reported_value"],-0.2)
        later=snapshot(self.rows,"2022-12-23T00:00:00Z")["visible_vintages"]
        self.assertEqual(later["GBP:2022Q3"]["reported_value"],-0.3)
        self.assertEqual(later["GBP:2022Q3"]["stage_order"],1)

    def test_japan_publisher_original_PDF_two_stages_2015_base(self):
        first=snapshot(self.rows,"2022-11-16T00:00:00Z")["visible_vintages"]
        self.assertEqual(first["JPY:2022Q3"]["reported_value"],-0.3)
        self.assertEqual(first["JPY:2022Q3"]["reference_base_year"],2015)
        later=snapshot(self.rows,"2022-12-09T00:00:00Z")["visible_vintages"]
        self.assertEqual(later["JPY:2022Q3"]["reported_value"],-0.2)
        self.assertEqual(later["JPY:2022Q3"]["reference_base_year"],2015)

    def test_swiss_canada_australia_new_zealand_first_asof(self):
        before=snapshot(self.rows,"2022-11-29T23:59:59Z")["visible_vintages"]
        self.assertNotIn("CHF:2022Q3",before)
        after=snapshot(self.rows,"2022-11-30T00:00:00Z")["visible_vintages"]
        self.assertEqual(after["CHF:2022Q3"]["reported_value"],0.2)
        self.assertEqual(after["CHF:2022Q3"]["reported_unit"],
                         "PERCENT_QOQ_SA_CALENDAR_SPORTS")
        self.assertIn("NOT_PROOF_NO_EARLIER_FLASH",
                      after["CHF:2022Q3"]["first_release_uncertainty"])
        self.assertEqual(after["CAD:2022Q3"]["reported_value"],0.7)
        self.assertNotIn("AUD:2022Q3",after)
        next_week=snapshot(self.rows,"2022-12-08T00:00:00Z")["visible_vintages"]
        self.assertEqual(next_week["AUD:2022Q3"]["reported_value"],0.6)
        self.assertNotIn("NZD:2022Q3",next_week)
        later=snapshot(self.rows,"2022-12-16T00:00:00Z")["visible_vintages"]
        self.assertEqual(later["NZD:2022Q3"]["reported_value"],2.0)
        self.assertEqual(later["NZD:2022Q3"]["reported_unit"],
                         "PERCENT_QOQ_SA_CHAIN_VOLUME_PRODUCTION")

    def test_twenty_quarters_160_first_events_in_research_unified(self):
        receipt=research_receipt()
        self.assertEqual(receipt["quarters_documented"],20)
        self.assertEqual(receipt["first_publisher_statements_documented"],160)
        self.assertEqual(receipt["first_statement_quarters_per_currency"],
                         {x:20 for x in "USD EUR GBP JPY CHF CAD AUD NZD".split()})
        all_rows=unified_research_rows()
        self.assertEqual(len({(r["currency"],r["reference_quarter"]) for r in all_rows
                              if r["stage_order"]==0}),160)
        asof=snapshot(all_rows,"2022-12-16T00:00:00Z")
        self.assertIn("NZD:2022Q3",asof["visible_vintages"])
        self.assertNotIn("USD:2022Q4",asof["visible_vintages"])
        for flag in ("safe_to_update_live_macro_D","safe_to_change_28_pairs",
                     "safe_to_use_for_beta","safe_to_use_for_forward"):
            self.assertIs(asof[flag],False)
        self.assertIs(receipt["historical_training_approved"],False)
        self.assertIs(receipt["intraday_PIT_certified"],False)

    def test_fake_source_wrong_release_day_and_false_PIT_fail_closed(self):
        for field,value in (("source_url","https://fake.publisher.example/bogus"),
                            ("publisher_release_day","2022-09-30"),
                            ("PIT_training_vintage_certified",True)):
            bad=copy.deepcopy(self.rows)
            bad[0][field]=value
            if field=="source_url":bad[0]["verified_publisher_host"]="fake.publisher.example"
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate(bad)

if __name__=="__main__":
    unittest.main()
