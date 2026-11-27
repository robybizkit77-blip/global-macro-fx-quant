#!/usr/bin/env python3
"""G8 archive chart source: coverage, expiry identity and no silent history fiction."""
from __future__ import annotations
import copy
import json
import unittest
from datetime import date, timedelta
from pathlib import Path

from build_next_g8_pricing_history_v1 import (
    CCYS, TENORS, ROOT, build, read_jsonl, SNAP, OFFICIAL, QUOTES, CONFLICTS, NZD, DEST, NZD_ARCHIVE, nzd_monthly_reference, usd_roll_momentum
)


class TestG8History(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=json.loads(SNAP.read_text(encoding="utf-8"))
        cls.archive=read_jsonl(OFFICIAL)
        cls.quotes=read_jsonl(QUOTES)
        cls.conflicts=read_jsonl(CONFLICTS)
        cls.nzd=json.loads(NZD.read_text(encoding="utf-8"))
        cls.nzd_archive=read_jsonl(NZD_ARCHIVE)
        cls.actual=build(cls.snapshot,cls.archive,cls.quotes,cls.conflicts,cls.nzd,cls.nzd_archive)

    def test_source_parity_and_complete_g8_shell(self):
        self.assertEqual(self.actual,json.loads(DEST.read_text(encoding="utf-8")))
        self.assertEqual(tuple(self.actual["currencies"]),CCYS)
        self.assertEqual(self.actual["schema"],"GMFQ_NEXT_G8_PRICING_HISTORY_V1")
        self.assertFalse(self.actual["official_ois_created"])
        self.assertFalse(self.actual["eligible_for_fx_engine"])
        self.assertFalse(self.actual["date_gaps_interpolated"])
        for c,row in self.actual["currencies"].items():
            self.assertEqual(tuple(row["tenors"]),TENORS)
            self.assertTrue(row["quality"])
            self.assertTrue(row["source"])
            self.assertGreater(sum(len(row["tenors"][t]) for t in TENORS),0)
            for t,points in row["tenors"].items():
                self.assertEqual([p["date"] for p in points],
                                 sorted({p["date"] for p in points}))
                self.assertTrue(all(p["date"]<=self.actual["as_of"] for p in points))
                if c in {"USD","EUR","CHF"}:
                    self.assertTrue(all(p["contract"] and
                                        p["source_class"]=="SECONDARY_SAME_CONTRACT"
                                        for p in points))
                if c in {"GBP","JPY","AUD","CAD"}:
                    self.assertTrue(all(p["source_class"]=="OFFICIAL_TENOR" and
                                        not p["derived"] for p in points))
                if c=="NZD":
                    self.assertTrue(all(p["source_class"].startswith("BANK_BILL_PROXY")
                                        for p in points))

    def test_rebuild_without_new_bars_keeps_last_observation_date(self):
        snapshot = copy.deepcopy(self.snapshot)
        build_day = date.fromisoformat(snapshot["snapshot_built_from_repo_date"])
        snapshot["snapshot_built_from_repo_date"] = (build_day + timedelta(days=1)).isoformat()
        rebuilt = build(snapshot, self.archive, self.quotes, self.conflicts, self.nzd, self.nzd_archive)
        latest = max(point["date"] for row in rebuilt["currencies"].values()
                     for points in row["tenors"].values() for point in points
                     if not point["derived"])
        self.assertEqual(rebuilt["as_of"], latest)
        self.assertEqual(rebuilt, self.actual)

    def test_quarantined_conflicts_cannot_enter_history(self):
        excluded={tuple(e["key"]) for e in self.conflicts
                  if e.get("status")=="UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT"}
        for c in ("USD","EUR","CHF"):
            for tenor in TENORS:
                for p in self.actual["currencies"][c]["tenors"][tenor]:
                    self.assertNotIn((c,p["contract"],p["date"]),excluded)
        self.assertEqual(self.actual["excluded_conflicted_contract_days"],len(excluded))

    def test_cad_invalid_curve_never_reenters_history(self):
        quarantine=ROOT/"validation/cb_pricing/history/quarantine/CAD_CORRA_INVALID_2026-11-26.jsonl"
        bad=read_jsonl(quarantine)
        self.assertEqual(len(bad),1)
        self.assertEqual(bad[0]["horizons"]["6m"]["rate"],-762)
        rebuilt=build(self.snapshot,self.archive+bad,self.quotes,self.conflicts,self.nzd,self.nzd_archive)
        self.assertEqual(rebuilt,self.actual)
        self.assertTrue(all(-5<=p["rate"]<=25 for points in rebuilt["currencies"]["CAD"]["tenors"].values() for p in points))

    def test_secondary_not_overtaken_by_forged_future_wrong_100_price(self):
        bad=copy.deepcopy(self.quotes[-1])
        bad["observation_date"]="2999-12-25"
        bad["contract"]="FORGED_FUTURE"
        bad["futures_price"]=88
        bad["implied_rate"]=12
        forged=build(self.snapshot,self.archive,self.quotes+[bad],self.conflicts,self.nzd,self.nzd_archive)
        self.assertEqual(forged,self.actual)

        bad2=copy.deepcopy(self.quotes[-1])
        bad2["observation_date"]="2026-11-01"
        bad2["contract"]="FORGED_PRICE"
        bad2["futures_price"]=98
        bad2["implied_rate"]=5
        forged2=build(self.snapshot,self.archive,self.quotes+[bad2],self.conflicts,self.nzd,self.nzd_archive)
        self.assertEqual(forged2,self.actual)

    def test_nzd_reference_is_derived_and_never_observed(self):
        nz=self.actual["currencies"]["NZD"]
        self.assertEqual(nz["kind"],"PROXY FUTURES")
        self.assertGreaterEqual(nz["observed_dates"],5)
        for tenor in TENORS:
            self.assertGreaterEqual(sum(not p["derived"] for p in nz["tenors"][tenor]),5)
            self.assertTrue(all(p.get("expiration") for p in nz["tenors"][tenor] if not p["derived"]))
            self.assertTrue(all("PROXY" in p["source_class"] for p in nz["tenors"][tenor]))

    def test_nzd_conflicting_observations_are_quarantined(self):
        rec=copy.deepcopy(self.nzd_archive[0])
        h=rec["feed"]["horizons"]["6m"]
        h["settlement_price"]=round(h["settlement_price"]+.01,4)
        h["implied_bank_bill_rate"]=round(100-h["settlement_price"],4)
        result=build(self.snapshot,self.archive,self.quotes,self.conflicts,self.nzd,self.nzd_archive+[rec])
        self.assertGreaterEqual(result["excluded_nzd_conflicted_contract_days"],1)
        self.assertNotIn(rec["feed"]["as_of"],[x["date"] for x in result["currencies"]["NZD"]["tenors"]["6m"]])

    def test_nzd_exact_monthly_reference(self):
        feed=copy.deepcopy(next(x["feed"] for x in self.nzd_archive if x["feed"]["as_of"]=="2026-11-23"))
        d="2026-11-23"
        h=feed["horizons"]["6m"]
        self.assertEqual((feed["as_of"],h["expiry_label"],h["implied_bank_bill_rate"]),(d,"Jun 2027",3.7))
        feed["monthly_reference"]={
            "schema":"GMFQ_NZD_ASX_EXACT_20_WEEKDAY_REFERENCE_V1","status":"REFERENCE_PARSED",
            "official_ois_created":False,"fx_engine_effect":"NONE","as_of":d,
            "reference_date":"2026-10-26","current_source_url":feed["source_url"],
            "reference_url":"https://www.asx.com.au/data/futures/reports/EODWebMarketSummary261026ZFT.htm",
            "decoded_source_sha256":"88e6c88b112435f8c46af6bdc25d07e4822f30bed0e5c56de31ef2e2d5d53c1b",
            "horizons":{"6m":{"contract":"Jun 2027","expiration":"2027-06-16",
              "reference_price":95.94,"reference_implied_pct":4.06,"current_price":96.3,
              "current_implied_pct":3.7,"change_bp":-36,
              "basis":"EXACT_LISTED_ASX_BANK_BILL_CONTRACT_NOT_OIS"}}}
        observed={"6m":{d:{"contract":"Jun 2027","expiration":"2027-06-16","rate":3.7}}}
        result=nzd_monthly_reference(feed,observed,{})
        self.assertEqual(result["change_bp"],-36)
        self.assertIsNone(nzd_monthly_reference(feed,observed,{("2026-10-26","Jun 2027","2027-06-16"):{95.95}}))
        self.assertIsNone(nzd_monthly_reference(feed,{},{}))
        bad=copy.deepcopy(feed)
        bad["monthly_reference"]["horizons"]["6m"]["change_bp"]=-99
        self.assertIsNone(nzd_monthly_reference(bad,observed,{}))
        bad=copy.deepcopy(feed)
        bad["monthly_reference"]["reference_date"]="2026-10-27"
        self.assertIsNone(nzd_monthly_reference(bad,observed,{}))

    def test_usd_single_roll_estimate(self):
        points=[{"date":"2026-10-27","contract":"APR","rate":4.38},
                {"date":"2026-11-17","contract":"APR","rate":4.47},
                {"date":"2026-11-19","contract":"MAY","rate":4.58},
                {"date":"2026-11-24","contract":"MAY","rate":4.475}]
        a={"contract":"APR","implied_rate":4.495,"expiration":"2027-05-03","first_seen_at_utc":"2026-11-18T21:50:30Z"}
        b={"contract":"MAY","implied_rate":4.55,"expiration":"2027-06-01","first_seen_at_utc":"2026-11-19T02:38:45Z"}
        q={"2026-11-18":[a,b]}
        out=usd_roll_momentum(points,q)
        self.assertEqual(out["20"]["change_bp"],4.0)
        self.assertEqual(out["5"]["change_bp"],-5.0)
        self.assertEqual(out["20"]["basis"],"ESTIMATED_SINGLE_ROLL_SAME_SOURCE_NOT_SYNCHRONIZED")
        self.assertFalse(out["20"]["official_ois_created"])
        self.assertEqual(usd_roll_momentum(points,{}),{})
        self.assertEqual(usd_roll_momentum(points,{"2026-11-18":[a]}),{})
        self.assertEqual(usd_roll_momentum(points,{"2026-11-18":[a,b,dict(b)]}),{})
        self.assertEqual(usd_roll_momentum(points,{"2026-11-18":[a,b],"2026-11-20":[a]}),{})
        late=dict(b,first_seen_at_utc="2026-11-20T02:38:45Z")
        self.assertEqual(usd_roll_momentum(points,{"2026-11-18":[a,late]}),{})

    def test_official_withheld_never_launders_stale_rows(self):
        archive=copy.deepcopy(self.archive)
        record=copy.deepcopy(next(x for x in archive if x.get("currency")=="GBP"))
        record["captured_at_utc"]="2026-11-13T23:00:00Z"
        record["source_as_of"]="2026-11-13"
        record["operational_status"]="WITHHELD"
        record["horizons"]={t:{"rate":99} for t in TENORS}
        data=build(self.snapshot,archive+[record],self.quotes,self.conflicts,self.nzd,self.nzd_archive)
        self.assertEqual(data,self.actual)


if __name__ == "__main__":
    unittest.main(verbosity=2)
