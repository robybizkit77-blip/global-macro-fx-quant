"""Contracts for the G8 credit, liquidity and conditions research bridge V4."""
import unittest
import copy
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from validation.macro import build_g8_credit_liquidity_v4 as m


class CreditLiquidityV4ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.today=datetime.now(ZoneInfo("Europe/Rome")).date()
        cls.book=m.build(today=cls.today)

    def test_eight_country_40_channel_coverage_not_40_fake_signals(self):
        b=self.book
        self.assertEqual(tuple(b["countries"]),m.FX)
        self.assertEqual(b["coverage"]["countries"],8)
        self.assertEqual(b["coverage"]["channels_possible"],40)
        self.assertEqual(b["coverage"]["fx_signals"],0)
        self.assertEqual(b["coverage"]["verified_causal_credit_chains"],0)
        self.assertFalse(b["safe_for_site"])
        self.assertFalse(b["safe_for_reports"])
        self.assertFalse(b["safe_for_fx_ranking"])
        for c,p in b["countries"].items():
            with self.subTest(currency=c):
                self.assertEqual(set(p["credit_liquidity_channels"]),set(m.ROLES))
                self.assertEqual(len(p["credit_liquidity_narrative_it"]),12)
                self.assertIsNone(p["automatic_fx_signal"])
                self.assertFalse(p["credit_transmission_causally_verified"])
                self.assertFalse(p["actual_borrower_rate_is_government_yield"])
                self.assertFalse(p["liquidity_stock_is_automatic_risk_flow"])
                self.assertFalse(p["source_releases_verified"])
                self.assertIn(p["bank"],p["credit_liquidity_narrative_it"][7])

    def test_nzd_no_fabricated_credit_data(self):
        b=self.book
        self.assertEqual(b["countries"]["NZD"]["coverage_missing_roles"],list(m.ROLES))
        self.assertEqual(len([k for k in b["coverage"]["channels_missing"]
                              if k.startswith("NZD.")]),5)
        self.assertIn("non abbiamo una serie diretta",b["countries"]["NZD"]["credit_liquidity_narrative_it"][1])

    def test_us_sloos_tightening_not_any_positive_credit_bullish_claim(self):
        rows=self.book["countries"]["USD"]["credit_liquidity_channels"]
        survey=rows["credit_supply"][0]
        self.assertEqual(survey["net_tightening_status_if_verified"],"NET_TIGHTENING")
        self.assertGreater(survey["current"],survey["previous"])
        self.assertGreater(survey["change_raw_units"],0)
        self.assertIn("irrigidimento",m.describe("credit_supply",rows["credit_supply"]))
        bank_stock=rows["credit_quantity"][0]
        self.assertEqual(bank_stock["kind"],"loan_stock")
        self.assertIsNotNone(bank_stock["within_series_stock_change_pct_not_credit_growth_rate"])
        self.assertIn("NON flusso",bank_stock["semantic_guardrail"])
        loan_rate=rows["borrowing_cost"][0]
        self.assertEqual(loan_rate["frequency"],"W")
        self.assertAlmostEqual(loan_rate["change_bp_if_borrower_rate"],19,places=1)

    def test_euro_standards_still_tightening_but_less_tightening(self):
        r=self.book["countries"]["EUR"]["credit_liquidity_channels"]["credit_supply"]
        self.assertEqual(r[0]["net_tightening_status_if_verified"],"NET_TIGHTENING")
        self.assertLess(r[0]["change_raw_units"],0)
        words=m.describe("credit_supply",r)
        self.assertIn("intensità in diminuzione",words)
        self.assertNotIn("saldo non positivo",words)
        self.assertEqual(r[1]["kind"],"survey_demand")
        self.assertIn("EUR.borrowing_cost",self.book["coverage"]["channels_missing"])

    def test_uk_mortgage_cost_is_borrower_rate_not_gilt(self):
        uk=self.book["countries"]["GBP"]
        cost=uk["credit_liquidity_channels"]["borrowing_cost"][0]
        self.assertEqual(cost["kind"],"borrower_rate")
        self.assertAlmostEqual(cost["change_bp_if_borrower_rate"],13)
        self.assertIn("prestiti/mutui",cost["semantic_guardrail"])
        approvals=uk["credit_liquidity_channels"]["credit_quantity"][0]
        self.assertEqual(approvals["kind"],"mortgage_approvals")
        self.assertIsNone(approvals["within_series_stock_change_pct_not_credit_growth_rate"])
        self.assertIn("non equivalgono",uk["credit_liquidity_narrative_it"][8])

    def test_chf_currency_fx_is_not_credit_stress(self):
        x=self.book["countries"]["CHF"]["credit_liquidity_channels"]["conditions"][0]
        self.assertEqual(x["kind"],"exchange_rate_index")
        self.assertIn("NON indice di stress",x["semantic_guardrail"])
        self.assertIn("CHF.credit_supply",self.book["coverage"]["channels_missing"])
        self.assertEqual(
            self.book["countries"]["CHF"]["rates_and_pricing"]["yield_freshness"],
            "2Y_OLDER_THAN_7_CALENDAR_DAYS")

    def test_nzd_2y_stale_and_no_policy_hypothesis_turned_signal(self):
        x=self.book["countries"]["NZD"]
        self.assertEqual(x["rates_and_pricing"]["yield_freshness"],
                         "2Y_OLDER_THAN_7_CALENDAR_DAYS")
        self.assertIn("ipotesi",x["monetary_transmission_hypothesis"])
        self.assertIsNone(x["automatic_fx_signal"])

    def test_dates_weekly_quarterly_daily_and_country_specific_formats(self):
        self.assertEqual(m.parse_period("2026-W38","W"),(date(2026,9,20),"W"))
        self.assertEqual(m.parse_period("2026-Q3","Q"),(date(2026,9,30),"Q"))
        self.assertEqual(m.parse_period("2026-07-01","Q"),(date(2026,9,30),"Q"))
        self.assertEqual(m.parse_period("2026-09-18 00:00:00+00:00","D"),
                         (date(2026,9,18),"D"))
        self.assertEqual(m.parse_period("31/07/2026","M"),(date(2026,7,31),"M"))
        self.assertEqual(m.parse_period("31-Aug-2026","M"),(date(2026,8,31),"M"))

    def test_no_future_series_no_inconsistent_numerator(self):
        sample={"id":"fake","label":"f","frequency":"M","dates":["2026-09","2026-10"],
                "values":[10,12],"last_date":"2026-10","last_value":12,
                "source_file":"fake.csv","unit":"index"}
        with self.assertRaisesRegex(ValueError,"future period"):
            m.observation(sample,"loan_stock",today=date(2026,9,30))
        sample["last_value"]=999
        with self.assertRaisesRegex(ValueError,"last_value mismatch"):
            m.observation(sample,"loan_stock",today=self.today)
        sample["last_value"]=12
        sample["dates"]=["2026-10","2026-09"]
        sample["last_date"]="2026-09"
        with self.assertRaisesRegex(ValueError,"non-ordered"):
            m.observation(sample,"loan_stock",today=self.today)

    def test_noncontiguous_stock_has_no_change_and_unknown_convention_uninterpreted(self):
        sample={"id":"x","label":"x","dates":["2026-01","2026-08"],
                "values":[10,20],"last_date":"2026-08","last_value":20,
                "frequency":"M","source_file":"x.csv"}
        obs=m.observation(sample,"loan_stock",today=self.today)
        self.assertFalse(obs["comparable_adjacent_periods"])
        self.assertIsNone(obs["within_series_stock_change_pct_not_credit_growth_rate"])
        survey=m.observation(sample,"survey_unverified_sign",today=self.today)
        self.assertIsNone(survey["net_tightening_status_if_verified"])

    def test_research_only_export_not_covering_high_yield(self):
        text=m.markdown(self.book)
        self.assertIn("NO SITO / REPORT / SEGNALI",text)
        self.assertIn("## USD",text)
        self.assertIn("## NZD",text)
        self.assertTrue(any("IG/HY" in p for p in self.book["limits"]))
        self.assertFalse(self.book["safe_for_site"])


if __name__=="__main__":
    unittest.main()
