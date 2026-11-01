#!/usr/bin/env python3
"""Offline source and safety contract for delayed BZ=F Brent futures proxy."""
import copy
import datetime as dt
import unittest

from validation.estimated.refresh_brent_market_proxy_v1 import (
    LANE, SYMBOL, BASE_URL, parse_chart, build_output,
)

TODAY = dt.date(2026, 10, 30)
STAMP = dt.datetime(2026, 10, 30, 22, 30, tzinfo=dt.timezone.utc)


def fixture():
    days = [TODAY - dt.timedelta(days=i) for i in range(11, -1, -1)]
    return {"chart": {"error": None, "result": [{
        "meta": {"symbol": SYMBOL, "currency": "USD",
                 "instrumentType": "FUTURE", "exchangeName": "NYM"},
        "timestamp": [
            int(dt.datetime.combine(day, dt.time(), dt.timezone.utc).timestamp())
            for day in days
        ],
        "indicators": {"quote": [{"close": [110.0 + i for i in range(len(days))]}]},
    }]}}


def residual():
    return {
        "schema": "GMFQ_ESTIMATED_RESIDUAL_GAPS_V1",
        "official_lanes_untouched": True,
        "status": "INFORMATIONAL_ONLY",
        "lanes": {
            LANE: {"proxy_as_of": "2026-10-29", "value": 111.0},
            "GOLD.market_proxy": {"proxy_as_of": "2026-10-30", "value": 3900},
            "CHF.credit": {"value": 9},
        },
        "governance": {
            "core_score_effect": "NONE", "bias_effect": "NONE",
            "sizing_effect": "NONE", "pair_engine_effect": "NONE",
            "forward_logger_effect": "NONE",
            "backtest_eligible_as_official": False,
        },
    }


class BrentMarketProxyTests(unittest.TestCase):
    def test_valid_futures_delayed_quote_and_scope(self):
        rows, meta = parse_chart(fixture(), TODAY)
        source = residual()
        saved = copy.deepcopy(source)
        output = build_output(source, rows, meta, STAMP)
        self.assertEqual(source, saved)
        for key in source:
            if key != "lanes":
                self.assertEqual(output[key], source[key])
        for key in source["lanes"]:
            if key != LANE:
                self.assertEqual(output["lanes"][key], source["lanes"][key])
        b = output["lanes"][LANE]
        self.assertEqual(b["proxy_as_of"], "2026-10-30")
        self.assertEqual(b["vendor_symbol"], SYMBOL)
        self.assertEqual(b["instrument_type"], "FUTURE")
        self.assertEqual(b["source_endpoint"], BASE_URL)
        self.assertEqual(b["currency"], "USD")
        self.assertEqual(b["value"], 121.0)
        self.assertEqual(b["change_1d_pct"], round((121 / 120 - 1) * 100, 4))
        self.assertTrue(b["official_canonical_untouched"])
        self.assertIn("does not replace canonical EIA Brent spot", b["interpretation"])

    def test_wrong_metadata_must_never_default_to_futures(self):
        for key, bad in (
            ("symbol", "RBRTE"), ("symbol", None),
            ("currency", "EUR"), ("currency", None),
            ("instrumentType", "INDEX"), ("instrumentType", None)
        ):
            with self.subTest(key=key, value=bad):
                source = fixture()
                source["chart"]["result"][0]["meta"][key] = bad
                with self.assertRaises(ValueError):
                    parse_chart(source, TODAY)

    def test_dates_and_quotations_fail_closed(self):
        for flaw in ("future", "stale", "duplicate", "unsorted", "negative",
                     "nan", "short", "no_result", "two_results", "shape"):
            with self.subTest(flaw=flaw):
                obj = fixture()
                rows = obj["chart"]["result"][0]
                asof = TODAY
                if flaw == "future":
                    asof = TODAY - dt.timedelta(days=1)
                elif flaw == "stale":
                    asof = TODAY + dt.timedelta(days=4)
                elif flaw == "duplicate":
                    rows["timestamp"][-1] = rows["timestamp"][-2]
                elif flaw == "unsorted":
                    rows["timestamp"][-2:] = rows["timestamp"][-2:][::-1]
                elif flaw == "negative":
                    rows["indicators"]["quote"][0]["close"][-1] = -1
                elif flaw == "nan":
                    rows["indicators"]["quote"][0]["close"][-1] = float("nan")
                elif flaw == "short":
                    rows["timestamp"] = rows["timestamp"][-3:]
                    rows["indicators"]["quote"][0]["close"] = rows["indicators"]["quote"][0]["close"][-3:]
                elif flaw == "no_result":
                    obj["chart"]["result"] = []
                elif flaw == "two_results":
                    obj["chart"]["result"].append(copy.deepcopy(rows))
                elif flaw == "shape":
                    rows["indicators"]["quote"][0]["close"].pop()
                with self.assertRaises((ValueError, OverflowError)):
                    parse_chart(obj, asof)

    def test_safety_governance_no_rollback(self):
        rows, meta = parse_chart(fixture(), TODAY)
        for flaw in ("core", "backtest", "official", "rollback", "metadata"):
            with self.subTest(flaw=flaw):
                source = residual()
                if flaw == "core":
                    source["governance"]["core_score_effect"] = "ALLOW"
                elif flaw == "backtest":
                    source["governance"]["backtest_eligible_as_official"] = True
                elif flaw == "official":
                    source["official_lanes_untouched"] = False
                elif flaw == "rollback":
                    source["lanes"][LANE]["proxy_as_of"] = "2026-11-01"
                elif flaw == "metadata":
                    meta = {**meta, "instrumentType": "SPOT"}
                with self.assertRaises(ValueError):
                    build_output(source, rows, meta, STAMP)
                meta = fixture()["chart"]["result"][0]["meta"]

    def test_friday_close_saturday_catchup_admissible(self):
        rows, _ = parse_chart(fixture(), TODAY + dt.timedelta(days=1))
        self.assertEqual(rows[-1][0], TODAY.isoformat())
        with self.assertRaisesRegex(ValueError, "stale"):
            parse_chart(fixture(), TODAY + dt.timedelta(days=4))


if __name__ == "__main__":
    unittest.main()
