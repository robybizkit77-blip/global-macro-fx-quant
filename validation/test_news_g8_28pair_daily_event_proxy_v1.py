"""Bounded offline validation for all 28 G8 ECB fixing pairs."""
import copy
import json
import unittest

from validation.news_g8_28pair_daily_event_proxy_v1 import SOURCE, build, G8


class G8DailyContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = json.loads(SOURCE.read_text(encoding="utf-8"))

    def proxy(self, source=None, *, event_date="2026-10-02", as_of="2026-10-26"):
        return build(self.fx if source is None else source,
                     event_date=event_date, as_of=as_of,
                     event_label="BLS_US_JOBS_2026_10_02")

    def test_28_unique_pairs_complete_without_event_causality(self):
        result = self.proxy()
        self.assertEqual(result["pair_count"], 28)
        self.assertEqual(result["observed_pair_count"], 28)
        self.assertEqual(len(set(p["pair"] for p in result["pairs"])), 28)
        self.assertEqual(result["status"], "DAILY_REFERENCE_CONTEXT_AVAILABLE")
        self.assertEqual(result["event_causality"], "NOT_ESTABLISHED")
        self.assertIsNone(result["event_impact_score"])
        self.assertFalse(result["eligible_for_backtest"])
        self.assertFalse(result["eligible_for_pair_rank_change"])
        self.assertFalse(result["writes_live_data"])
        self.assertTrue(result["date_filter_only_not_historical_pit_vintage_certification"])

    def test_observed_eurusd_daily_not_intra_event_pips(self):
        pair = next(x for x in self.proxy()["pairs"] if x["pair"] == "EURUSD")
        self.assertEqual(pair["previous_fixing"], 1.1298)
        self.assertEqual(pair["event_day_fixing"], 1.1225)
        self.assertEqual(pair["next_fixing"], 1.1204)
        self.assertEqual(pair["previous_to_event_fixing_pips"], -73)
        self.assertEqual(pair["event_to_next_fixing_pips"], -21)
        self.assertIsNone(pair["intraday_reaction_pips"])
        self.assertIsNone(pair["estimated_event_impact_pips"])

    def test_cross_formula_quote_over_base_and_jpy_pip_units(self):
        row = next(x for x in self.fx["rows"] if x["Date"] == "2026-10-02")
        pairs = {x["pair"]: x for x in self.proxy()["pairs"]}
        self.assertAlmostEqual(pairs["USDJPY"]["event_day_fixing"],row["JPY"]/row["USD"],places=8)
        self.assertAlmostEqual(pairs["GBPCHF"]["event_day_fixing"],row["CHF"]/row["GBP"],places=8)
        self.assertAlmostEqual(pairs["AUDNZD"]["event_day_fixing"],row["NZD"]/row["AUD"],places=8)
        self.assertEqual(pairs["USDJPY"]["pip_size"],0.01)
        self.assertEqual(pairs["EURJPY"]["pip_size"],0.01)
        self.assertEqual(pairs["AUDNZD"]["pip_size"],0.0001)

    def test_no_future_fixing_on_event_date_cutoff(self):
        result = self.proxy(as_of="2026-10-02")
        self.assertEqual(result["observed_pair_count"],0)
        self.assertEqual(result["status"],"NO_COMPARABLE_DAILY_REFERENCE_WINDOW")
        self.assertTrue(all(p["status"]=="WAITING_ADJACENT_FIXINGS" for p in result["pairs"]))

    def test_weekend_event_has_no_event_date_fixing(self):
        result = self.proxy(event_date="2026-10-03")
        self.assertEqual(result["observed_pair_count"],0)
        self.assertTrue(all(p["status"]=="NO_EVENT_DAY_FIXING" for p in result["pairs"]))

    def test_missing_currency_does_not_invent_seven_crosses(self):
        data=copy.deepcopy(self.fx)
        row=next(x for x in data["rows"] if x["Date"]=="2026-10-02")
        row["CAD"]=None
        result=self.proxy(data)
        self.assertEqual(result["observed_pair_count"],21)
        self.assertEqual(result["missing_pair_count"],7)
        self.assertEqual(sum(p["status"]=="MISSING_CURRENCY_FIXING" for p in result["pairs"]),7)
        self.assertEqual(next(p for p in result["pairs"] if p["pair"]=="EURUSD")["status"],
                         "DAILY_REFERENCE_PROXY_OBSERVED")

    def test_invalid_negative_cross_rate_rejected(self):
        data=copy.deepcopy(self.fx)
        row=next(x for x in data["rows"] if x["Date"]=="2026-10-02")
        row["AUD"]=-1.2
        with self.assertRaisesRegex(ValueError,"invalid ECB reference rate"):
            self.proxy(data)

    def test_duplicate_date_rejected(self):
        data=copy.deepcopy(self.fx)
        i=next(i for i,x in enumerate(data["rows"]) if x["Date"]=="2026-10-02")
        data["rows"].insert(i,copy.deepcopy(data["rows"][i]))
        with self.assertRaisesRegex(ValueError,"unordered or duplicated"):
            self.proxy(data)

    def test_unapproved_provenance_rejected(self):
        data=copy.deepcopy(self.fx)
        data["source_url"]="https://example.com/pretend-ecb"
        with self.assertRaisesRegex(ValueError,"invalid official ECB"):
            self.proxy(data)

    def test_fake_eur_base_rejected(self):
        data=copy.deepcopy(self.fx)
        data["rows"][0]["EUR"]=1.01
        with self.assertRaisesRegex(ValueError,"EUR base"):
            self.proxy(data)

    def test_as_of_must_follow_event(self):
        with self.assertRaisesRegex(ValueError,"as_of cannot precede"):
            self.proxy(as_of="2026-10-01")

    def test_28_pair_coverage_even_if_event_is_earliest_available(self):
        first=self.fx["first_as_of"]
        result=self.proxy(event_date=first)
        self.assertEqual(len(result["pairs"]),28)
        self.assertEqual(result["observed_pair_count"],0)
        self.assertTrue(all(p["status"]=="WAITING_ADJACENT_FIXINGS" for p in result["pairs"]))

    def test_pair_orientation_matches_8_currency_combinations(self):
        result=self.proxy()
        self.assertEqual(set(p["base_ccy"] for p in result["pairs"]), set(G8[:-1]))
        self.assertTrue(all(p["base_ccy"] != p["quote_ccy"] for p in result["pairs"]))


if __name__ == "__main__":
    unittest.main()
