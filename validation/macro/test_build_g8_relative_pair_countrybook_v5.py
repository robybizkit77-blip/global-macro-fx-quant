"""G8 28-pair prospective macro/rates/FX research V5 tests."""
from __future__ import annotations

from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
import copy
import math
import unittest
from validation.macro import build_g8_relative_pair_countrybook_v5 as m


class RelativeG8PairsV5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.today=datetime.now(ZoneInfo("Europe/Rome")).date()
        cls.book=m.build(today=cls.today)

    def test_28_distinct_pairs_g8_economic_reactions_without_signals(self):
        b=self.book
        self.assertEqual(b["schema"],m.SCHEMA)
        self.assertEqual(b["scope"]["pairs"],28)
        self.assertEqual(b["scope"]["currencies"],8)
        registry=m.json.loads((m.ROOT/m.PAIR_REGISTRY_FILE).read_text())
        self.assertEqual(tuple(b["pairs"]),
                         tuple(rec["canonical_pair"] for rec in registry["pairs"].values()))
        self.assertIn("AUD/CAD",b["pairs"])
        self.assertIn("EUR/USD",b["pairs"])
        self.assertNotIn("CAD/AUD",b["pairs"])
        self.assertEqual(len(set(b["pairs"])),28)
        self.assertEqual(b["scope"]["fx_signals"],0)
        self.assertEqual(b["scope"]["validated_policy_repricing"],0)
        self.assertEqual(b["scope"]["automatic_monetary_policy_divergences"],0)
        self.assertFalse(b["scope"]["site_published"])
        self.assertFalse(b["scope"]["reports_published"])
        self.assertFalse(b["scope"]["28pair_canonical_core_modified"])
        for p,item in b["pairs"].items():
            with self.subTest(pair=p):
                self.assertEqual(item["pair"],p)
                self.assertEqual(len(item["pair_narrative_it"]),7)
                self.assertIsNone(item["fx_signal"])
                self.assertIsNone(item["position_size"])
                self.assertIsNone(item["probability_of_fx_move"])
                self.assertIsNone(item["trade_attractiveness"])
                self.assertIsNone(item["relative_repricing_pre_post_event_bp"])
                self.assertIsNone(item["macro_surprise_consensus_dated"])
                self.assertIn(item["base_bank"],item["base_bank_want_can"])
                self.assertIn(item["quote_bank"],item["quote_bank_want_can"])
                self.assertIn("WANT",item["base_bank_want_can"])
                self.assertIn("CAN",item["quote_bank_want_can"])
                self.assertIn("Funzione di reazione relativa",item["pair_narrative_it"][2])
                self.assertIn(item["research_gate"],"DESCRIPTIVE_HYPOTHESES_NOT_TRADABLE")
                self.assertIn("NON",item["pair_narrative_it"][4] if
                              item["money_market_6m"]["six_month_arithmetic_reference_spread_bp"]
                              is not None else "NON") # no 6M trade signal
                self.assertIsNone(item["rates_2y"]["observed_change_1d_relative_bp"])

    def test_price_cross_pair_math_and_observation_as_of(self):
        book=self.book
        a=book["pairs"]["EUR/USD"]["price_ecb_reference"]
        b=book["pairs"]["EUR/GBP"]["price_ecb_reference"]
        c=book["pairs"]["AUD/CAD"]["price_ecb_reference"]
        self.assertEqual(a["as_of"],book["fx_price_last_asof"])
        self.assertGreater(a["reference_price_quote_per_base"],0)
        self.assertGreater(b["reference_price_quote_per_base"],0)
        self.assertGreater(c["reference_price_quote_per_base"],0)
        self.assertEqual(a["interpretation_status"],
                         "DESCRIPTIVE_DIRECTION_NOT_TRADE_CONFIRMATION")
        self.assertIsNone(a["flow_inference"])
        self.assertIn(a["price_status"],(
            "OFFICIAL_ECB_FIXING_REFERENCE_NOT_LIVE","DATED_ECB_REFERENCE_NOT_LIVE"))
        # Compare to the LAST persisted official ECB row, not a stale constant.
        # Separate calculation here tests the publisher quote/cross identity.
        fx=m.json.loads((m.ROOT/m.PRICE_FILE).read_text())
        last=fx["rows"][-1]
        self.assertEqual(last["Date"],book["fx_price_last_asof"])
        self.assertAlmostEqual(a["reference_price_quote_per_base"],
                               last["USD"]/last["EUR"],places=7)
        self.assertAlmostEqual(b["reference_price_quote_per_base"],
                               last["GBP"]/last["EUR"],places=7)
        self.assertAlmostEqual(c["reference_price_quote_per_base"],
                               last["CAD"]/last["AUD"],places=7)
        self.assertNotEqual(book["pairs"]["AUD/CAD"]["price_ecb_reference"]["five_observation_change_pct"],None)

    def test_full_market_6m_official_is_not_homogeneous_ois(self):
        # The availability of matching official instruments changes as
        # individual issuers refresh. Do not freeze the expected 6/28 list,
        # and never call asynchronous, stale or mixed instruments OIS spreads.
        b=self.book
        ois=m.json.loads((m.ROOT/m.OIS_FILE).read_text())["currencies"]
        eligible=0
        for pair,x in b["pairs"].items():
            self.assertFalse(x["money_market_6m"]["comparable_equivalent_policy_6m"])
            self.assertIsNone(x["money_market_6m"]["implied_policy_move_difference_bp"])
            self.assertIsNone(x["money_market_6m"]["event_repricing_bp"])
            base,quote=x["base"],x["quote"]
            a,c=ois[base],ois[quote]
            official=all(
                z["operational_status"]=="GREEN_OFFICIAL"
                and z.get("quality")=="OFFICIAL_CERTIFIED"
                and m.isnum(z.get("horizons",{}).get("6m",{}).get("rate"))
                for z in (a,c)
            )
            same_date=a["as_of"]==c["as_of"]
            fresh=all(0<=(self.today-date.fromisoformat(z["as_of"])).days<=7
                      for z in (a,c))
            admissible=official and same_date and fresh
            expected_status=("OFFICIAL_SAME_DAY_HETEROGENEOUS_REFERENCE_NOT_POLICY_SPREAD"
                             if admissible else "PARTIAL_OR_ASYNCHRONOUS_REFERENCE")
            row=x["money_market_6m"]
            self.assertEqual(row["status"],expected_status,pair)
            self.assertEqual(row["six_month_arithmetic_reference_spread_bp"] is not None,
                             admissible,pair)
            if admissible:
                eligible+=1
                self.assertAlmostEqual(row["six_month_arithmetic_reference_spread_bp"],
                    round((a["horizons"]["6m"]["rate"]-
                           c["horizons"]["6m"]["rate"])*100,2),places=2)
        self.assertEqual(b["scope"]["official_same_day_heterogeneous_6m_pairs"],
                         eligible)
        self.assertEqual(b["scope"]["validated_policy_repricing"],0)

    def test_same_date_two_year_spreads_but_not_asynchronous_inferences(self):
        b=self.book
        # The number of same-day official 2Y comparisons changes as live
        # sources refresh; validate every pair's real dates, not a frozen 6/28.
        references=m.json.loads((m.ROOT/m.RATE_FILE).read_text())
        eligible=0
        for pair,item in b["pairs"].items():
            a,c=pair.split("/")
            r1,r2=references[a],references[c]
            date_ok=r1["date"]==r2["date"]
            fresh=all(0<=(self.today-date.fromisoformat(r["date"])).days<=7
                      for r in (r1,r2))
            official=all(r["quality"].startswith("FULL_CURRENT_OFFICIAL")
                         for r in (r1,r2))
            expected=date_ok and fresh and official
            value=item["rates_2y"]["spread_2y_bp"]
            self.assertEqual(value is not None,expected,pair)
            if expected:
                eligible+=1
                self.assertAlmostEqual(value,
                    round((r1["2Y"]-r2["2Y"])*100,2),places=2)
                self.assertEqual(item["rates_2y"]["rate_gap_status"],
                    "ILLUSTRATIVE_SAME_DAY_DIFFERENT_GOVERNMENT_BENCHMARKS")
            else:
                self.assertEqual(item["rates_2y"]["rate_gap_status"],
                    "NO_SYNCHRONIZED_RECENT_2Y_COMPARISON")
        self.assertEqual(b["scope"]["synchronized_2y_references"],eligible)
        self.assertEqual(
            b["pairs"]["EUR/USD"]["rates_2y"]["rate_gap_status"],
            "ILLUSTRATIVE_SAME_DAY_DIFFERENT_GOVERNMENT_BENCHMARKS")
        self.assertEqual(
            b["pairs"]["EUR/USD"]["rates_2y"]["observed_change_1d_relative_bp"],None)

    def test_currency_a_b_symmetry_in_ecb_pricing(self):
        row={"Date":"2026-11-06","EUR":1.0,"AUD":1.625,"CAD":1.5705}
        x=m.fx_ratio(row,"AUD","CAD")
        y=m.fx_ratio(row,"CAD","AUD")
        self.assertAlmostEqual(x*y,1,places=12)
        with self.assertRaisesRegex(ValueError,"invalid ECB reference"):
            m.fx_ratio({"AUD":0,"CAD":1},"AUD","CAD")

    def test_unverified_ois_rejected_even_if_has_numbers(self):
        v={"operational_status":"GREEN_ESTIMATED","quality":"ESTIMATED_INFORMATIONAL",
           "as_of":self.today.isoformat(),
           "source":"some secondary tool",
           "horizons":{"6m":{"rate":4.4}}}
        official={"operational_status":"GREEN_OFFICIAL","quality":"OFFICIAL_CERTIFIED",
                  "as_of":self.today.isoformat(),
                  "source":"official",
                  "horizons":{"6m":{"rate":4.2}}}
        p=m.forward_market("USD","AUD",{"USD":v,"AUD":official},self.today)
        self.assertIsNone(p["six_month_arithmetic_reference_spread_bp"])
        self.assertFalse(p["both_official_6m_reference"])

    def test_asynchronous_and_old_rates_cannot_be_differenced(self):
        rd={
            "USD":{"date":self.today.isoformat(),"2Y":4.1,"10Y":4.6,
                   "quality":"FULL_CURRENT_OFFICIAL","source":"official"},
            "JPY":{"date":(self.today-timedelta(days=12)).isoformat(),
                   "2Y":1.4,"10Y":2.3,
                   "quality":"FULL_CURRENT_OFFICIAL","source":"official"},
        }
        out=m.treasury("USD","JPY",rd,self.today)
        self.assertIsNone(out["spread_2y_bp"])
        self.assertFalse(out["exact_same_date"])
        rd["JPY"]["date"]=rd["USD"]["date"]
        out2=m.treasury("USD","JPY",rd,self.today)
        self.assertAlmostEqual(out2["spread_2y_bp"],270)
        rd["JPY"]["date"]=(self.today+timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError,"future market reference"):
            m.treasury("USD","JPY",rd,self.today)

    def test_no_duplicates_future_fx_or_false_operational_publish(self):
        today=self.today
        sample=[]
        start=today-timedelta(days=35)
        for i in range(26):
            dt=start+timedelta(days=i)
            sample.append({"Date":dt.isoformat(),"USD":1.1,"EUR":1.0,"JPY":150})
        r=m.price_history(sample,"USD","JPY",today)
        self.assertEqual(r["price_status"],"DATED_ECB_REFERENCE_NOT_LIVE")
        sample[-1]["Date"]=sample[-2]["Date"]
        with self.assertRaisesRegex(ValueError,"duplicated ECB fixing"):
            m.price_history(sample,"USD","JPY",today)
        sample[-1]["Date"]=(today+timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError,"future ECB reference"):
            m.price_history(sample,"USD","JPY",today)
        self.assertIn("28 coppie, nessun segnale FX",m.markdown(self.book))
        self.assertFalse(self.book["scope"]["site_published"])


if __name__=="__main__":
    unittest.main()
