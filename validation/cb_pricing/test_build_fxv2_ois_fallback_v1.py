"""Strict tests for FX Quant V2 fallback auto-refresh, with no network or writes."""
import copy
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import json
from pathlib import Path
import unittest

from validation.cb_pricing.build_fxv2_ois_fallback_v1 import (
    ROOT, SNAPSHOT, OPERATIONAL, ESTIMATED, NZD_PROXY, G8, HORIZONS,
    candidate, rebuild
)


class FallbackPricingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.op = json.loads(OPERATIONAL.read_text(encoding="utf-8"))
        cls.est = json.loads(ESTIMATED.read_text(encoding="utf-8"))
        cls.nzd = json.loads(NZD_PROXY.read_text(encoding="utf-8"))
        cls.today = datetime.now(ZoneInfo('Europe/Rome')).date()

    def test_all_eight_and_24_dated_instruments_remain_research_only(self):
        result, changed = rebuild(self.snap,self.op,self.est,self.nzd,today=self.today)
        self.assertEqual(set(result["currencies"]), set(G8))
        self.assertFalse(result["eligible_for_fx_engine"])
        self.assertTrue(result["ui_only"])
        self.assertEqual(sum(len(v["horizons"]) for v in result["currencies"].values()),24)
        self.assertEqual(result["currencies"]["GBP"]["kind"],"OIS")
        self.assertEqual(result["currencies"]["NZD"]["kind"],"PROXY FUTURES")
        self.assertTrue(isinstance(result["currencies"]["NZD"]["horizons"]["6m"]["rate"], (int,float)))
        self.assertLessEqual(result["currencies"]["NZD"]["horizons"]["6m"]["as_of"],
                             self.today.isoformat())
        self.assertEqual(result["currencies"]["CHF"]["kind"],"FUTURES SECONDARI")
        self.assertEqual(result["currencies"]["USD"]["kind"],"FUTURES SECONDARI")
        self.assertIsInstance(changed, list)
        self.assertTrue(set(changed).issubset(set(G8)))

    def test_per_tenor_new_quote_has_its_real_date_not_currency_date(self):
        result,_=rebuild(self.snap,self.op,self.est,self.nzd,today=self.today)
        # Compare each actual quote timestamp independently. These feeds can
        # advance during PR testing: do NOT hardcode today's tenor levels.
        for currency in ("USD","CHF","EUR"):
            incoming=candidate(currency,self.op,self.est,self.nzd)
            row=result["currencies"][currency]
            old=self.snap["currencies"][currency]
            for h in HORIZONS:
                z=incoming["horizons"][h]
                expected=max(z["as_of"],old["horizons"][h]["as_of"])
                self.assertEqual(row["horizons"][h]["as_of"],expected)
                if z["as_of"]>=old["horizons"][h]["as_of"]:
                    self.assertEqual(row["horizons"][h]["rate"],z["rate"])
            self.assertEqual(row["as_of"],max(x["as_of"] for x in row["horizons"].values()))

    def test_stale_feed_cannot_replace_newer_snapshot_or_advance_quote_clock(self):
        stale=copy.deepcopy(self.est)
        stale["currencies"]["USD"]["as_of"]="2026-10-01"
        for h in HORIZONS:
            z=stale["currencies"]["USD"]["horizons"][h]
            z["quote_as_of"]="2026-10-01"
            z["rate"]=10.0
        result,_=rebuild(self.snap,self.op,stale,self.nzd,today=self.today)
        self.assertEqual(result["currencies"]["USD"]["horizons"]["3m"]["rate"],
                         self.snap["currencies"]["USD"]["horizons"]["3m"]["rate"])
        self.assertEqual(result["currencies"]["USD"]["horizons"]["6m"]["as_of"],
                         self.snap["currencies"]["USD"]["horizons"]["6m"]["as_of"])

    def test_future_quote_rejected_instead_of_fabricating_freshness(self):
        bad=copy.deepcopy(self.est)
        bad["currencies"]["USD"]["horizons"]["3m"]["quote_as_of"]=(self.today+timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError,"future quote"):
            rebuild(self.snap,self.op,bad,self.nzd,today=self.today)

    def test_proxy_cannot_be_misrepresented_as_official_ois(self):
        invalid=copy.deepcopy(self.nzd)
        invalid["governance"]["substitutes_for_ois_level"]=True
        with self.assertRaisesRegex(ValueError,"proxy may never become"):
            rebuild(self.snap,self.op,self.est,invalid,today=self.today)

    def test_benchmark_family_change_requires_separate_review(self):
        bad=copy.deepcopy(self.snap)
        bad["currencies"]["USD"]["kind"]="OIS"
        with self.assertRaisesRegex(ValueError,"changed benchmark family"):
            rebuild(bad,self.op,self.est,self.nzd,today=self.today)

    def test_second_build_is_idempotent_no_fake_new_repo_date(self):
        first,_=rebuild(self.snap,self.op,self.est,self.nzd,today=self.today)
        second,changed=rebuild(first,self.op,self.est,self.nzd,today=self.today+timedelta(days=1))
        self.assertEqual(changed,[])
        self.assertEqual(first,second)

    def test_no_source_or_canonical_runtime_writes(self):
        old={str(p):p.read_bytes() for p in [SNAPSHOT,OPERATIONAL,ESTIMATED,NZD_PROXY]}
        rebuild(self.snap,self.op,self.est,self.nzd,today=self.today)
        self.assertEqual(old,{str(p):p.read_bytes() for p in [SNAPSHOT,OPERATIONAL,ESTIMATED,NZD_PROXY]})

    def test_existing_release_wires_producer_to_fxv2_publication(self):
        producer=(ROOT/".github/workflows/ois-g8-history-persistent-daily-v1.yml").read_text()
        publisher=(ROOT/".github/workflows/publish-fx-quant-v2.yml").read_text()
        self.assertIn("build_fxv2_ois_fallback_v1.py",producer)
        self.assertIn("site/fx-quant-v2/ois-pricing-snapshot.json",producer)
        self.assertIn("OIS G8 History Persistent Daily V1",publisher)
        self.assertEqual(producer.count("cron: '15 6 * * 1-5'"),1)
        self.assertEqual(producer.count("cron: '15 7 * * 1-5'"),1)
        self.assertIn("gh-pages",publisher)


if __name__ == "__main__":
    unittest.main()
