"""Research-only historical publisher vintages for 2023Q1 GDP G8."""
import copy
import json
import unittest
from pathlib import Path
from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot
from validation.macro.v2_g8_gdp_unified_web_research_v1 import research_receipt, unified_research_rows

FIX = Path(__file__).parent / "fixtures"
SOURCE = FIX / "v2_g8_gdp_q1_2023_official_web_release_research_v1.json"

class GDP2023Q1ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads(SOURCE.read_text(encoding="utf-8"))
        cls.rows=validate(cls.doc["records"])

    def test_eight_original_publisher_records_and_eight_followups(self):
        first=[r for r in self.rows if r["stage_order"]==0]
        self.assertEqual(len(first),8)
        self.assertEqual(len(self.rows),16)
        self.assertEqual({r["currency"] for r in first},
                         set("USD EUR GBP JPY CHF CAD AUD NZD".split()))
        self.assertEqual(self.doc["first_releases_expected"],8)
        self.assertEqual(self.doc["subsequent_statements_documented"],8)
        self.assertTrue(all(r["reference_quarter"]=="2023Q1" for r in self.rows))
        self.assertTrue(all(r["PIT_training_vintage_certified"] is False and
                            r["eligible_for_macro_scoring"] is False for r in self.rows))
        for f in ("eligible_for_macro_scoring","eligible_for_beta","eligible_for_forward","may_rewrite_D_json"):
            self.assertIs(self.doc[f],False)

    def test_us_advance_second_third_and_no_lookahead(self):
        self.assertNotIn("USD:2023Q1",snapshot(self.rows,"2023-04-27T23:59:59Z")["visible_vintages"])
        for asof,val,stage in (
            ("2023-04-28T00:00:00Z",1.1,0),
            ("2023-05-26T00:00:00Z",1.3,1),
            ("2023-06-30T00:00:00Z",2.0,2),
        ):
            with self.subTest(asof=asof):
                r=snapshot(self.rows,asof)["visible_vintages"]["USD:2023Q1"]
                self.assertEqual((r["reported_value"],r["stage_order"]),(val,stage))
                self.assertEqual(r["reported_unit"],"PERCENT_SAAR_ANNUALIZED")

    def test_eurozone_original_positive_then_negative_after_june(self):
        for asof,val,stage in (
            ("2023-04-29T00:00:00Z",0.1,0),
            ("2023-05-17T00:00:00Z",0.1,1),
            ("2023-06-09T00:00:00Z",-0.1,2),
        ):
            with self.subTest(asof=asof):
                r=snapshot(self.rows,asof)["visible_vintages"]["EUR:2023Q1"]
                self.assertEqual((r["reported_value"],r["stage_order"]),(val,stage))
                self.assertEqual(r["population_reference"],"EA20")

    def test_uk_initial_and_q2_release_back_revision(self):
        early=snapshot(self.rows,"2023-05-13T00:00:00Z")["visible_vintages"]
        self.assertEqual(early["GBP:2023Q1"]["reported_value"],0.1)
        june=snapshot(self.rows,"2023-07-01T00:00:00Z")["visible_vintages"]
        self.assertEqual(june["GBP:2023Q1"]["reported_value"],0.1)
        sep=snapshot(self.rows,"2023-09-30T00:00:00Z")["visible_vintages"]
        self.assertEqual(sep["GBP:2023Q1"]["reported_value"],0.3)
        self.assertIn("EARLIER_Q1",sep["GBP:2023Q1"]["publication_stage"])

    def test_japan_esri_native_qoq_second_preliminary(self):
        first=snapshot(self.rows,"2023-05-18T00:00:00Z")["visible_vintages"]
        self.assertEqual(first["JPY:2023Q1"]["reported_value"],0.4)
        self.assertEqual(first["JPY:2023Q1"]["reference_base_year"],2015)
        final=snapshot(self.rows,"2023-06-09T00:00:00Z")["visible_vintages"]
        self.assertEqual(final["JPY:2023Q1"]["reported_value"],0.7)
        self.assertEqual(final["JPY:2023Q1"]["reported_unit"],"PERCENT_QOQ_SA")

    def test_swiss_earliest_located_and_later_back_revision_distinguished(self):
        before=snapshot(self.rows,"2023-05-30T23:59:59Z")["visible_vintages"]
        self.assertNotIn("CHF:2023Q1",before)
        first=snapshot(self.rows,"2023-05-31T00:00:00Z")["visible_vintages"]
        self.assertEqual(first["CHF:2023Q1"]["reported_value"],0.5)
        self.assertIn("NOT_PROOF_NO_EARLIER_FLASH",first["CHF:2023Q1"]["first_release_uncertainty"])
        later=snapshot(self.rows,"2023-09-05T00:00:00Z")["visible_vintages"]
        self.assertEqual(later["CHF:2023Q1"]["reported_value"],0.9)
        self.assertEqual(later["CHF:2023Q1"]["adjustment_scope"],"SEASONAL_CALENDAR_SPORTS")

    def test_other_first_currencies_and_14_quarter_unified_research_scope(self):
        before=snapshot(self.rows,"2023-06-08T00:00:00Z")["visible_vintages"]
        self.assertEqual(before["CAD:2023Q1"]["reported_value"],0.8)
        self.assertEqual(before["AUD:2023Q1"]["reported_value"],0.2)
        self.assertNotIn("NZD:2023Q1",before)
        after=snapshot(self.rows,"2023-06-16T00:00:00Z")["visible_vintages"]
        self.assertEqual(after["NZD:2023Q1"]["reported_value"],-0.1)
        receipt=research_receipt()
        self.assertEqual(receipt["quarters_documented"],14)
        self.assertEqual(receipt["first_publisher_statements_documented"],112)
        self.assertEqual(receipt["first_statement_quarters_per_currency"],
                         {c:14 for c in "USD EUR GBP JPY CHF CAD AUD NZD".split()})
        historic=snapshot(unified_research_rows(),"2023-06-16T00:00:00Z")
        self.assertNotIn("USD:2023Q2",historic["visible_vintages"])
        for flag in ("safe_to_update_live_macro_D","safe_to_use_for_beta",
                     "safe_to_use_for_forward","safe_to_change_28_pairs"):
            self.assertIs(historic[flag],False)
        self.assertIs(receipt["historical_training_approved"],False)

    def test_host_forgery_backdated_release_and_false_certification_blocked(self):
        for k,v in (("source_url","https://fake.example/gdp"),
                    ("publisher_release_day","2023-03-31"),
                    ("PIT_training_vintage_certified",True)):
            bad=copy.deepcopy(self.rows)
            bad[0][k]=v
            if k=="source_url":bad[0]["verified_publisher_host"]="fake.example"
            with self.subTest(k=k),self.assertRaises(ValueError):
                validate(bad)

if __name__=="__main__":
    unittest.main()
