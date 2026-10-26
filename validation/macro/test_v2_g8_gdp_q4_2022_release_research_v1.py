"""GDP Q4 2022 original official publication vintages. Research, not trained PIT."""
import copy
import json
import unittest
from pathlib import Path

from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot
from validation.macro.v2_g8_gdp_unified_web_research_v1 import research_receipt, unified_research_rows

SRC=Path(__file__).parent/"fixtures"/"v2_g8_gdp_q4_2022_official_web_release_research_v1.json"

class GDP2022Q4PublisherResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads(SRC.read_text(encoding="utf-8"))
        cls.rows=validate(cls.doc["records"])

    def test_eight_initial_six_followups_all_research_only(self):
        self.assertEqual(len(self.rows),14)
        initial=[r for r in self.rows if r["stage_order"]==0]
        self.assertEqual(len(initial),8)
        self.assertEqual({r["currency"] for r in initial},
                         {"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"})
        self.assertEqual(len(self.rows)-len(initial),6)
        self.assertEqual(self.doc["first_releases_expected"],8)
        self.assertEqual(self.doc["subsequent_statements_documented"],6)
        self.assertTrue(all(r["reference_quarter"]=="2022Q4" for r in self.rows))
        self.assertTrue(all(r["eligible_for_macro_scoring"] is False and
                            r["PIT_training_vintage_certified"] is False for r in self.rows))
        for key in ("eligible_for_macro_scoring","eligible_for_beta",
                    "eligible_for_forward","may_rewrite_D_json"):
            self.assertIs(self.doc[key],False)

    def test_us_three_gdp_versions_no_revision_lookahead(self):
        self.assertNotIn("USD:2022Q4",snapshot(self.rows,"2023-01-26T23:59:59Z")["visible_vintages"])
        for when,value,stage in (
            ("2023-01-27T00:00:00Z",2.9,0),
            ("2023-02-24T00:00:00Z",2.7,1),
            ("2023-03-31T00:00:00Z",2.6,2),
        ):
            with self.subTest(when=when):
                r=snapshot(self.rows,when)["visible_vintages"]["USD:2022Q4"]
                self.assertEqual((r["reported_value"],r["stage_order"]),(value,stage))
                self.assertEqual(r["reported_unit"],"PERCENT_SAAR_ANNUALIZED")

    def test_euro_area_preliminary_unrevised_then_zero(self):
        for when,value,stage in (
            ("2023-02-01T00:00:00Z",0.1,0),
            ("2023-02-15T00:00:00Z",0.1,1),
            ("2023-03-09T00:00:00Z",0.0,2),
        ):
            with self.subTest(when=when):
                r=snapshot(self.rows,when)["visible_vintages"]["EUR:2022Q4"]
                self.assertEqual((r["reported_value"],r["stage_order"]),(value,stage))
                self.assertEqual(r["population_reference"],"EA20")

    def test_uk_initial_stagnation_later_positive(self):
        first=snapshot(self.rows,"2023-02-11T00:00:00Z")["visible_vintages"]["GBP:2022Q4"]
        self.assertEqual(first["reported_value"],0.0)
        self.assertEqual(first["stage_order"],0)
        self.assertEqual(snapshot(self.rows,"2023-03-31T00:00:00Z")["visible_vintages"]
                         ["GBP:2022Q4"]["reported_value"],0.0)
        later=snapshot(self.rows,"2023-04-01T00:00:00Z")["visible_vintages"]["GBP:2022Q4"]
        self.assertEqual(later["reported_value"],0.1)
        self.assertEqual(later["stage_order"],1)

    def test_japan_original_archive_zero_after_second(self):
        first=snapshot(self.rows,"2023-02-15T00:00:00Z")["visible_vintages"]["JPY:2022Q4"]
        self.assertEqual(first["reported_value"],0.2)
        self.assertEqual(first["reference_base_year"],2015)
        second=snapshot(self.rows,"2023-03-10T00:00:00Z")["visible_vintages"]["JPY:2022Q4"]
        self.assertEqual(second["reported_value"],0.0)
        self.assertEqual(second["reference_base_year"],2015)

    def test_swiss_cad_aud_nz_first_publication(self):
        before=snapshot(self.rows,"2023-02-28T23:59:59Z")["visible_vintages"]
        self.assertNotIn("CHF:2022Q4",before)
        after=snapshot(self.rows,"2023-03-02T00:00:00Z")["visible_vintages"]
        self.assertEqual(after["CHF:2022Q4"]["reported_value"],0.0)
        self.assertIn("FIRST_LOCATED",after["CHF:2022Q4"]["publication_stage"])
        self.assertEqual(after["CAD:2022Q4"]["reported_value"],0.0)
        self.assertEqual(after["AUD:2022Q4"]["reported_value"],0.5)
        self.assertNotIn("NZD:2022Q4",after)
        nz=snapshot(self.rows,"2023-03-17T00:00:00Z")["visible_vintages"]
        self.assertEqual(nz["NZD:2022Q4"]["reported_value"],-0.6)
        self.assertEqual(nz["NZD:2022Q4"]["reported_unit"],
                         "PERCENT_QOQ_SA_CHAIN_VOLUME_PRODUCTION")
        self.assertIn("FIRST_RELEASE_MINUS_0_6",nz["NZD:2022Q4"]["original_source_value_not_current_vintage"])

    def test_fifteen_quarters_120_first_sources_and_no_operational_promotion(self):
        r=research_receipt()
        self.assertEqual(r["quarters_documented"],15)
        self.assertEqual(r["first_publisher_statements_documented"],120)
        self.assertEqual(r["first_statement_quarters_per_currency"],
                         {c:15 for c in "USD EUR GBP JPY CHF CAD AUD NZD".split()})
        all_rows=unified_research_rows()
        self.assertEqual(len({(x["currency"],x["reference_quarter"]) for x in all_rows
                              if x["stage_order"]==0}),120)
        early=snapshot(all_rows,"2023-02-24T00:00:00Z")
        self.assertIn("USD:2022Q4",early["visible_vintages"])
        self.assertNotIn("USD:2023Q1",early["visible_vintages"])
        for key in ("safe_to_update_live_macro_D","safe_to_change_28_pairs",
                    "safe_to_use_for_beta","safe_to_use_for_forward"):
            self.assertIs(early[key],False)
        self.assertIs(r["historical_training_approved"],False)

    def test_fail_closed_forged_host_premature_release_or_false_PIT(self):
        for field,new in (("source_url","https://forgery.example/fake"),
                          ("publisher_release_day","2022-12-31"),
                          ("PIT_training_vintage_certified",True)):
            rows=copy.deepcopy(self.rows)
            rows[0][field]=new
            if field=="source_url":rows[0]["verified_publisher_host"]="forgery.example"
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate(rows)

if __name__=="__main__":
    unittest.main()
