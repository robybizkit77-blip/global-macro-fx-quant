"""G8 inflation transmission V3 contracts: source semantics, clocks and no fake policy call."""
from __future__ import annotations
import copy
from datetime import date, datetime, timedelta
import unittest
from zoneinfo import ZoneInfo
from validation.macro import build_g8_inflation_transmission_v3 as m


class InflationTransmissionResearchV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.today=datetime.now(ZoneInfo("Europe/Rome")).date()
        cls.book=m.build(today=cls.today)

    def test_full_g8_inflation_core_and_zero_unearned_fx_signal(self):
        b=self.book
        self.assertEqual(tuple(b["countries"]),m.v2.v1.FX)
        self.assertEqual(b["coverage"]["currencies"],8)
        self.assertEqual(b["coverage"]["core_available_all"],8)
        self.assertEqual(b["coverage"]["driver_attributions_proven"],0)
        self.assertEqual(b["coverage"]["fx_signal_count"],0)
        self.assertFalse(b["safe_for_site"])
        self.assertFalse(b["safe_for_reports"])
        self.assertFalse(b["safe_for_28pair_signals"])
        self.assertIn("GBP",b["coverage"]["services_direct_missing"])
        self.assertNotIn("EUR",b["coverage"]["services_direct_missing"])
        self.assertEqual(set(b["countries"]),set(m.INFLATION))
        for c,p in b["countries"].items():
            with self.subTest(ccy=c):
                self.assertEqual(len(p["inflation_layer"]["headline"]),1)
                self.assertGreaterEqual(len(p["inflation_layer"]["core"]),1)
                self.assertEqual(len(p["inflation_narrative_it"]),11)
                self.assertIsNone(p["automatic_fx_signal"])
                self.assertFalse(p["ready_for_site"])
                self.assertFalse(p["ready_for_reports"])
                self.assertFalse(p["inflation_layer"]["demand_driven_inflation_verified"])
                self.assertFalse(p["inflation_layer"]["supply_driven_inflation_verified"])
                self.assertFalse(p["inflation_layer"]["persistent_services_inflation_verified"])
                self.assertIsNone(p["inflation_layer"]["central_bank_next_move_forecast"])
                self.assertIsNone(p["inflation_layer"]["supply_causality_proof"])
                self.assertIn(p["bank"],p["inflation_narrative_it"][9])

    def test_us_headline_and_core_indexes_transformed_to_yoy_not_levels(self):
        usd=self.book["countries"]["USD"]["inflation_layer"]
        h=usd["headline"][0]
        c=usd["core"][0]
        self.assertEqual(h["transformation"],"DERIVED_YOY_FROM_MATCHED_12M_SEASONALLY_ADJUSTED_INDEX")
        self.assertEqual(c["transformation"],h["transformation"])
        self.assertLess(h["latest_rate_pct_or_proxy_value"],20)
        self.assertLess(c["latest_rate_pct_or_proxy_value"],20)
        self.assertNotEqual(h["latest_rate_pct_or_proxy_value"],336.298)
        self.assertEqual(usd["headline_core_yoy_gap_pp_same_period_only"],None)
        w=usd["wages"][0]
        self.assertTrue(w["is_actual_wage"])
        self.assertEqual(w["transformation"],"NOMINAL_WAGE_YOY_DERIVED_FROM_HOURLY_PAY_LEVEL")
        self.assertLess(w["latest_rate_pct_or_proxy_value"],20)

    def test_uk_japan_core_semantics_cannot_relabel_as_demand(self):
        jp=self.book["countries"]["JPY"]["inflation_layer"]
        self.assertIn("includere energia",jp["core_definition"])
        self.assertFalse(jp["demand_driven_inflation_verified"])
        uk=self.book["countries"]["GBP"]["inflation_layer"]
        self.assertEqual(uk["services"],[])
        self.assertEqual(uk["wages"],[])

    def test_euro_services_wages_observed_but_not_same_clock(self):
        eu=self.book["countries"]["EUR"]["inflation_layer"]
        self.assertEqual(len(eu["services"]),1)
        self.assertEqual(len(eu["wages"]),1)
        self.assertFalse(eu["headline_core_same_economic_period"])
        self.assertIsNone(eu["headline_core_yoy_gap_pp_same_period_only"])
        self.assertEqual(eu["wages"][0]["frequency"],"Q")

    def test_canadian_boc_business_survey_is_not_cpi_percent(self):
        ca=self.book["countries"]["CAD"]["inflation_layer"]
        self.assertEqual(len(ca["core"]),2)
        self.assertEqual(
            ca["expectations"][0]["transformation"],
            "BUSINESS_PRICE_SURVEY_INDICATOR_NOT_CPI")
        self.assertTrue(ca["expectations"][0]["is_survey_not_price_or_paid_wage"])
        self.assertNotIn(
            "1,00%",m.inflation_sentence(ca["expectations"],kind="Sondaggio"))

    def test_australian_monthly_context_not_merged_into_quarterly(self):
        au=self.book["countries"]["AUD"]["inflation_layer"]
        self.assertEqual(au["headline"][0]["frequency"],"Q")
        self.assertEqual(au["core"][0]["frequency"],"Q")
        self.assertEqual(len(au["monthly_context"]),2)
        self.assertTrue(all(x["frequency"]=="M" for x in au["monthly_context"]))
        self.assertIn("non viene sommato",self.book["countries"]["AUD"]["inflation_narrative_it"][2])

    def test_nz_expectation_is_quarterly_survey_not_observed_wages(self):
        nz=self.book["countries"]["NZD"]["inflation_layer"]
        self.assertTrue(all(x["frequency"]=="Q" for x in nz["expectations"]))
        self.assertEqual(len(nz["expectations"]),2)
        self.assertEqual(len(nz["wage_expectations"]),1)
        self.assertTrue(nz["wage_expectations"][0]["is_survey_not_price_or_paid_wage"])
        self.assertFalse(nz["wage_expectations"][0]["is_actual_wage"])
        self.assertEqual(nz["wages"],[])

    def test_index_yoy_requires_valid_matched_calendar_year(self):
        dummy={
            "id":"test_index",
            "dates":["2025-01","2026-01"],
            "values":[100,109],
            "last_date":"2026-01",
            "last_value":109,"unit":"Index 2017=100","frequency":"M",
            "label":"Example","source_file":"demo.csv",
        }
        self.assertAlmostEqual(m.yoy_index_values(dummy,1),9)
        with self.assertRaisesRegex(ValueError,"missing/duplicate 12m index comparator"):
            m.yoy_index_values(dummy,0)
        dummy["dates"][0]="2025-02"
        with self.assertRaisesRegex(ValueError,"missing/duplicate 12m index comparator"):
            m.yoy_index_values(dummy,1)

    def test_future_and_out_of_order_observations_fail_closed(self):
        sample={"id":"x","label":"test","dates":["2026-08","2026-09"],
                "values":[3.1,3.4],"last_date":"2026-09","last_value":3.4,
                "frequency":"M","unit":"Percent YoY","source_file":"test.csv"}
        with self.assertRaisesRegex(ValueError,"future observation"):
            m.inflation_row(sample,today=date(2026,8,31),meaning="headline")
        sample["dates"]=["2026-09","2026-08"]
        sample["last_date"]="2026-08"
        with self.assertRaisesRegex(ValueError,"non-increasing"):
            m.inflation_row(sample,today=date(2026,11,9),meaning="headline")

    def test_research_output_has_stated_gaps_and_no_production_files(self):
        b=self.book
        txt=m.markdown(b)
        self.assertIn("SOLO RICERCA",txt)
        self.assertIn("## USD",txt)
        self.assertIn("## NZD",txt)
        self.assertFalse(b["safe_for_site"])
        self.assertIn("macro_series",b["source_paths"])
        self.assertEqual(
            b["source_sha256"]["macro_series"],b["source_sha256"]["inflation_series"])
        self.assertIn("GBP.wages",b["coverage"]["selected_components_missing"])


if __name__=="__main__":
    unittest.main()
