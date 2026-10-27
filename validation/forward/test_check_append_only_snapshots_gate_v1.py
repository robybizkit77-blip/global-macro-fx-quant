"""Regression: appended daily prospective decision batches must not block E2E."""
import copy
import json
import unittest
from pathlib import Path
from validation.forward.check_append_only_snapshots_gate_v1 import inspect,PAIRS,canonical_hash

ROOT=Path(__file__).resolve().parents[2]
ARCH=ROOT/"validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl"


def current():
    return [json.loads(line) for line in ARCH.read_text(encoding="utf-8").splitlines() if line.strip()]


def reseal(row):
    row["snapshot_sha256"]=canonical_hash(row)


class ForwardJournalGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=current()

    def test_real_append_only_56_rows_two_complete_batches(self):
        r=inspect(self.rows)
        self.assertGreaterEqual(r["snapshot_rows"],56)
        self.assertEqual(r["snapshot_rows"],28*r["complete_28_pair_batches"])
        self.assertTrue(r["snapshot_hash_identity_integrity"])
        self.assertTrue(r["no_forward_returns_embedded"])
        self.assertGreaterEqual(r["legacy_v1_0_batches"],1)
        self.assertFalse(r["backtest_PIT_certified"])
        self.assertFalse(r["forward_outcomes_validated"])
        self.assertFalse(r["safe_to_modify_core_or_pairs"])

    def test_missing_or_duplicate_pair_never_accepted(self):
        with self.assertRaises(ValueError):inspect(self.rows[:-1])
        x=copy.deepcopy(self.rows)
        x[-1]=dict(x[-2])
        with self.assertRaises(ValueError):inspect(x)

    def test_legacy_smoke_batch_alone_still_verifies(self):
        x=inspect(self.rows[:28])
        self.assertEqual(x["complete_28_pair_batches"],1)
        self.assertEqual(x["snapshot_rows"],28)

    def test_cross_cutoff_reordering_and_corrupt_provenance_rejected(self):
        x=self.rows[28:]+self.rows[:28]
        with self.assertRaises(ValueError):inspect(x)
        x=copy.deepcopy(self.rows)
        x[-1]["thesis_strength"]="FORGED"
        with self.assertRaises(ValueError):inspect(x)

    def test_future_input_after_cutoff_must_fail_even_with_rehashed_snapshot(self):
        x=copy.deepcopy(self.rows)
        row=x[-1]
        self.assertTrue(row["schema_version"].endswith("V1.1.0"))
        key=next(k for k,v in row["inputs"].items()
                 if isinstance(v,dict) and "available_at" in v)
        row["inputs"][key]["available_at"]="2027-12-01T00:00:00Z"
        reseal(row)
        with self.assertRaisesRegex(ValueError,"future source"):inspect(x)

    def test_cannot_reclassify_frozen_core_as_current_on_v1_1(self):
        x=copy.deepcopy(self.rows)
        x[-1]["current_macro_score_certified"]=True
        reseal(x[-1])
        with self.assertRaisesRegex(ValueError,"certification forgery"):inspect(x)

    def test_fake_future_outcome_in_decision_rejected(self):
        x=copy.deepcopy(self.rows)
        x[-1]["forward_return"]=0.05
        reseal(x[-1])
        with self.assertRaisesRegex(ValueError,"future outcomes"):inspect(x)


if __name__=="__main__":unittest.main()
