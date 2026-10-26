"""Q2 2023 historical GDP G8 official source vintages (research only)."""
import copy
import json
import unittest
from pathlib import Path
from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot
from validation.macro.v2_g8_gdp_unified_web_research_v1 import research_receipt, unified_research_rows

FIX=Path(__file__).parent / "fixtures"
F=FIX / "v2_g8_gdp_q2_2023_official_web_release_research_v1.json"

class GDP2023Q2ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads(F.read_text(encoding="utf-8"))
        cls.rows=validate(cls.doc["records"])

    def test_8_initial_7_followups_research_only(self):
        self.assertEqual(len(self.rows),15)
        first=[r for r in self.rows if r["stage_order"]==0]
        self.assertEqual(len(first),8)
        self.assertEqual({r["currency"] for r in first},
                         set("USD EUR GBP JPY CHF CAD AUD NZD".split()))
        self.assertEqual(len(self.rows)-len(first),7)
        for field in ("eligible_for_macro_scoring","eligible_for_beta",
                      "eligible_for_forward","may_rewrite_D_json"):
            self.assertIs(self.doc[field],False)
        self.assertTrue(all(r["PIT_training_vintage_certified"] is False for r in self.rows))

    def test_us_advance_second_third_values_and_asof(self):
        self.assertNotIn("USD:2023Q2",snapshot(self.rows,"2023-07-27T23:59:59Z")["visible_vintages"])
        for at,value,stage in [
            ("2023-07-28T00:00:00Z",2.4,0),
            ("2023-08-31T00:00:00Z",2.1,1),
            ("2023-09-29T00:00:00Z",2.1,2)
        ]:
            with self.subTest(at=at):
                r=snapshot(self.rows,at)["visible_vintages"]["USD:2023Q2"]
                self.assertEqual((r["reported_value"],r["stage_order"]),(value,stage))
                self.assertEqual(r["reported_unit"],"PERCENT_SAAR_ANNUALIZED")

    def test_euro_area_initial_0_3_revised_down_0_1(self):
        for at,value,stage in [
            ("2023-08-01T00:00:00Z",0.3,0),
            ("2023-08-17T00:00:00Z",0.3,1),
            ("2023-09-08T00:00:00Z",0.1,2)
        ]:
            with self.subTest(at=at):
                r=snapshot(self.rows,at)["visible_vintages"]["EUR:2023Q2"]
                self.assertEqual((r["reported_value"],r["stage_order"]),(value,stage))
                self.assertEqual(r["population_reference"],"EA20")

    def test_uk_first_and_september_unchanged_december_revision(self):
        initial=snapshot(self.rows,"2023-08-12T00:00:00Z")["visible_vintages"]
        self.assertEqual(initial["GBP:2023Q2"]["reported_value"],0.2)
        sept=snapshot(self.rows,"2023-09-30T00:00:00Z")["visible_vintages"]
        self.assertEqual(sept["GBP:2023Q2"]["reported_value"],0.2)
        self.assertEqual(sept["GBP:2023Q2"]["stage_order"],1)
        dec=snapshot(self.rows,"2023-12-23T00:00:00Z")["visible_vintages"]
        self.assertEqual(dec["GBP:2023Q2"]["reported_value"],0.0)
        self.assertEqual(dec["GBP:2023Q2"]["stage_order"],2)
        self.assertEqual(dec["GBP:2023Q2"]["earlier_quarter_revised_during"],
                         "2023Q3_QUARTERLY_NATIONAL_ACCOUNTS")

    def test_japan_1_5_to_1_2_original_2015_base(self):
        first=snapshot(self.rows,"2023-08-16T00:00:00Z")["visible_vintages"]
        self.assertEqual(first["JPY:2023Q2"]["reported_value"],1.5)
        self.assertEqual(first["JPY:2023Q2"]["reference_base_year"],2015)
        second=snapshot(self.rows,"2023-09-09T00:00:00Z")["visible_vintages"]
        self.assertEqual(second["JPY:2023Q2"]["reported_value"],1.2)

    def test_swiss_first_located_cad_negative_zero_nz_0_9(self):
        before=snapshot(self.rows,"2023-09-04T23:59:59Z")["visible_vintages"]
        self.assertNotIn("CHF:2023Q2",before)
        after=snapshot(self.rows,"2023-09-05T00:00:00Z")["visible_vintages"]
        self.assertEqual(after["CHF:2023Q2"]["reported_value"],0.0)
        self.assertIn("FIRST_LOCATED",after["CHF:2023Q2"]["publication_stage"])
        self.assertEqual(after["CAD:2023Q2"]["reported_value"],0.0)
        self.assertIn("-0.0%",after["CAD:2023Q2"]["original_publisher_displayed_value"])
        self.assertEqual(after["CAD:2023Q2"]["reported_unit"],"PERCENT_QOQ_SA")
        self.assertNotIn("NZD:2023Q2",after)
        nz=snapshot(self.rows,"2023-09-22T00:00:00Z")["visible_vintages"]
        self.assertEqual(nz["NZD:2023Q2"]["reported_value"],0.9)
        self.assertEqual(nz["AUD:2023Q2"]["reported_value"],0.4)

    def test_18_quarters_144_unique_first_source_records_and_no_promotion(self):
        receipt=research_receipt()
        self.assertEqual(receipt["quarters_documented"],18)
        self.assertEqual(receipt["first_publisher_statements_documented"],144)
        self.assertEqual(receipt["first_statement_quarters_per_currency"],
                         {x:18 for x in "USD EUR GBP JPY CHF CAD AUD NZD".split()})
        rows=unified_research_rows()
        self.assertEqual(len({(r["currency"],r["reference_quarter"])
                              for r in rows if r["stage_order"]==0}),144)
        historic=snapshot(rows,"2023-09-02T00:00:00Z")
        self.assertIn("CAD:2023Q2",historic["visible_vintages"])
        self.assertNotIn("NZD:2023Q2",historic["visible_vintages"])
        self.assertNotIn("USD:2023Q3",historic["visible_vintages"])
        for field in ("safe_to_update_live_macro_D","safe_to_use_for_beta",
                      "safe_to_use_for_forward","safe_to_change_28_pairs"):
            self.assertIs(historic[field],False)
        self.assertIs(receipt["historical_training_approved"],False)

    def test_invalid_host_wrong_date_and_promotion_rejected(self):
        for field,val in (("source_url","https://malicious.example/gdp"),
                          ("publisher_release_day","2023-06-30"),
                          ("PIT_training_vintage_certified",True)):
            rows=copy.deepcopy(self.rows)
            rows[0][field]=val
            if field=="source_url":rows[0]["verified_publisher_host"]="malicious.example"
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate(rows)

if __name__=="__main__":
    unittest.main()
