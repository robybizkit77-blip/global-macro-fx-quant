"""Initial five-year G8 quarterly GDP coverage: historical public-release evidence only."""
import copy
import json
import unittest
from pathlib import Path
from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot
from validation.macro.v2_g8_gdp_unified_web_research_v1 import unified_research_rows, research_receipt

DIR = Path(__file__).parent / "fixtures"
NAME = "v2_g8_gdp_q{}_2021_official_web_release_research_v1.json"
G8 = set("USD EUR GBP JPY CHF CAD AUD NZD".split())

class GDP2021FiveYearResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q3=json.loads((DIR/NAME.format(3)).read_text(encoding="utf-8"))
        cls.q4=json.loads((DIR/NAME.format(4)).read_text(encoding="utf-8"))
        cls.rows3=validate(cls.q3["records"])
        cls.rows4=validate(cls.q4["records"])

    def test_8_initial_and_6_followups_each_and_no_promotion(self):
        for q,doc,rows in [("2021Q3",self.q3,self.rows3),("2021Q4",self.q4,self.rows4)]:
            with self.subTest(q=q):
                self.assertEqual(len(rows),14)
                self.assertEqual(doc["first_releases_expected"],8)
                self.assertEqual(doc["subsequent_statements_documented"],6)
                self.assertEqual({r["currency"] for r in rows if r["stage_order"]==0},G8)
                self.assertTrue(all(r["reference_quarter"]==q for r in rows))
                self.assertTrue(all(r["PIT_training_vintage_certified"] is False
                                    and r["eligible_for_macro_scoring"] is False for r in rows))
                for flag in ("eligible_for_macro_scoring","eligible_for_beta","eligible_for_forward","may_rewrite_D_json"):
                    self.assertIs(doc[flag],False)

    def test_us_q3_original_2_to_2_1_to_2_3_no_lookahead(self):
        self.assertNotIn("USD:2021Q3",snapshot(self.rows3,"2021-10-28T23:59:59Z")["visible_vintages"])
        for at,val,stage in (
            ("2021-10-29T00:00:00Z",2.0,0),
            ("2021-11-25T00:00:00Z",2.1,1),
            ("2021-12-23T00:00:00Z",2.3,2)):
            with self.subTest(at=at):
                x=snapshot(self.rows3,at)["visible_vintages"]["USD:2021Q3"]
                self.assertEqual((x["reported_value"],x["stage_order"]),(val,stage))
                self.assertEqual(x["reported_unit"],"PERCENT_SAAR_ANNUALIZED")

    def test_us_q4_original_6_9_to_7_0_to_6_9(self):
        self.assertNotIn("USD:2021Q4",snapshot(self.rows4,"2022-01-27T23:59:59Z")["visible_vintages"])
        for at,val,stage in (
            ("2022-01-28T00:00:00Z",6.9,0),
            ("2022-02-25T00:00:00Z",7.0,1),
            ("2022-03-31T00:00:00Z",6.9,2)):
            with self.subTest(at=at):
                x=snapshot(self.rows4,at)["visible_vintages"]["USD:2021Q4"]
                self.assertEqual((x["reported_value"],x["stage_order"]),(val,stage))
                self.assertEqual(x["reported_unit"],"PERCENT_SAAR_ANNUALIZED")

    def test_euro_2021_population_ea19_and_dated_confirmation(self):
        for rows,q,dates,val in (
            (self.rows3,"2021Q3",["2021-10-30","2021-11-17","2021-12-08"],2.2),
            (self.rows4,"2021Q4",["2022-02-01","2022-02-16","2022-03-09"],0.3),
        ):
            for stage,day in enumerate(dates):
                with self.subTest(q=q,stage=stage):
                    x=snapshot(rows,day+"T00:00:00Z")["visible_vintages"]["EUR:"+q]
                    self.assertEqual((x["reported_value"],x["stage_order"]),(val,stage))
                    self.assertEqual(x["population_reference"],"EA19")
                    self.assertEqual(x["reported_unit"],"PERCENT_QOQ_SA_CALENDAR")

    def test_uk_japan_revisions_must_arrive_later(self):
        for rows,q,at0,at1,gbp,jpy in (
            (self.rows3,"2021Q3","2021-11-16","2021-12-23",(1.3,1.1),(-0.8,-0.9)),
            (self.rows4,"2021Q4","2022-02-16","2022-04-01",(1.0,1.3),(1.3,1.1))
        ):
            initial=snapshot(rows,at0+"T00:00:00Z")["visible_vintages"]
            revised=snapshot(rows,at1+"T00:00:00Z")["visible_vintages"]
            self.assertEqual(initial["GBP:"+q]["reported_value"],gbp[0])
            self.assertEqual(revised["GBP:"+q]["reported_value"],gbp[1])
            self.assertEqual(initial["JPY:"+q]["reported_value"],jpy[0])
            self.assertEqual(revised["JPY:"+q]["reported_value"],jpy[1])
            self.assertEqual(initial["JPY:"+q]["reference_base_year"],2015)
            self.assertEqual(revised["JPY:"+q]["reference_base_year"],2015)

    def test_swiss_original_scope_australia_and_nz_pandemic_swing(self):
        for rows,q,date,chf,aud,nzd in (
            (self.rows3,"2021Q3","2021-12-17",1.7,-1.9,-3.7),
            (self.rows4,"2021Q4","2022-03-18",0.3,3.4,3.0)
        ):
            visible=snapshot(rows,date+"T00:00:00Z")["visible_vintages"]
            self.assertEqual(visible["CHF:"+q]["reported_value"],chf)
            self.assertIn("NOT_ASSUMED_SPORTS",visible["CHF:"+q]["adjustment_scope"])
            self.assertEqual(visible["AUD:"+q]["reported_value"],aud)
            self.assertEqual(visible["NZD:"+q]["reported_value"],nzd)
            self.assertEqual(visible["CAD:"+q]["reported_value"],1.3 if q=="2021Q3" else 1.6)

    def test_20_consecutive_quarters_160_initial_research_keys(self):
        receipt=research_receipt()
        self.assertEqual(receipt["quarters_documented"],20)
        self.assertEqual(receipt["first_publisher_statements_documented"],160)
        self.assertEqual(receipt["first_statement_quarters_per_currency"],{c:20 for c in G8})
        rows=unified_research_rows()
        expected={f"{year}Q{q}" for year in range(2021,2027) for q in range(1,5)
                  if (year>2021 or q>=3) and (year<2026 or q<=2)}
        self.assertEqual({r["reference_quarter"] for r in rows},expected)
        first={(r["reference_quarter"],r["currency"]) for r in rows if r["stage_order"]==0}
        self.assertEqual(len(first),160)
        vintage=snapshot(rows,"2021-12-17T00:00:00Z")
        self.assertIn("NZD:2021Q3",vintage["visible_vintages"])
        self.assertNotIn("USD:2021Q4",vintage["visible_vintages"])
        for flag in ("safe_to_update_live_macro_D","safe_to_use_for_beta",
                     "safe_to_use_for_forward","safe_to_change_28_pairs"):
            self.assertIs(receipt[flag],False)
        self.assertIs(receipt["historical_training_approved"],False)
        self.assertIs(receipt["intraday_PIT_certified"],False)

    def test_forged_dates_domains_and_false_training_rejected(self):
        for rows in (self.rows3,self.rows4):
            for field,value in (
                ("publisher_release_day","2021-09-30" if rows is self.rows3 else "2021-12-31"),
                ("source_url","https://fraud.example/fabricated"),
                ("PIT_training_vintage_certified",True)):
                bad=copy.deepcopy(rows)
                bad[0][field]=value
                if field=="source_url":bad[0]["verified_publisher_host"]="fraud.example"
                with self.subTest(field=field,q=rows[0]["reference_quarter"]),self.assertRaises(ValueError):
                    validate(bad)

if __name__=="__main__":
    unittest.main()
