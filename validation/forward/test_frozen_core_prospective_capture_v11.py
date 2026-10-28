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
    day = "2026-10-26"
    quote = {ccy: 1.1 + i/10 for i, ccy in enumerate(gate.G8)}
    quote["EUR"] = 1.0
    ecb_row = {"Date": day, **quote}
    fx = {
        "status": "CURRENT_OFFICIAL_HISTORY",
        "source_url": "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml",
        "last_as_of": day,
        "rows": [{"Date": "2026-10-23", **quote} for _ in range(20)] + [ecb_row],
        "row_count": 21,
    }
    canonical = [
        a + "/" + b for i, a in enumerate(gate.G8) for b in gate.G8[i + 1:]
    ]
    pairs = {p.replace("/", ""): {"canonical_pair": p} for p in canonical}
    setup = {
        "status": "CURRENT_CANONICAL_ENGINE",
        "pair_count": 28,
        "price_asof": day,
        "macro_baseline_asof": "2026-09-25",
        "pairs": pairs,
        "price_audit": {
            "status": "PASS", "as_of": day, "overlay_asof": day,
            "history_asof": day, "pair_count": 28,
            "complete_pair_count": 28, "returns_complete": True,
            "no_lookahead": True,
        },
    }
    d = {
        "asOf": "2026-09-25",
        "pairs": [{"pair": p} for p in canonical],
        "pairStates": {p: {} for p in canonical},
    }
    return fx, setup, d

def local(hour):
    return dt.datetime(2026,10,26,hour,31,tzinfo=gate.ROME)

class ProspectiveAdmission(unittest.TestCase):
    def test_primary_backup_and_unmatched_utc_crons_across_dst(self):
        # 19:30 + 20:30 Rome on CET and CEST; same-day source gate stays.
        self.assertEqual(gate.schedule_attempt(
            dt.datetime(2026,10,26,19,31,tzinfo=gate.ROME),
            "schedule","30 18 * * 1-5"),"PRIMARY_1930_ROME")
        self.assertEqual(gate.schedule_attempt(
            dt.datetime(2026,10,26,20,31,tzinfo=gate.ROME),
            "schedule","30 19 * * 1-5"),"FALLBACK_2030_ROME")
        self.assertEqual(gate.schedule_attempt(
            dt.datetime(2026,10,23,19,31,tzinfo=gate.ROME),
            "schedule","30 17 * * 1-5"),"PRIMARY_1930_ROME")
        self.assertEqual(gate.schedule_attempt(
            dt.datetime(2026,10,23,20,31,tzinfo=gate.ROME),
            "schedule","30 18 * * 1-5"),"FALLBACK_2030_ROME")
        self.assertEqual(gate.schedule_attempt(
            dt.datetime(2026,10,26,18,31,tzinfo=gate.ROME),
            "schedule","30 17 * * 1-5"),"SKIPPED_DUPLICATE_DST_UTC_SLOT")
        self.assertEqual(gate.schedule_attempt(
            dt.datetime(2026,10,23,21,31,tzinfo=gate.ROME),
            "schedule","30 19 * * 1-5"),"SKIPPED_DUPLICATE_DST_UTC_SLOT")
        self.assertEqual(gate.schedule_attempt(
            dt.datetime(2026,10,26,20,31,tzinfo=gate.ROME),
            "workflow_dispatch",""),"MANUAL_ATTEMPT")
        self.assertEqual(gate.schedule_attempt(
            dt.datetime(2026,10,26,21,31,tzinfo=gate.ROME),
            "workflow_run",""),"AFTER_CANONICAL_PAIR_HANDOFF_REAL_TIME_RETRY")
        with self.assertRaisesRegex(ValueError,"aware"):
            gate.schedule_attempt(dt.datetime(2026,10,26,20,31),"schedule","30 19 * * 1-5")

    def test_pair_handoff_late_event_must_still_obey_official_same_day_gate(self):
        fx, setup, core = minimal()
        late = dt.datetime(2026,10,26,21,31,tzinfo=gate.ROME)
        allowed = gate.assess(late,fx,setup,core)
        self.assertEqual(allowed["status"],"ADMITTED_PROSPECTIVE_BASELINE_OBSERVATION")
        stale=copy.deepcopy(setup)
        stale["price_asof"]="2026-10-23"
        blocked=gate.assess(late,fx,stale,core)
        self.assertEqual(blocked["status"],"BLOCKED_NO_CAPTURE")
        self.assertIn("PAIR_SETUP_CURRENT_DAY_28_PAIR_PRICE_NOT_PRESENT",blocked["checks"])
        oldfx=copy.deepcopy(fx)
        oldfx["last_as_of"]="2026-10-23"
        blocked=gate.assess(late,oldfx,setup,core)
        self.assertIn("ECB_CURRENT_DAY_FIXING_NOT_PRESENT",blocked["checks"])
        # Source event alone cannot override the real Rome-hour safety check.
        earlier=dt.datetime(2026,10,26,18,31,tzinfo=gate.ROME)
        self.assertIn("NOT_AFTER_1900_ROME",gate.assess(earlier,fx,setup,core)["checks"])

    def test_existing_forward_workflow_event_recovery_has_no_new_cron_or_pr_capture(self):
        workflow=(gate.ROOT/".github/workflows/forward-frozen-core-prospective-daily-v1.yml"
                  ).read_text(encoding="utf-8")
        self.assertEqual(workflow.count("cron: '30 17 * * 1-5'"),1)
        self.assertEqual(workflow.count("cron: '30 18 * * 1-5'"),1)
        self.assertEqual(workflow.count("cron: '30 19 * * 1-5'"),1)
        self.assertIn("workflows: ['Pair Setup Operational View V1', 'Hourly Certified Alert Readiness V1']",workflow)
        self.assertIn("Gate existing hourly retries before expensive tests",workflow)
        self.assertIn("needs.test.outputs.eligible == 'true'",workflow)
        self.assertIn("types: [completed]",workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'",workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'",workflow)
        self.assertIn("github.event.workflow_run.event != 'pull_request'",workflow)
        self.assertIn("steps.admit.outputs.admitted == 'true'",workflow)
        self.assertIn("EXISTING_DATE_ALREADY_FROZEN_NO_OVERWRITE",workflow)
        self.assertIn("Certify V2 research capture separately after primary Core commit",workflow)
        # The canonical pair exporter does not itself depend on any forward
        # workflow, preventing an accidental workflow-run feedback loop.
        exporter=(gate.ROOT/".github/workflows/pair-setup-operational-view-v1.yml"
                  ).read_text(encoding="utf-8")
        self.assertNotIn("'Forward Frozen Core Prospective Daily V1'",exporter)

    def test_backup_does_not_replay_official_oct23_fixing(self):
        fx,setup,d=minimal()
        fx["last_as_of"]="2026-10-23"
        setup["price_asof"]="2026-10-23"
        result=gate.assess(dt.datetime(2026,10,26,20,31,tzinfo=gate.ROME),fx,setup,d)
        self.assertEqual(result["status"],"BLOCKED_NO_CAPTURE")
        self.assertIn("ECB_CURRENT_DAY_FIXING_NOT_PRESENT",result["checks"])

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
        setup["pairs"].pop(next(iter(setup["pairs"])))
        self.assertIn("PAIR_SETUP_CURRENT_DAY_28_PAIR_PRICE_NOT_PRESENT",
            gate.assess(local(19),fx,setup,d)["checks"])

    def test_complete_source_and_pair_integrity_required_before_admission(self):
        # A 28-record count is NOT proof of the correct 28 G8 orientations.
        fx, setup, core = minimal()
        self.assertTrue(gate.certified_pair_universe(setup, core))
        self.assertEqual(gate.assess(local(19), fx, setup, core)["checks"], [])

        altered = copy.deepcopy(setup)
        original = next(iter(altered["pairs"]))
        altered["pairs"]["ZZZZZZ"] = altered["pairs"].pop(original)
        self.assertIn("PAIR_CORE_G8_ORIENTATION_MISMATCH",
                      gate.assess(local(19), fx, altered, core)["checks"])

        altered = copy.deepcopy(setup)
        original = next(iter(altered["pairs"]))
        altered["pairs"][original]["canonical_pair"] = "EUR/EUR"
        self.assertIn("PAIR_CORE_G8_ORIENTATION_MISMATCH",
                      gate.assess(local(19), fx, altered, core)["checks"])

        altered = copy.deepcopy(setup)
        altered["price_audit"]["status"] = "FAIL"
        self.assertIn("PAIR_PRICE_AUDIT_NOT_CERTIFIED",
                      gate.assess(local(19), fx, altered, core)["checks"])

        altered = copy.deepcopy(setup)
        altered["price_audit"]["history_asof"] = "2026-10-23"
        self.assertIn("PAIR_PRICE_AUDIT_NOT_CERTIFIED",
                      gate.assess(local(19), fx, altered, core)["checks"])

        altered = copy.deepcopy(setup)
        altered["macro_baseline_asof"] = "2026-10-20"
        self.assertIn("PAIR_MACRO_BASELINE_MISMATCH",
                      gate.assess(local(19), fx, altered, core)["checks"])

        altered = copy.deepcopy(core)
        altered["pairs"][0]["pair"] = "EUR/EUR"
        self.assertIn("PAIR_CORE_G8_ORIENTATION_MISMATCH",
                      gate.assess(local(19), fx, setup, altered)["checks"])

    def test_ecb_date_label_does_not_certify_corrupt_last_row(self):
        fx, setup, core = minimal()
        fx["rows"][-1]["Date"] = "2026-10-23"
        self.assertIn("ECB_OFFICIAL_ROW_INTEGRITY_FAILED",
                      gate.assess(local(19), fx, setup, core)["checks"])
        fx, setup, core = minimal()
        fx["rows"][-1]["JPY"] = None
        self.assertIn("ECB_OFFICIAL_ROW_INTEGRITY_FAILED",
                      gate.assess(local(19), fx, setup, core)["checks"])
        fx, setup, core = minimal()
        fx["row_count"] = 999
        self.assertIn("ECB_OFFICIAL_ROW_INTEGRITY_FAILED",
                      gate.assess(local(19), fx, setup, core)["checks"])

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
        self.assertTrue(all(len(x["inputs"])==9 for x in rows))
        self.assertTrue(all(x["inputs"]["macro"]["state"]=="WITHHELD" for x in rows))
        self.assertTrue(all(x["inputs"]["macro"]["value"] is None for x in rows))
        self.assertTrue(all(x["t0_fx_reference"]["intra_day_traded_price"] is False for x in rows))
        self.assertTrue(all(x["t0_fx_reference"]["official_publication_instant_independently_verified"] is False for x in rows))
        self.assertTrue(all(x["inputs"]["ecb_reference"] == x["t0_fx_reference"] for x in rows))
        for row in rows:
            if row["t0_fx_reference"]["state"] == "OBSERVED_AT_CAPTURE":
                self.assertGreater(row["t0_fx_reference"]["rate"], 0)
                self.assertEqual(row["t0_fx_reference"]["source_date"], "2026-10-26")
            else:
                self.assertIsNone(row["t0_fx_reference"]["rate"])

        self.assertTrue(all(x["snapshot_sha256"]==logger.digest(
            {k:v for k,v in x.items() if k!="snapshot_sha256"}) for x in rows))

    def test_prospective_hash_and_missing_inputs_block_before_append(self):
        rows=logger.make_rows(logger.parse_cutoff("2026-10-26T19:31:00Z"),"forward-20261026")
        logger.validate_prospective_batch(rows)
        changed=copy.deepcopy(rows)
        changed[0]["inputs"].pop("macro")
        changed[0]["snapshot_sha256"]=logger.digest(
            {k:v for k,v in changed[0].items() if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError,"MISSING_PIT_INPUTS"):
            logger.validate_prospective_batch(changed)
        changed=copy.deepcopy(rows)
        changed[0]["core_recomputed_at_capture"]=True
        changed[0]["snapshot_sha256"]=logger.digest(
            {k:v for k,v in changed[0].items() if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError,"PROMOTION_FORBIDDEN"):
            logger.validate_prospective_batch(changed)
        changed=copy.deepcopy(rows)
        changed[0]["withheld_flags"]["macro"]=False
        changed[0]["snapshot_sha256"]=logger.digest(
            {k:v for k,v in changed[0].items() if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError,"WITHHELD_FLAG_MISMATCH"):
            logger.validate_prospective_batch(changed)

    def test_prospective_source_clock_and_wrong_pair_block(self):
        rows=logger.make_rows(logger.parse_cutoff("2026-10-26T19:31:00Z"),"forward-20261026")
        changed=copy.deepcopy(rows)
        changed[0]["pair"]="EUR/EUR"
        changed[0]["snapshot_sha256"]=logger.digest(
            {k:v for k,v in changed[0].items() if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError,"NON_G8_PAIR_OR_ORIENTATION"):
            logger.validate_prospective_batch(changed)
        changed=copy.deepcopy(rows)
        changed[0]["inputs"]["core_pair_state"]["available_at"]="2026-10-27T23:59:59Z"
        changed[0]["snapshot_sha256"]=logger.digest(
            {k:v for k,v in changed[0].items() if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError,"POST_DECISION_INPUT_LEAK"):
            logger.validate_prospective_batch(changed)

    def test_prospective_t0_promotion_rejected_without_touching_ledger(self):
        rows=logger.make_rows(logger.parse_cutoff("2026-10-26T19:31:00Z"),"forward-20261026")
        rows[0]["t0_fx_reference"]["intra_day_traded_price"]=True
        rows[0]["snapshot_sha256"]=logger.digest(
            {k:v for k,v in rows[0].items() if k!="snapshot_sha256"})
        with tempfile.TemporaryDirectory() as tmp:
            old=logger.DECISIONS
            try:
                logger.DECISIONS=pathlib.Path(tmp)/"ledger.jsonl"
                with self.assertRaisesRegex(ValueError,"T0_REFERENCE_MISMATCH_OR_PROMOTION"):
                    logger.append_rows(rows,False)
                self.assertFalse(logger.DECISIONS.exists())
            finally:
                logger.DECISIONS=old

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
