"""Q3 2023 original GDP publisher statements (research-only retrospective archive)."""
import copy
import json
import unittest
from pathlib import Path

from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot
from validation.macro.v2_g8_gdp_unified_web_research_v1 import research_receipt, unified_research_rows

SOURCE=Path(__file__).parent/"fixtures"/"v2_g8_gdp_q3_2023_official_web_release_research_v1.json"

class GDP2023Q3ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads(SOURCE.read_text(encoding="utf-8"))
        cls.rows=validate(cls.source["records"])

    def test_eight_first_recorded_and_six_followups_unpromoted(self):
        self.assertEqual(len(self.rows),14)
        self.assertEqual(self.source["first_releases_expected"],8)
        self.assertEqual(self.source["subsequent_statements_documented"],6)
        first=[r for r in self.rows if r["stage_order"]==0]
        self.assertEqual({r["currency"] for r in first},
            {"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"})
        self.assertEqual(len(first),8)
        self.assertTrue(all(r["reference_quarter"]=="2023Q3" for r in self.rows))
        self.assertTrue(all(r["PIT_training_vintage_certified"] is False
                            and r["eligible_for_macro_scoring"] is False for r in self.rows))
        for flag in ("eligible_for_macro_scoring","eligible_for_beta",
                     "eligible_for_forward","may_rewrite_D_json"):
            self.assertIs(self.source[flag],False)

    def test_us_advance_second_third_2023_release_history(self):
        self.assertNotIn("USD:2023Q3",
            snapshot(self.rows,"2023-10-26T23:59:59Z")["visible_vintages"])
        for at,value,stage in (("2023-10-27T00:00:00Z",4.9,0),
                               ("2023-11-30T00:00:00Z",5.2,1),
                               ("2023-12-22T00:00:00Z",4.9,2)):
            with self.subTest(at=at):
                r=snapshot(self.rows,at)["visible_vintages"]["USD:2023Q3"]
                self.assertEqual((r["reported_value"],r["stage_order"]),(value,stage))
                self.assertEqual(r["reported_unit"],"PERCENT_SAAR_ANNUALIZED")

    def test_eurostat_three_original_publisher_events_no_revision(self):
        for at,stage in (("2023-11-01T00:00:00Z",0),
                         ("2023-11-15T00:00:00Z",1),
                         ("2023-12-08T00:00:00Z",2)):
            with self.subTest(at=at):
                r=snapshot(self.rows,at)["visible_vintages"]["EUR:2023Q3"]
                self.assertEqual(r["reported_value"],-0.1)
                self.assertEqual(r["stage_order"],stage)
                self.assertEqual(r["population_reference"],"EA20")

    def test_uk_revised_down_and_japan_second_preliminary(self):
        initial=snapshot(self.rows,"2023-11-16T00:00:00Z")["visible_vintages"]
        self.assertEqual(initial["GBP:2023Q3"]["reported_value"],0)
        self.assertEqual(initial["JPY:2023Q3"]["reported_value"],-0.5)
        self.assertEqual(initial["JPY:2023Q3"]["reference_base_year"],2015)
        second=snapshot(self.rows,"2023-12-09T00:00:00Z")["visible_vintages"]
        self.assertEqual(second["JPY:2023Q3"]["reported_value"],-0.7)
        self.assertEqual(second["GBP:2023Q3"]["reported_value"],0)
        final=snapshot(self.rows,"2023-12-23T00:00:00Z")["visible_vintages"]
        self.assertEqual(final["GBP:2023Q3"]["reported_value"],-0.1)

    def test_swiss_first_located_not_claiming_flash_and_asof(self):
        before=snapshot(self.rows,"2023-12-01T23:59:59Z")["visible_vintages"]
        self.assertNotIn("CHF:2023Q3",before)
        after=snapshot(self.rows,"2023-12-02T00:00:00Z")["visible_vintages"]
        chf=after["CHF:2023Q3"]
        self.assertEqual(chf["reported_value"],0.3)
        self.assertEqual(chf["reported_unit"],"PERCENT_QOQ_SA_CALENDAR_SPORTS")
        self.assertEqual(chf["publication_stage"],"FIRST_LOCATED_DETAILED_RELEASE")
        self.assertIn("NOT_PROOF_NO_EARLIER_FLASH",chf["first_release_uncertainty"])
        self.assertEqual(after["CAD:2023Q3"]["reported_value"],-0.3)

    def test_australia_nz_first_vintages_and_later_visibility(self):
        before=snapshot(self.rows,"2023-12-07T00:00:00Z")["visible_vintages"]
        self.assertEqual(before["AUD:2023Q3"]["reported_value"],0.2)
        self.assertNotIn("NZD:2023Q3",before)
        later=snapshot(self.rows,"2023-12-15T00:00:00Z")["visible_vintages"]
        self.assertEqual(later["NZD:2023Q3"]["reported_value"],-0.3)
        self.assertEqual(later["NZD:2023Q3"]["reported_unit"],
                         "PERCENT_QOQ_SA_CHAIN_VOLUME_PRODUCTION")

    def test_unified_fourteen_quarters_112_first_records_not_live(self):
        receipt=research_receipt()
        self.assertEqual(receipt["quarters_documented"],14)
        self.assertEqual(receipt["first_publisher_statements_documented"],112)
        all_rows=unified_research_rows()
        first={(r["currency"],r["reference_quarter"]) for r in all_rows
               if r["stage_order"]==0}
        self.assertEqual(len(first),112)
        at=snapshot(all_rows,"2023-12-22T00:00:00Z")
        self.assertIn("NZD:2023Q3",at["visible_vintages"])
        self.assertNotIn("USD:2023Q4",at["visible_vintages"])
        for flag in ("safe_to_update_live_macro_D","safe_to_use_for_beta",
                     "safe_to_use_for_forward","safe_to_change_28_pairs"):
            self.assertIs(at[flag],False)
        self.assertIs(receipt["historical_training_approved"],False)

    def test_invalid_source_and_future_promotion_rejected(self):
        for field, value in (("source_url","https://malicious.example/false"),
                             ("publisher_release_day","2023-09-30"),
                             ("PIT_training_vintage_certified",True)):
            rows=copy.deepcopy(self.rows)
            rows[0][field]=value
            if field=="source_url":
                rows[0]["verified_publisher_host"]="malicious.example"
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(rows)

if __name__=="__main__":
    unittest.main()
