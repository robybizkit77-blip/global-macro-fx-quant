"""Historical G8 GDP 2023 Q4 dated statements; no live promotion."""
import copy
import json
import unittest
from pathlib import Path

from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot
from validation.macro.v2_g8_gdp_unified_web_research_v1 import unified_research_rows, research_receipt

FIX=Path(__file__).parent/"fixtures"
SOURCE=FIX/"v2_g8_gdp_q4_2023_official_web_release_research_v1.json"

class GDP2023Q4ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads(SOURCE.read_text(encoding="utf-8"))
        cls.rows=validate(cls.doc["records"])

    def test_eight_first_recorded_and_six_followups(self):
        self.assertEqual(len(self.rows),14)
        first=[r for r in self.rows if r["stage_order"]==0]
        self.assertEqual(len(first),8)
        self.assertEqual({r["currency"] for r in first},set("USD EUR GBP JPY CHF CAD AUD NZD".split()))
        self.assertEqual(self.doc["first_releases_expected"],8)
        self.assertEqual(self.doc["subsequent_statements_documented"],6)
        self.assertTrue(all(r["reference_quarter"]=="2023Q4" for r in self.rows))
        for flag in ("eligible_for_macro_scoring","eligible_for_beta",
                     "eligible_for_forward","may_rewrite_D_json"):
            self.assertIs(self.doc[flag],False)
        self.assertTrue(all(r["PIT_training_vintage_certified"] is False for r in self.rows))

    def test_us_publisher_vintages_separate_and_saar(self):
        self.assertNotIn("USD:2023Q4",snapshot(self.rows,"2024-01-25T23:59:59Z")["visible_vintages"])
        for date,value,stage in [
            ("2024-01-26",3.3,0),("2024-02-29",3.2,1),("2024-03-29",3.4,2)
        ]:
            with self.subTest(date=date):
                row=snapshot(self.rows,date+"T00:00:00Z")["visible_vintages"]["USD:2023Q4"]
                self.assertEqual((row["reported_value"],row["stage_order"]),(value,stage))
                self.assertEqual(row["reported_unit"],"PERCENT_SAAR_ANNUALIZED")

    def test_japan_sign_change_only_after_march_11(self):
        before=snapshot(self.rows,"2024-02-16T00:00:00Z")["visible_vintages"]["JPY:2023Q4"]
        self.assertEqual(before["reported_value"],-0.1)
        self.assertEqual(before["reference_base_year"],2015)
        after=snapshot(self.rows,"2024-03-12T00:00:00Z")["visible_vintages"]["JPY:2023Q4"]
        self.assertEqual(after["reported_value"],0.1)

    def test_eur_uk_unchanged_swiss_first_located_only(self):
        before=snapshot(self.rows,"2024-02-16T00:00:00Z")["visible_vintages"]
        self.assertEqual(before["EUR:2023Q4"]["reported_value"],0)
        self.assertEqual(before["EUR:2023Q4"]["population_reference"],"EA20")
        self.assertEqual(before["GBP:2023Q4"]["reported_value"],-0.3)
        self.assertNotIn("CHF:2023Q4",before)
        after=snapshot(self.rows,"2024-03-01T00:00:00Z")["visible_vintages"]
        self.assertEqual(after["CHF:2023Q4"]["reported_value"],0.3)
        self.assertEqual(after["CHF:2023Q4"]["reported_unit"],"PERCENT_QOQ_SA_CALENDAR_SPORTS")
        self.assertIn("NOT_PROOF_NO_EARLIER_FLASH",after["CHF:2023Q4"]["first_release_uncertainty"])
        self.assertEqual(after["CAD:2023Q4"]["reported_value"],0.2)
        late=snapshot(self.rows,"2024-03-29T00:00:00Z")["visible_vintages"]
        self.assertEqual(late["GBP:2023Q4"]["reported_value"],-0.3)

    def test_nz_original_minus_point_one_not_current_revised_plus_point_five(self):
        before=snapshot(self.rows,"2024-03-21T23:59:59Z")["visible_vintages"]
        self.assertNotIn("NZD:2023Q4",before)
        after=snapshot(self.rows,"2024-03-22T00:00:00Z")["visible_vintages"]
        self.assertEqual(after["NZD:2023Q4"]["reported_value"],-0.1)
        self.assertEqual(after["AUD:2023Q4"]["reported_value"],0.2)
        self.assertEqual(after["AUD:2023Q4"]["reported_unit"],"PERCENT_QOQ_SA_CHAIN_VOLUME")

    def test_eleven_quarter_union_research_only(self):
        receipt=research_receipt()
        self.assertEqual(receipt["quarters_documented"],11)
        self.assertEqual(receipt["first_publisher_statements_documented"],88)
        rows=unified_research_rows()
        first={(r["currency"],r["reference_quarter"]) for r in rows if r["stage_order"]==0}
        self.assertEqual(len(first),88)
        for flag in ("safe_to_update_live_macro_D","safe_to_use_for_beta",
                     "safe_to_use_for_forward","safe_to_change_28_pairs",
                     "historical_training_approved","intraday_PIT_certified"):
            self.assertIs(receipt[flag],False)

    def test_invalid_host_early_date_and_score_promotion_fail(self):
        for field,value in [("source_url","https://fake.example/gdp"),
                            ("publisher_release_day","2023-12-31"),
                            ("eligible_for_macro_scoring",True)]:
            bad=copy.deepcopy(self.rows)
            bad[0][field]=value
            if field=="source_url": bad[0]["verified_publisher_host"]="fake.example"
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate(bad)

if __name__=="__main__":
    unittest.main()
