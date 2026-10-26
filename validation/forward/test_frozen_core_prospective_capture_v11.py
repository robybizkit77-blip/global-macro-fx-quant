"""Prospective only: frozen model, no intraday clock fabrication, immutable days."""
from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

HERE=pathlib.Path(__file__).resolve().parent

def load(name):
    sp=importlib.util.spec_from_file_location(name,HERE/(name+".py"))
    mod=importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    return mod

gate=load("admit_frozen_core_prospective_capture_v1")
logger=load("log_core_decision_v1")


def minimal():
    fx={
        "status":"CURRENT_OFFICIAL_HISTORY",
        "source_url":"https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml",
        "last_as_of":"2026-10-26",
    }
    pairs={f"P{i:02}":{} for i in range(28)}
    setup={"pair_count":28,"price_asof":"2026-10-26","pairs":pairs}
    d={"asOf":"2026-09-25",
       "pairs":[{"pair":f"{i:02}/XX"} for i in range(28)],
       "pairStates":{f"{i:02}/XX":{} for i in range(28)}}
    return fx,setup,d

def local(hour):
    return dt.datetime(2026,10,26,hour,31,tzinfo=gate.ROME)

class ProspectiveAdmission(unittest.TestCase):
    def test_after_close_all_28_and_official_current_date(self):
        fx,setup,d=minimal()
        result=gate.assess(local(19),fx,setup,d)
        self.assertEqual(result["status"],"ADMITTED_PROSPECTIVE_BASELINE_OBSERVATION")
        self.assertFalse(result["new_core_signal"])
        self.assertFalse(result["backfilled"])
        self.assertFalse(result["core_recomputed"])

    def test_older_price_does_not_get_forward_snapshot(self):
        fx,setup,d=minimal()
        fx["last_as_of"]="2026-10-23"
        self.assertIn("ECB_CURRENT_DAY_FIXING_NOT_PRESENT",
            gate.assess(local(19),fx,setup,d)["checks"])

    def test_mixed_current_ecb_and_old_setup_refused(self):
        fx,setup,d=minimal()
        setup["price_asof"]="2026-10-23"
        self.assertIn("PAIR_SETUP_CURRENT_DAY_28_PAIR_PRICE_NOT_PRESENT",
            gate.assess(local(19),fx,setup,d)["checks"])

    def test_session_cannot_capture_before_1900(self):
        fx,setup,d=minimal()
        self.assertEqual(gate.assess(local(18),fx,setup,d)["status"],"BLOCKED_NO_CAPTURE")

    def test_weekend_cannot_capture(self):
        fx,setup,d=minimal()
        self.assertIn("NOT_ROME_BUSINESS_WEEKDAY",
            gate.assess(dt.datetime(2026,10,31,19,30,tzinfo=gate.ROME),fx,setup,d)["checks"])

    def test_future_core_baseline_cannot_be_loaded(self):
        fx,setup,d=minimal()
        d["asOf"]="2026-10-27"
        self.assertIn("CORE_BASELINE_NOT_HISTORICALLY_PREEXISTING",
            gate.assess(local(19),fx,setup,d)["checks"])

    def test_no_partial_pair_setup(self):
        fx,setup,d=minimal()
        setup["pairs"].pop("P27")
        self.assertIn("PAIR_SETUP_CURRENT_DAY_28_PAIR_PRICE_NOT_PRESENT",
            gate.assess(local(19),fx,setup,d)["checks"])

    def test_unaware_capture_clock_rejected(self):
        fx,setup,d=minimal()
        with self.assertRaisesRegex(ValueError,"timezone"):
            gate.assess(dt.datetime(2026,10,26,19,30),fx,setup,d)

    def test_schema_v11_inputs_and_baseline_are_tied_to_original_source(self):
        rows=logger.make_rows(logger.parse_cutoff("2026-10-26T19:31:00Z"),"forward-20261026")
        self.assertEqual(len(rows),28)
        self.assertTrue(all(x["schema_version"].endswith("V1.1.0") for x in rows))
        self.assertTrue(all(x["capture_class"]=="FROZEN_CORE_BASELINE_OBSERVATION" for x in rows))
        self.assertTrue(all(x["core_baseline_as_of"]=="2026-09-25" for x in rows))
        self.assertTrue(all(x["core_recomputed_at_capture"] is False for x in rows))
        self.assertTrue(all(len(x["inputs"])==8 for x in rows))
        self.assertTrue(all(x["inputs"]["macro"]["state"]=="WITHHELD" for x in rows))
        self.assertTrue(all(x["inputs"]["macro"]["value"] is None for x in rows))
        self.assertTrue(all(x["snapshot_sha256"]==logger.digest(
            {k:v for k,v in x.items() if k!="snapshot_sha256"}) for x in rows))

    def test_same_day_second_run_does_not_duplicate_even_if_clock_changes(self):
        rows=logger.make_rows(logger.parse_cutoff("2026-10-26T19:31:00Z"),"forward-20261026")
        newer=logger.make_rows(logger.parse_cutoff("2026-10-26T20:32:00Z"),"forward-retry")
        with tempfile.TemporaryDirectory() as tmp:
            old=logger.DECISIONS
            try:
                logger.DECISIONS=pathlib.Path(tmp)/"ledger.jsonl"
                a=logger.append_rows(rows,False)
                before=logger.DECISIONS.read_bytes()
                b=logger.append_rows(newer,False)
                self.assertEqual(a["written"],28)
                self.assertEqual(b["written"],0)
                self.assertTrue(b["same_day_observation_already_preserved"])
                self.assertEqual(logger.DECISIONS.read_bytes(),before)
            finally:
                logger.DECISIONS=old

    def test_partial_daily_archive_refuses_replay_or_repair(self):
        rows=logger.make_rows(logger.parse_cutoff("2026-10-26T19:31:00Z"),"fwd-20261026")
        with tempfile.TemporaryDirectory() as tmp:
            old=logger.DECISIONS
            try:
                logger.DECISIONS=pathlib.Path(tmp)/"ledger.jsonl"
                logger.DECISIONS.write_bytes(logger.canonical(rows[0]))
                with self.assertRaisesRegex(ValueError,"partial existing daily observation"):
                    logger.append_rows(rows,False)
            finally:
                logger.DECISIONS=old


if __name__=="__main__":
    unittest.main()
