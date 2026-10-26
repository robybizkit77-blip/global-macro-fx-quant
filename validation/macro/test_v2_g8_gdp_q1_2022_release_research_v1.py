"""Original G8 2022Q1 GDP release chronology — research only, not certified PIT."""
import copy
import json
import unittest
from pathlib import Path

from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot
from validation.macro.v2_g8_gdp_unified_web_research_v1 import research_receipt, unified_research_rows

F=Path(__file__).parent/"fixtures"/"v2_g8_gdp_q1_2022_official_web_release_research_v1.json"

class GDP2022Q1ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads(F.read_text(encoding="utf-8"))
        cls.rows=validate(cls.doc["records"])

    def test_eight_first_and_seven_later_research_only(self):
        first=[r for r in self.rows if r["stage_order"]==0]
        self.assertEqual(len(first),8)
        self.assertEqual(len(self.rows),15)
        self.assertEqual(len(self.rows)-len(first),7)
        self.assertEqual({r["currency"] for r in first},
                         {"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"})
        self.assertEqual(self.doc["first_releases_expected"],8)
        self.assertEqual(self.doc["subsequent_statements_documented"],7)
        for key in ("eligible_for_macro_scoring","eligible_for_beta",
                    "eligible_for_forward","may_rewrite_D_json"):
            self.assertIs(self.doc[key],False)
        self.assertTrue(all(r["PIT_training_vintage_certified"] is False and
                            r["eligible_for_macro_scoring"] is False for r in self.rows))

    def test_us_advance_second_third_original_annualized_values(self):
        self.assertNotIn("USD:2022Q1",
                         snapshot(self.rows,"2022-04-28T23:59:59Z")["visible_vintages"])
        for at,value,stage in (
            ("2022-04-29T00:00:00Z",-1.4,0),
            ("2022-05-27T00:00:00Z",-1.5,1),
            ("2022-06-30T00:00:00Z",-1.6,2)):
            with self.subTest(at=at):
                r=snapshot(self.rows,at)["visible_vintages"]["USD:2022Q1"]
                self.assertEqual((r["reported_value"],r["stage_order"]),(value,stage))
                self.assertEqual(r["reported_unit"],"PERCENT_SAAR_ANNUALIZED")

    def test_eurozone_ea19_first_second_regular_vintages(self):
        for at,value,stage in (
            ("2022-04-30T00:00:00Z",0.2,0),
            ("2022-05-18T00:00:00Z",0.3,1),
            ("2022-06-09T00:00:00Z",0.6,2)):
            with self.subTest(at=at):
                r=snapshot(self.rows,at)["visible_vintages"]["EUR:2022Q1"]
                self.assertEqual((r["reported_value"],r["stage_order"]),(value,stage))
                self.assertEqual(r["population_reference"],"EA19")

    def test_uk_first_and_quarterly_confirmation(self):
        first=snapshot(self.rows,"2022-05-13T00:00:00Z")["visible_vintages"]
        self.assertEqual(first["GBP:2022Q1"]["reported_value"],0.8)
        self.assertEqual(first["GBP:2022Q1"]["stage_order"],0)
        later=snapshot(self.rows,"2022-07-01T00:00:00Z")["visible_vintages"]
        self.assertEqual((later["GBP:2022Q1"]["reported_value"],
                          later["GBP:2022Q1"]["stage_order"]),(0.8,1))

    def test_japan_first_vs_second_2015_benchmark(self):
        first=snapshot(self.rows,"2022-05-19T00:00:00Z")["visible_vintages"]
        self.assertEqual(first["JPY:2022Q1"]["reported_value"],-0.2)
        self.assertEqual(first["JPY:2022Q1"]["reference_base_year"],2015)
        later=snapshot(self.rows,"2022-06-09T00:00:00Z")["visible_vintages"]
        self.assertEqual(later["JPY:2022Q1"]["reported_value"],-0.1)

    def test_swiss_original_not_sports_adjusted_and_later_correction(self):
        before=snapshot(self.rows,"2022-05-31T23:59:59Z")["visible_vintages"]
        self.assertNotIn("CHF:2022Q1",before)
        first=snapshot(self.rows,"2022-06-01T00:00:00Z")["visible_vintages"]
        chf=first["CHF:2022Q1"]
        self.assertEqual(chf["reported_value"],0.5)
        self.assertEqual(chf["reported_unit"],"PERCENT_QOQ_SA_CALENDAR_NO_SPORTS")
        self.assertIn("NOT_PROOF_NO_EARLIER_FLASH",chf["first_release_uncertainty"])
        before_correction=snapshot(self.rows,"2022-09-13T23:59:59Z")["visible_vintages"]
        self.assertEqual(before_correction["CHF:2022Q1"]["reported_value"],0.5)
        revised=snapshot(self.rows,"2022-09-14T00:00:00Z")["visible_vintages"]["CHF:2022Q1"]
        self.assertEqual((revised["reported_value"],revised["stage_order"]),(0.3,1))
        comp=revised["sport_adjusted_comparator"]
        self.assertEqual(comp["value"],0.2)
        self.assertEqual(comp["reported_unit"],"PERCENT_QOQ_SA_CALENDAR_SPORTS")
        self.assertIs(comp["not_a_same_series_stage"],True)
        self.assertEqual(revised["reported_unit"],chf["reported_unit"])

    def test_canada_australia_nz_and_eighteen_quarters(self):
        may=snapshot(self.rows,"2022-06-01T00:00:00Z")["visible_vintages"]
        self.assertEqual(may["CAD:2022Q1"]["reported_value"],0.8)
        self.assertNotIn("AUD:2022Q1",may)
        june=snapshot(self.rows,"2022-06-02T00:00:00Z")["visible_vintages"]
        self.assertEqual(june["AUD:2022Q1"]["reported_value"],0.8)
        self.assertNotIn("NZD:2022Q1",june)
        nz=snapshot(self.rows,"2022-06-17T00:00:00Z")["visible_vintages"]
        self.assertEqual(nz["NZD:2022Q1"]["reported_value"],-0.2)
        r=research_receipt()
        self.assertEqual(r["quarters_documented"],18)
        self.assertEqual(r["first_publisher_statements_documented"],144)
        self.assertEqual(r["first_statement_quarters_per_currency"],
                         {c:18 for c in "USD EUR GBP JPY CHF CAD AUD NZD".split()})
        rows=unified_research_rows()
        self.assertEqual(len({(x["currency"],x["reference_quarter"])
                              for x in rows if x["stage_order"]==0}),144)
        asof=snapshot(rows,"2022-06-17T00:00:00Z")
        self.assertNotIn("USD:2022Q2",asof["visible_vintages"])
        for key in ("safe_to_update_live_macro_D","safe_to_change_28_pairs",
                    "safe_to_use_for_beta","safe_to_use_for_forward"):
            self.assertIs(asof[key],False)
        self.assertIs(r["historical_training_approved"],False)

    def test_fake_source_backdating_and_false_certification_rejected(self):
        for field,value in (("source_url","https://fraud.example/gdp"),
                            ("publisher_release_day","2022-03-31"),
                            ("PIT_training_vintage_certified",True)):
            rows=copy.deepcopy(self.rows)
            rows[0][field]=value
            if field=="source_url":
                rows[0]["verified_publisher_host"]="fraud.example"
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate(rows)

if __name__=="__main__":
    unittest.main()
