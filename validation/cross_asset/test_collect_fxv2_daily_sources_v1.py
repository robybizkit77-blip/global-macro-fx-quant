#!/usr/bin/env python3
import datetime as dt
import importlib.util
import io
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[2]
MODULE=ROOT/"validation/cross_asset/collect_fxv2_daily_sources_v1.py"
spec=importlib.util.spec_from_file_location("fxv2_source_collector", MODULE)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DAY=dt.date(2026,11,4)
BASE={"schema":module.SCHEMA,"streams":{}}

def source_csv(code, vals, *, dates=None):
    if dates is None:
        dates=["2026-10-"+str(i).zfill(2) for i in range(19,29)]+["2026-11-02","2026-11-03"]
    assert len(vals)==len(dates)
    name={"IG_OAS":"BAMLC0A0CM","HY_OAS":"BAMLH0A0HYM2"}.get(code,code)
    headers=("DATE,OPEN,HIGH,LOW,CLOSE" if code=="VIX" else "observation_date,"+name)
    rows = [d+","+("0,0,0," if code=="VIX" else "")+str(v) for d,v in zip(dates,vals)]
    return "\n".join([headers,*rows])+"\n"

class FxV2CrossAssetDatedCollector(unittest.TestCase):
    def test_five_independently_dated_feeds(self):
        vals={"SP500":7541.4,"NASDAQCOM":25164.3,"IG_OAS":0.94,"HY_OAS":3.43,"VIX":21.15}
        payloads={key:source_csv(key,[v*.97]*11+[v]) for key,v in vals.items()}
        out=module.produce(DAY,BASE,payloads)
        self.assertEqual(out["status"],"FIVE_STREAMS_VERIFIED")
        self.assertEqual(len(out["streams"]),5)
        self.assertEqual(out["streams"]["VIX"]["date"],"2026-11-03")
        self.assertFalse(out["eligible_for_fx_core"])
        self.assertFalse(out["eligible_for_backtest"])
        self.assertEqual(out["streams"]["IG_OAS"]["unit"],"percent")
    def test_prevent_future_and_stale_dates(self):
        vals=[19.5]*12
        future=source_csv("VIX",vals,dates=["2026-10-"+str(i).zfill(2) for i in range(18,29)]+["2026-11-05"])
        stale=source_csv("SP500",[7500]*12,dates=["2026-09-"+str(i).zfill(2) for i in range(18,30)])
        with self.assertRaises(ValueError):
            module.validate_series("SP500",module.parse_csv("SP500",stale,DAY),DAY)
        parsed=module.parse_csv("VIX",future,DAY)
        self.assertNotEqual(parsed[-1][0],"2026-11-05")
    def test_older_source_cannot_roll_back(self):
        vals=[20]*12
        today=source_csv("VIX",vals)
        rows=module.parse_csv("VIX",today,DAY)
        with self.assertRaises(ValueError):
            module.validate_series("VIX",rows,DAY,{"date":"2026-11-04"})
    def test_missing_stream_does_not_fabricate_an_update(self):
        vix=source_csv("VIX",[20]*12)
        out=module.produce(DAY,BASE,{"VIX":vix})
        self.assertEqual(out["status"],"PARTIAL_SOURCE_SUCCESS")
        self.assertEqual(list(out["streams"]),"VIX")
        self.assertIn("SP500",out["source_errors"])
    def test_bad_source_does_not_poison_other_streams(self):
        current={"schema":module.SCHEMA,"streams":{"SP500":{"date":"2026-11-02","value":7541.4}}}
        out=module.produce(DAY,current,{"VIX":source_csv("VIX",[20]*12),"SP500":"not,a,csv\n1,2,3\n"})
        self.assertEqual(out["streams"]["SP500"]["date"],"2026-11-02")
        self.assertEqual(out["streams"]["VIX"]["date"],"2026-11-03")
    def test_csv_order_and_no_interpolation(self):
        raw=source_csv("HY_OAS",[3.43]*12)
        pts=module.parse_csv("HY_OAS",raw,DAY)
        self.assertEqual(pts[-1],("2026-11-03",3.43))
        self.assertEqual(len(pts),12)

if __name__=="__main__":
    unittest.main()
