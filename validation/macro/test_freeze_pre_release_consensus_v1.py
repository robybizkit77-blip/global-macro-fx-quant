"""Freeze issuer-matched forecast only before scheduled news, never overwrite."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path

from validation.macro.freeze_pre_release_consensus_v1 import (
    CONSENSUS, LEDGER, SCHEMA, SEED, freeze, parse_forecast,
    read_existing, run, validate_existing
)

T0="2026-10-28T08:35:00Z"

class ConsensusFreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=json.loads(SEED.read_text(encoding="utf-8"))
        cls.consensus=json.loads(CONSENSUS.read_text(encoding="utf-8"))

    def freeze_at(self,at=T0,seed=None,consensus=None,old=None):
        return freeze(seed or self.seed,consensus or self.consensus,
                      [] if old is None else old,at)

    def test_real_october_30_usd_cad_forecasts_freeze_before_release(self):
        records,receipt=self.freeze_at()
        self.assertEqual(len(records),2)
        self.assertEqual(receipt["new_forecasts_frozen"],2)
        self.assertEqual({r["currency"] for r in records},{"USD","CAD"})
        self.assertEqual({r["official_scheduled_release_utc"] for r in records},
                         {"2026-10-30T12:30:00Z"})
        by={r["currency"]:r for r in records}
        self.assertEqual(by["USD"]["consensus"],"0.8%")
        self.assertEqual(by["CAD"]["consensus"],"0.2%")
        self.assertEqual(by["USD"]["provider_event"],"Employment Cost Index q/q")
        self.assertEqual(by["CAD"]["provider_event"],"GDP m/m")
        self.assertTrue(all(r["schema"]==SCHEMA for r in records))
        self.assertTrue(all(r["provider_is_official"] is False and
                            r["actual"] is None and r["surprise"] is None and
                            r["FX_signal"] is None and
                            r["eligible_for_live_model"] is False and
                            r["publisher_first_public_delivery_verified"] is False
                            for r in records))
        validate_existing(records)

    def test_first_capture_never_overwritten_by_later_forecast_change(self):
        original,_=self.freeze_at()
        changed=copy.deepcopy(self.consensus)
        changed["generated_at_utc"]="2026-10-29T06:00:00Z"
        changed["events"][0]["consensus"]="0.9%"
        new,receipt=self.freeze_at("2026-10-29T08:35:00Z",consensus=changed,old=original)
        self.assertEqual(new,original)
        self.assertEqual(receipt["new_forecasts_frozen"],0)
        self.assertEqual(receipt["skipped"]["ALREADY_FROZEN_KEEP_FIRST_OBSERVATION"],2)

    def test_no_backdating_or_post_announcement_rewrite(self):
        records,receipt=self.freeze_at("2026-10-30T12:30:00Z")
        self.assertEqual(records,[])
        self.assertEqual(receipt["new_forecasts_frozen"],0)
        self.assertEqual(receipt["skipped"]["NOT_CAPTURED_BEFORE_ISSUER_SCHEDULE"],2)
        late_source=copy.deepcopy(self.consensus)
        late_source["generated_at_utc"]="2026-10-30T12:35:00Z"
        records,_=self.freeze_at("2026-10-30T12:36:00Z",consensus=late_source)
        self.assertEqual(records,[])
        bad_future=copy.deepcopy(self.consensus)
        bad_future["generated_at_utc"]="2026-10-29T11:00:00Z"
        with self.assertRaises(ValueError):
            self.freeze_at(consensus=bad_future)

    def test_event_series_and_provider_unit_fail_closed(self):
        base=self.consensus
        variants=[
            {"provider_event":"Import Prices q/q"},
            {"status":"PREVIOUS_ONLY"},
            {"confidence_grade":"C"},
            {"official_date_overridden":True},
            {"date_match_gap_days":1},
            {"consensus":None},
            {"consensus":"0.8"},  # missing unit
            {"consensus":"0.8 pts"}, # not percent
            {"actual_ignored_for_pre_release_consensus":False},
        ]
        for mutation in variants:
            with self.subTest(mutation=mutation):
                d=copy.deepcopy(base);d["events"][0].update(mutation)
                records,receipt=self.freeze_at(consensus=d)
                self.assertEqual(len(records),1)
                self.assertEqual(records[0]["currency"],"CAD")
        seed=copy.deepcopy(self.seed)
        usd=next(e for e in seed["events"] if e["ccy"]=="USD"
                 and e["title"]=="Employment Cost Index")
        usd["time_local"]=None
        records,_=self.freeze_at(seed=seed)
        self.assertEqual([r["currency"] for r in records],["CAD"])

    def test_immutable_chain_rejects_edits_reordering_or_false_actual(self):
        records,_=self.freeze_at()
        for edit in (
            lambda a:a[0].update(consensus="0.1%"),
            lambda a:a[0].update(actual="0.9%"),
            lambda a:a[1].update(previous_record_sha256="GENESIS"),
            lambda a:a[0].update(captured_at_utc="2026-10-30T13:00:00Z"),
            lambda a:a.reverse(),
            lambda a:a.append(copy.deepcopy(a[0]))
        ):
            altered=copy.deepcopy(records);edit(altered)
            with self.assertRaises(ValueError):validate_existing(altered)

    def test_run_adds_exactly_once_and_mutates_no_other_files(self):
        with tempfile.TemporaryDirectory() as td:
            ledger=Path(td)/"ledger.jsonl"
            before=(SEED.read_bytes(),CONSENSUS.read_bytes())
            first=run(SEED,CONSENSUS,ledger,captured_at=T0)
            self.assertEqual(first["new_forecasts_frozen"],2)
            bytes_first=ledger.read_bytes()
            second=run(SEED,CONSENSUS,ledger,captured_at="2026-10-28T09:00:00Z")
            self.assertEqual(second["new_forecasts_frozen"],0)
            self.assertEqual(bytes_first,ledger.read_bytes())
            self.assertEqual(len(read_existing(ledger)),2)
            self.assertEqual(before,(SEED.read_bytes(),CONSENSUS.read_bytes()))
        self.assertFalse(LEDGER.exists() and LEDGER.stat().st_size>1 and
                         any(r.get("FX_signal") for r in read_existing(LEDGER)))

    def test_number_parser_no_undocumented_unit_conversions(self):
        self.assertAlmostEqual(parse_forecast("+0.8%"),0.8)
        self.assertAlmostEqual(parse_forecast("-0.2%"),-0.2)
        for value in (None,"","2 bp","3.3",float("nan"),"NaN%"):
            with self.assertRaises(ValueError):parse_forecast(value)


if __name__=="__main__":unittest.main()
