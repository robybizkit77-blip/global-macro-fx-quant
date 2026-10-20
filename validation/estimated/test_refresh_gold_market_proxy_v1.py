#!/usr/bin/env python3
"""Contract tests: Gold futures is only a secondary informational lane."""
import copy
import datetime as dt
import unittest
from validation.estimated.refresh_gold_market_proxy_v1 import (
    LANE, build_output, parse_chart,
)

TODAY = dt.date(2026, 10, 20)
STAMP = dt.datetime(2026, 10, 20, 14, 15, tzinfo=dt.timezone.utc)


def fixture():
    rows = [TODAY - dt.timedelta(days=d) for d in range(11, -1, -1)]
    return {"chart": {"result": [{
        "meta": {"symbol": "GC=F", "currency": "USD", "instrumentType": "FUTURE", "exchangeName": "CMX"},
        "timestamp": [int(dt.datetime.combine(day, dt.time(), dt.timezone.utc).timestamp()) for day in rows],
        "indicators": {"quote": [{"close": [4100.0 + i for i in range(len(rows))]}]},
    }], "error": None}}


def residual():
    return {"schema": "GMFQ_ESTIMATED_RESIDUAL_GAPS_V1",
            "official_lanes_untouched": True, "status": "INFORMATIONAL_ONLY",
            "lanes": {"BRENT.market_proxy": {"value": 111.0}, "CHF.credit": {"value": 1}},
            "governance": {
                "core_score_effect": "NONE", "bias_effect": "NONE",
                "sizing_effect": "NONE", "pair_engine_effect": "NONE",
                "forward_logger_effect": "NONE", "backtest_eligible_as_official": False}}


class GoldMarketProxyTests(unittest.TestCase):
    def test_parsing_and_governance_scope(self):
        rows, meta = parse_chart(fixture(), TODAY)
        before = residual()
        saved = copy.deepcopy(before)
        after = build_output(before, rows, meta, STAMP)
        self.assertEqual(before, saved, "input was mutated")
        for key, value in before.items():
            if key != "lanes":
                self.assertEqual(after[key], value)
        for key, value in before["lanes"].items():
            self.assertEqual(after["lanes"][key], value)
        gold = after["lanes"][LANE]
        self.assertEqual(gold["vendor_symbol"], "GC=F")
        self.assertEqual(gold["instrument_type"], "FUTURE")
        self.assertEqual(gold["proxy_as_of"], TODAY.isoformat())
        self.assertEqual(gold["value"], 4111.0)
        self.assertEqual(gold["observation_count_1mo"], 12)
        self.assertTrue(gold["official_canonical_untouched"])
        self.assertIn("not LBMA", gold["interpretation"])
        self.assertIn("not certified exchange settlement", gold["interpretation"])

    def test_rejects_spot_or_other_contract(self):
        for name, value in (("symbol", "XAUUSD=X"), ("currency", "EUR"),
                            ("instrumentType", "CURRENCY")):
            with self.subTest(name=name):
                obj = fixture()
                obj["chart"]["result"][0]["meta"][name] = value
                with self.assertRaises(ValueError):
                    parse_chart(obj, TODAY)

    def test_rejects_old_or_future_data(self):
        with self.assertRaisesRegex(ValueError, "too old"):
            parse_chart(fixture(), TODAY + dt.timedelta(days=5))
        with self.assertRaisesRegex(ValueError, "future-dated"):
            parse_chart(fixture(), TODAY - dt.timedelta(days=1))

    def test_rejects_duplicates_and_bad_prices(self):
        obj = fixture()
        obj["chart"]["result"][0]["timestamp"][-1] = obj["chart"]["result"][0]["timestamp"][-2]
        with self.assertRaisesRegex(ValueError, "duplicated"):
            parse_chart(obj, TODAY)
        obj = fixture()
        obj["chart"]["result"][0]["indicators"]["quote"][0]["close"][-1] = -1
        with self.assertRaisesRegex(ValueError, "invalid quote"):
            parse_chart(obj, TODAY)

    def test_rejects_unauthorized_core_or_canonical_edits(self):
        rows, meta = parse_chart(fixture(), TODAY)
        for mutation in ("bias_score", "backtest", "official"):
            doc = residual()
            if mutation == "bias_score":
                doc["governance"]["bias_effect"] = "ACTIVE"
            elif mutation == "backtest":
                doc["governance"]["backtest_eligible_as_official"] = True
            else:
                doc["official_lanes_untouched"] = False
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                build_output(doc, rows, meta, STAMP)


if __name__ == "__main__":
    unittest.main()
