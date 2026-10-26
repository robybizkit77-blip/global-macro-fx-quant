"""2022Q2 G8 original GDP releases and revision chronology; research-only."""
import copy
import json
import unittest
from pathlib import Path
from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot
from validation.macro.v2_g8_gdp_unified_web_research_v1 import research_receipt, unified_research_rows

SRC=Path(__file__).parent/"fixtures"/"v2_g8_gdp_q2_2022_official_web_release_research_v1.json"

class GDP2022Q2ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads(SRC.read_text(encoding="utf-8"))
        cls.rows=validate(cls.doc["records"])

    def test_eight_first_six_later_and_no_certification(self):
        first=[r for r in self.rows if r["stage_order"]==0]
        self.assertEqual(len(first),8)
        self.assertEqual(len(self.rows),14)
        self.assertEqual(len(self.rows)-len(first),6)
        self.assertEqual(self.doc["first_releases_expected"],8)
        self.assertEqual(self.doc["subsequent_statements_documented"],6)
        self.assertEqual({r["currency"] for r in first},
                         set("USD EUR GBP JPY CHF CAD AUD NZD".split()))
        self.assertTrue(all(r["reference_quarter"]=="2022Q2" for r in self.rows))
        self.assertTrue(all(r["eligible_for_macro_scoring"] is False and
                            r["PIT_training_vintage_certified"] is False for r in self.rows))
        for flag in ("eligible_for_macro_scoring","eligible_for_beta",
                     "eligible_for_forward","may_rewrite_D_json"):
            self.assertIs(self.doc[flag],False)

    def test_us_original_recession_advance_and_two_followups_annualized(self):
        self.assertNotIn("USD:2022Q2",snapshot(self.rows,"2022-07-28T23:59:59Z")["visible_vintages"])
        for at,value,stage in (
            ("2022-07-29T00:00:00Z",-0.9,0),
            ("2022-08-26T00:00:00Z",-0.6,1),
            ("2022-09-30T00:00:00Z",-0.6,2),
        ):
            with self.subTest(at=at):
                row=snapshot(self.rows,at)["visible_vintages"]["USD:2022Q2"]
                self.assertEqual((row["reported_value"],row["stage_order"]),(value,stage))
                self.assertEqual(row["reported_unit"],"PERCENT_SAAR_ANNUALIZED")

    def test_eurostat_original_ea19_flash_down_up_revisions(self):
        for at,value,stage in (
            ("2022-07-30T00:00:00Z",0.7,0),
            ("2022-08-18T00:00:00Z",0.6,1),
            ("2022-09-08T00:00:00Z",0.8,2),
        ):
            with self.subTest(at=at):
                row=snapshot(self.rows,at)["visible_vintages"]["EUR:2022Q2"]
                self.assertEqual((row["reported_value"],row["stage_order"]),(value,stage))
                self.assertEqual(row["population_reference"],"EA19")
                self.assertEqual(row["reported_unit"],"PERCENT_QOQ_SA_CALENDAR")

    def test_uk_revised_from_contraction_to_positive_quarter(self):
        first=snapshot(self.rows,"2022-08-13T00:00:00Z")["visible_vintages"]["GBP:2022Q2"]
        self.assertEqual((first["reported_value"],first["stage_order"]),(-0.1,0))
        self.assertEqual(first["reported_unit"],"PERCENT_QOQ_SA")
        before=snapshot(self.rows,"2022-09-30T23:59:59Z")["visible_vintages"]["GBP:2022Q2"]
        self.assertEqual(before["reported_value"],-0.1)
        after=snapshot(self.rows,"2022-10-01T00:00:00Z")["visible_vintages"]["GBP:2022Q2"]
        self.assertEqual((after["reported_value"],after["stage_order"]),(0.2,1))

    def test_japan_release_summary_first_vs_second_2015_benchmark(self):
        first=snapshot(self.rows,"2022-08-16T00:00:00Z")["visible_vintages"]["JPY:2022Q2"]
        self.assertEqual(first["reported_value"],0.5)
        self.assertEqual(first["reference_base_year"],2015)
        second=snapshot(self.rows,"2022-09-09T00:00:00Z")["visible_vintages"]["JPY:2022Q2"]
        self.assertEqual(second["reported_value"],0.9)
        self.assertEqual(second["reference_base_year"],2015)

    def test_swiss_correction_does_not_invent_q2_revision(self):
        prior=snapshot(self.rows,"2022-09-05T23:59:59Z")["visible_vintages"]
        self.assertNotIn("CHF:2022Q2",prior)
        post=snapshot(self.rows,"2022-09-06T00:00:00Z")["visible_vintages"]
        chf=post["CHF:2022Q2"]
        self.assertEqual(chf["reported_value"],0.3)
        self.assertEqual(chf["reported_unit"],"PERCENT_QOQ_SA_CALENDAR_SPORTS")
        self.assertEqual(chf["stage_order"],0)
        self.assertEqual(chf["publisher_correction_notice_day"],"2022-09-13")
        self.assertIn("materially unaffected",chf["publisher_correction_note"])
        self.assertIn("no false 2022Q2 revision stage added",chf["publisher_correction_note"])
        later=snapshot(self.rows,"2022-09-20T00:00:00Z")["visible_vintages"]["CHF:2022Q2"]
        self.assertEqual(later["stage_order"],0)
        self.assertIn("NOT_PROOF_NO_EARLIER_FLASH",chf["first_release_uncertainty"])

    def test_canada_australia_nz_and_global_seventeen_quarters(self):
        at=snapshot(self.rows,"2022-09-01T00:00:00Z")["visible_vintages"]
        self.assertEqual(at["CAD:2022Q2"]["reported_value"],0.8)
        self.assertNotIn("AUD:2022Q2",at)
        later=snapshot(self.rows,"2022-09-08T00:00:00Z")["visible_vintages"]
        self.assertEqual(later["AUD:2022Q2"]["reported_value"],0.9)
        self.assertNotIn("NZD:2022Q2",later)
        nz=snapshot(self.rows,"2022-09-16T00:00:00Z")["visible_vintages"]
        self.assertEqual(nz["NZD:2022Q2"]["reported_value"],1.7)
        self.assertEqual(nz["NZD:2022Q2"]["reported_unit"],
                         "PERCENT_QOQ_SA_CHAIN_VOLUME_PRODUCTION")
        receipt=research_receipt()
        self.assertEqual(receipt["quarters_documented"],17)
        self.assertEqual(receipt["first_publisher_statements_documented"],136)
        self.assertEqual(receipt["first_statement_quarters_per_currency"],
                         {c:17 for c in "USD EUR GBP JPY CHF CAD AUD NZD".split()})
        all_rows=unified_research_rows()
        self.assertEqual(len({(r["currency"],r["reference_quarter"]) for r in all_rows
                              if r["stage_order"]==0}),136)
        historic=snapshot(all_rows,"2022-09-16T00:00:00Z")
        self.assertNotIn("USD:2022Q3",historic["visible_vintages"])
        for flag in ("safe_to_update_live_macro_D","safe_to_change_28_pairs",
                     "safe_to_use_for_beta","safe_to_use_for_forward"):
            self.assertIs(historic[flag],False)
        self.assertIs(receipt["historical_training_approved"],False)

    def test_forged_domain_early_release_and_false_training_fail_closed(self):
        for field,value in (("source_url","https://fake-publisher.example/gdp"),
                            ("publisher_release_day","2022-06-30"),
                            ("PIT_training_vintage_certified",True)):
            rows=copy.deepcopy(self.rows)
            rows[0][field]=value
            if field=="source_url":
                rows[0]["verified_publisher_host"]="fake-publisher.example"
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate(rows)

if __name__=="__main__":
    unittest.main()
