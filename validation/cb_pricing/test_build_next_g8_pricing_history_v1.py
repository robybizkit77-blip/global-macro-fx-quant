#!/usr/bin/env python3
"""G8 archive chart source: coverage, expiry identity and no silent history fiction."""
from __future__ import annotations
import copy
import json
import unittest
from pathlib import Path

from build_next_g8_pricing_history_v1 import (
    CCYS, TENORS, ROOT, build, read_jsonl, SNAP, OFFICIAL, QUOTES, CONFLICTS, NZD, DEST
)


class TestG8History(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=json.loads(SNAP.read_text(encoding="utf-8"))
        cls.archive=read_jsonl(OFFICIAL)
        cls.quotes=read_jsonl(QUOTES)
        cls.conflicts=read_jsonl(CONFLICTS)
        cls.nzd=json.loads(NZD.read_text(encoding="utf-8"))
        cls.actual=build(cls.snapshot,cls.archive,cls.quotes,cls.conflicts,cls.nzd)

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

    def test_quarantined_conflicts_cannot_enter_history(self):
        excluded={tuple(e["key"]) for e in self.conflicts
                  if e.get("status")=="UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT"}
        for c in ("USD","EUR","CHF"):
            for tenor in TENORS:
                for p in self.actual["currencies"][c]["tenors"][tenor]:
                    self.assertNotIn((c,p["contract"],p["date"]),excluded)
        self.assertEqual(self.actual["excluded_conflicted_contract_days"],len(excluded))

    def test_secondary_not_overtaken_by_forged_future_wrong_100_price(self):
        bad=copy.deepcopy(self.quotes[-1])
        bad["observation_date"]="2999-12-25"
        bad["contract"]="FORGED_FUTURE"
        bad["futures_price"]=88
        bad["implied_rate"]=12
        forged=build(self.snapshot,self.archive,self.quotes+[bad],self.conflicts,self.nzd)
        self.assertEqual(forged,self.actual)

        bad2=copy.deepcopy(self.quotes[-1])
        bad2["observation_date"]="2026-11-01"
        bad2["contract"]="FORGED_PRICE"
        bad2["futures_price"]=98
        bad2["implied_rate"]=5
        forged2=build(self.snapshot,self.archive,self.quotes+[bad2],self.conflicts,self.nzd)
        self.assertEqual(forged2,self.actual)

    def test_nzd_reference_is_derived_and_never_observed(self):
        nz=self.actual["currencies"]["NZD"]
        self.assertEqual(nz["kind"],"PROXY FUTURES")
        self.assertGreater(nz["derived_reference_points"],0)
        self.assertEqual(nz["observed_dates"],1)
        for tenor in TENORS:
            self.assertEqual(sum(not p["derived"] for p in nz["tenors"][tenor]),1)
            self.assertTrue(all("PROXY" in p["source_class"] for p in nz["tenors"][tenor]))

    def test_official_withheld_never_launders_stale_rows(self):
        archive=copy.deepcopy(self.archive)
        record=copy.deepcopy(next(x for x in archive if x.get("currency")=="GBP"))
        record["captured_at_utc"]="2026-11-13T23:00:00Z"
        record["source_as_of"]="2026-11-13"
        record["operational_status"]="WITHHELD"
        record["horizons"]={t:{"rate":99} for t in TENORS}
        data=build(self.snapshot,archive+[record],self.quotes,self.conflicts,self.nzd)
        self.assertEqual(data,self.actual)


if __name__ == "__main__":
    unittest.main(verbosity=2)
