#!/usr/bin/env python3
"""Offline safety checks for actual-date prospective shadow forecast captures."""
import importlib.util
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
name = "g8prospective"
spec = importlib.util.spec_from_file_location(name, HERE / "capture_g8_prospective_v1.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FirstSeenCapture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT/"live_data/sections/MACRO_SERIES.json").read_bytes()
        cls.model = (ROOT/"site/fx-quant-v2/next/g8-growth-shadow.js").read_bytes()
        cls.when = datetime(2026,11,12,8,49,0,tzinfo=timezone.utc)
        cls.receipt = module.build_receipt(cls.source,cls.model,"a"*40,cls.when)

    def test_frozen_verifiable_sources_and_no_trading_claim(self):
        r=self.receipt
        self.assertEqual(r["schema"],"GMFQ_G8_GROWTH_PROSPECTIVE_CAPTURE_V1")
        self.assertEqual(r["capture_rome_date"],"2026-11-12")
        self.assertEqual(r["source_macro_sha256"],module.sha256_bytes(self.source))
        self.assertEqual(r["source_model_sha256"],module.sha256_bytes(self.model))
        self.assertFalse(r["issuer_release_vintage_verified"])
        self.assertFalse(r["forecast_is_issuer_pre_release_certified"])
        self.assertFalse(r["affects_fx_rankings_or_signals"])
        self.assertEqual(set(r["selected_macro_vintage"]),set(module.FX))
        self.assertEqual(r["forecast_evidence"]["qualified"],["USD"])
        self.assertEqual(r["forecast_evidence"]["currencies"]["USD"]["nextObservationPeriod"],"2026-10")
        self.assertEqual(r["forecast_evidence"]["currencies"]["EUR"]["forecast"],None)
        self.assertIn("NON_ISSUER_FIRST_RELEASE",
          "NON_ISSUER_FIRST_RELEASE")  # explicit negative PIT contract above
        for ccy in module.FX:
            selected=r["selected_macro_vintage"][ccy]
            self.assertTrue(selected["observations"])
            self.assertEqual(selected["latest_observation_period"],selected["observations"][-1]["period"])
            self.assertTrue(all(x["period"]<="2026-11" for x in selected["observations"]))
            self.assertEqual(selected["historical_vintage"],
                             "FIRST_SEEN_IN_THIS_SYSTEM_NOT_ISSUER_FIRST_RELEASE")

    def test_deterministic_frozen_model_for_same_source_cutoff(self):
        a=module.build_receipt(self.source,self.model,"a"*40,self.when)
        b=module.build_receipt(self.source,self.model,"a"*40,self.when)
        self.assertEqual(a,b)

    def test_never_use_future_observation_or_duplicate_period(self):
        source=json.loads(self.source)
        us=next(x for x in source["USD"] if x["id"]=="US_PCEC96_history_value")
        us["dates"].append("2027-01-01")
        us["values"].append(999999.0)
        future=json.dumps(source,ensure_ascii=False).encode()
        result=module.build_receipt(future,self.model,"b"*40,self.when)
        self.assertEqual(result["forecast_evidence"]["currencies"]["USD"]["forecast"],
                         self.receipt["forecast_evidence"]["currencies"]["USD"]["forecast"])
        self.assertEqual(result["selected_macro_vintage"]["USD"]["latest_observation_period"],"2026-09")
        self.assertNotEqual(result["source_macro_sha256"],self.receipt["source_macro_sha256"])
        source=json.loads(self.source)
        us=next(x for x in source["USD"] if x["id"]=="US_PCEC96_history_value")
        us["dates"].append(us["dates"][-1])
        us["values"].append(us["values"][-1])
        with self.assertRaises(ValueError):
            module.build_receipt(json.dumps(source).encode(),self.model,"c"*40,self.when)

    def test_never_rewrite_existing_daily_capture(self):
        now=datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
        r={**self.receipt,"capture_rome_date":now}
        with patch.object(module,"github_json",return_value=(200,{"sha":"already"})) as api:
            result=module.publish_once(r,"fake-token","someowner/somerepo",now)
        self.assertEqual(result["status"],"ALREADY_CAPTURED_IMMUTABLE")
        self.assertFalse(result["wrote"])
        self.assertEqual(api.call_count,1)

    def test_new_capture_is_create_only(self):
        now=datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
        r={**self.receipt,"capture_rome_date":now}
        with patch.object(module,"github_json",side_effect=[
            (404,{"message":"Not Found"}),
            (201,{"content":{"sha":"created"}})
        ]) as api:
            result=module.publish_once(r,"fake-token","someowner/somerepo",now)
        self.assertEqual(result["status"],"CREATED_IMMUTABLE")
        self.assertTrue(result["wrote"])
        self.assertEqual(api.call_args_list[1].args[0],"PUT")
        self.assertNotIn("sha",api.call_args_list[1].args[3],
                         "No SHA in PUT: creation only, no overwrite")

    def test_no_backdated_publication(self):
        past={**self.receipt,"capture_rome_date":"2020-01-01"}
        today=datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
        with self.assertRaises(ValueError):
            module.publish_once(past,"token","owner/repo",today)


if __name__=="__main__":
    unittest.main()
