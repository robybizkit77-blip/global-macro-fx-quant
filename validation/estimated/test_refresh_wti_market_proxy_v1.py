#!/usr/bin/env python3
"""Offline validation for WTI CL=F informational futures feed."""
import copy
import datetime as dt
import unittest
from validation.estimated.refresh_wti_market_proxy_v1 import parse_chart, build_output, SYMBOL, LANE, BASE_URL

TODAY=dt.date(2026,11,3)
STAMP=dt.datetime(2026,11,3,12,0,tzinfo=dt.timezone.utc)

def chart():
    days=[TODAY-dt.timedelta(days=i) for i in range(12,-1,-1)]
    return {"chart":{"error":None,"result":[{
        "meta":{"symbol":SYMBOL,"currency":"USD","instrumentType":"FUTURE","exchangeName":"NYM"},
        "timestamp":[int(dt.datetime.combine(day,dt.time(),dt.timezone.utc).timestamp()) for day in days],
        "indicators":{"quote":[{"close":[80.0+i for i in range(len(days))]}]},
    }]}}

def doc():
    return {"schema":"GMFQ_ESTIMATED_RESIDUAL_GAPS_V1","official_lanes_untouched":True,
        "lanes":{"BRENT.market_proxy":{"value":104.83},"GOLD.market_proxy":{"value":3938.4}},
        "governance":{"core_score_effect":"NONE","bias_effect":"NONE","sizing_effect":"NONE",
                      "pair_engine_effect":"NONE","forward_logger_effect":"NONE",
                      "backtest_eligible_as_official":False}}

class WtiProxyTests(unittest.TestCase):
    def test_parse_and_isolate_output(self):
        rows,meta=parse_chart(chart(),TODAY)
        original=doc()
        before=copy.deepcopy(original)
        result=build_output(original,rows,meta,STAMP)
        self.assertEqual(original,before)
        self.assertEqual(result["lanes"]["BRENT.market_proxy"],original["lanes"]["BRENT.market_proxy"])
        self.assertEqual(result["lanes"]["GOLD.market_proxy"],original["lanes"]["GOLD.market_proxy"])
        lane=result["lanes"][LANE]
        self.assertEqual(lane["vendor_symbol"],"CL=F")
        self.assertEqual(lane["source_endpoint"],BASE_URL)
        self.assertEqual(lane["proxy_as_of"],TODAY.isoformat())
        self.assertEqual(lane["value"],92.0)
        self.assertEqual(lane["instrument_type"],"FUTURE")
        self.assertTrue(lane["official_canonical_untouched"])
        self.assertEqual(result["governance"],original["governance"])
    def test_wrong_identity_rejected(self):
        for key,value in [("symbol","BZ=F"),("currency","EUR"),("instrumentType","INDEX")]:
            obj=chart()
            obj["chart"]["result"][0]["meta"][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                parse_chart(obj,TODAY)
    def test_stale_future_and_negative_rejected(self):
        with self.assertRaises(ValueError):
            parse_chart(chart(),TODAY+dt.timedelta(days=4))
        with self.assertRaises(ValueError):
            parse_chart(chart(),TODAY-dt.timedelta(days=1))
        obj=chart()
        obj["chart"]["result"][0]["indicators"]["quote"][0]["close"][-1]=-1
        with self.assertRaises(ValueError):
            parse_chart(obj,TODAY)
    def test_no_rollback_or_signal_leakage(self):
        rows,meta=parse_chart(chart(),TODAY)
        x=doc()
        x["lanes"][LANE]={"proxy_as_of":"2026-11-04"}
        with self.assertRaises(ValueError):
            build_output(x,rows,meta,STAMP)
        x=doc()
        x["governance"]["core_score_effect"]="ALLOW"
        with self.assertRaises(ValueError):
            build_output(x,rows,meta,STAMP)
    def test_idempotence_and_revision_audit(self):
        rows,meta=parse_chart(chart(),TODAY)
        first=build_output(doc(),rows,meta,STAMP)
        self.assertEqual(build_output(first,rows,meta,STAMP+dt.timedelta(hours=1)),first)
        revised=copy.deepcopy(rows)
        revised[-1]=(TODAY.isoformat(),93.0)
        second=build_output(first,revised,meta,STAMP+dt.timedelta(hours=1))
        self.assertEqual(second["lanes"][LANE]["vintage_audit_count"],1)
        self.assertEqual(second["lanes"][LANE]["same_date_source_vintages"][0]["market_date"],TODAY.isoformat())
if __name__=="__main__":
    unittest.main()
