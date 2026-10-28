"""Exercise the WHOLE V2 attempt() input→gate→candidate→ledger pipeline.

A 27-Oct clock and records are permitted only in *isolated test RAM and a
temporary directory*, never in the committed prospective ledger. This proof
does NOT claim historical PIT or any real V2 forward result: the real forward
V2 launch starts only after its actual post-merge, same-day evening cutoff.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from validation.forward import capture_v2_research_prospective_evidence_v1 as cap
from validation.forward.test_capture_v2_research_prospective_evidence_v1 import (
    V2ProspectiveResearchCapture as IsolatedFixture
)


class WholeV2CapturePath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse the per-day isolated deterministic fixture (never an old
        # fixed 2026-10-27 runtime clock after the real market has advanced).
        # This test MUST NOT write a fake current-day FX fixing to live_data.
        IsolatedFixture.setUpClass()
        cls.cutoff = IsolatedFixture.cut
        cls.after = IsolatedFixture.now
        cls.names = (
            "ECB_G8_PRICE_HISTORY",
            "PAIR_SETUP_OPERATIONAL_VIEW",
            "D",
            "NATIVE_CB_DATA",
            "OIS_OPERATIONAL_VIEW",
            "NATIVE_RATES_DATA",
        )
        cls.source = {
            "ECB_G8_PRICE_HISTORY": IsolatedFixture.fx,
            "PAIR_SETUP_OPERATIONAL_VIEW": IsolatedFixture.pairs,
            "D": IsolatedFixture.legacy,
            "NATIVE_CB_DATA": IsolatedFixture.cb,
            "OIS_OPERATIONAL_VIEW": IsolatedFixture.ois,
            "NATIVE_RATES_DATA": IsolatedFixture.rates,
        }
        cls.candidate = IsolatedFixture.candidate
        cls.day = IsolatedFixture.day

    def sources(self, *, update=None):
        data = copy.deepcopy(self.source)
        if update:
            update(data)
        return data

    def attempt(self, data, journal, *, dry_run=False, candidate=None):
        # No monkeypatching of the global file system or current clock.
        # Only source reads are rerouted; the sole write is the /tmp test file.
        with patch.object(cap, "read_live", side_effect=lambda name: data[name]):
            with patch.object(cap, "file_sha",
                              side_effect=lambda filename: cap.sha(data[Path(filename).stem])):
                with patch.object(cap, "domestic_run",
                                  return_value=self.candidate if candidate is None else candidate):
                    return cap.attempt(cutoff=self.cutoff, now=self.after,
                                       dry_run=dry_run, path=journal)

    def test_real_command_path_synthetic_clock_full_8_g8_28_ecb_without_backfill(self):
        data = self.sources()
        roots = [cap.ROOT/"live_data/sections"/(name+".json")
                 for name in self.names]
        original = {str(path):hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in roots}
        original_ledger = cap.JOURNAL.read_bytes() if cap.JOURNAL.exists() else None
        with tempfile.TemporaryDirectory() as temp:
            journal = Path(temp)/"isolated_v2_research.jsonl"
            preflight = self.attempt(data, journal, dry_run=True)
            self.assertEqual(preflight["status"],
                             "VALID_FIRST_DAY_DRY_RUN_NO_WRITE")
            self.assertEqual(preflight["appended"], 0)
            self.assertFalse(journal.exists())
            saved = self.attempt(data, journal)
            self.assertEqual(saved["status"],
                             "PROSPECTIVE_SHADOW_RESEARCH_SNAPSHOT_APPEND_OK")
            self.assertEqual(saved["appended"], 1)
            self.assertEqual(saved["new_V2_pair_signals"], 0)
            self.assertEqual(saved["future_outcomes_at_capture"], 0)
            rows = [json.loads(line) for line in journal.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["schema"], cap.SCHEMA)
            self.assertEqual(row["local_date_rome"], self.day)
            self.assertEqual(row["official_ecb_t0_date"], self.day)
            self.assertEqual(len(row["domestic_v2_features"]),8)
            self.assertEqual(len(row["observed_t0_ref"]),28)
            self.assertEqual(len(row["old_core_pair_context_UNCHANGED"]),28)
            self.assertTrue(row["snapshot_may_be_compared_later_with_independent_ecb_reference_returns"])
            self.assertFalse(row["future_outcomes_observed_at_capture"])
            self.assertFalse(row["V2_pair_directional_predictions"])
            self.assertFalse(row["eligible_for_real_trading_or_sizing"])
            self.assertEqual(cap.verify_journal(rows), {self.day})
            first_bytes = journal.read_bytes()
            again = self.attempt(data, journal)
            self.assertEqual(again["status"],
                             "EXISTING_DATE_ALREADY_FROZEN_NO_OVERWRITE")
            self.assertEqual(again["appended"],0)
            self.assertEqual(journal.read_bytes(), first_bytes)
        self.assertEqual(original, {
            str(path):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in roots})
        self.assertEqual(original_ledger,
            cap.JOURNAL.read_bytes() if cap.JOURNAL.exists() else None)

    def test_real_command_rejects_stale_t0_before_computing_v2_candidate(self):
        def stale(data):
            previous=(self.cutoff.date()-timedelta(days=1)).isoformat()
            data["ECB_G8_PRICE_HISTORY"]["last_as_of"] = previous
            data["PAIR_SETUP_OPERATIONAL_VIEW"]["price_asof"] = previous
        data = self.sources(update=stale)
        with tempfile.TemporaryDirectory() as temp:
            journal = Path(temp)/"blocked.jsonl"
            with patch.object(cap, "read_live", side_effect=lambda name: data[name]):
                with patch.object(cap, "file_sha",
                                  side_effect=AssertionError("no source hash before admissibility")):
                    with patch.object(cap,"domestic_run",
                                      side_effect=AssertionError("must gate before candidate calculation")):
                        result=cap.attempt(cutoff=self.cutoff, now=self.after,path=journal)
            self.assertEqual(result["status"],
                             "BLOCKED_NO_OFFICIAL_SAME_DAY_T0_NO_V2_CAPTURE")
            self.assertIn("ECB_CURRENT_DAY_FIXING_NOT_PRESENT",result["admission_checks"])
            self.assertIn("PAIR_SETUP_CURRENT_DAY_28_PAIR_PRICE_NOT_PRESENT",
                          result["admission_checks"])
            self.assertEqual(result["appended"],0)
            self.assertFalse(journal.exists())

    def test_no_pseudo_forward_if_research_source_drifted_after_admission(self):
        # V2 input cannot be stamped in the journal if the candidate is
        # unexpectedly a trading score or the source records are inconsistent.
        changed = copy.deepcopy(self.candidate)
        changed["countries"]["USD"]["FX_strength_candidate"]=0.9
        with tempfile.TemporaryDirectory() as temp:
            journal = Path(temp)/"never.jsonl"
            with self.assertRaises(ValueError):
                self.attempt(self.sources(),journal,candidate=changed)
            self.assertFalse(journal.exists())
        def inconsistent_cb(data):
            data["NATIVE_CB_DATA"]["CAD"]["rate"] += 0.25
        with tempfile.TemporaryDirectory() as temp:
            journal = Path(temp)/"never.jsonl"
            with self.assertRaises(ValueError):
                self.attempt(self.sources(update=inconsistent_cb),journal)
            self.assertFalse(journal.exists())

    def test_runtime_gate_rejects_actual_too_early_clock_even_if_sources_present(self):
        with tempfile.TemporaryDirectory() as temp:
            journal = Path(temp)/"early.jsonl"
            with self.assertRaises(ValueError):
                cap.attempt(
                    cutoff=datetime.fromisoformat("2026-10-27T18:00:00+01:00"),
                    now=datetime.fromisoformat("2026-10-27T18:00:07+01:00"),
                    path=journal)
            self.assertFalse(journal.exists())


if __name__ == "__main__":
    unittest.main()
