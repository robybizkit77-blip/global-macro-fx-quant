"""Read-only historic Beta/Forward archive readiness gates."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "audit_beta_forward_launch_readiness_v1",
    HERE / "audit_beta_forward_launch_readiness_v1.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def fixtures():
    beta = json.loads(mod.BETA.read_text())
    schema = json.loads(mod.SCHEMA.read_text())
    dec = mod._read_lines(mod.DECISIONS)
    out = mod._read_lines(mod.OUTCOMES)
    return beta, schema, dec, out


class LaunchTruthGateTests(unittest.TestCase):
    def setUp(self):
        self.beta, self.schema, self.dec, self.out = fixtures()

    def test_real_repo_archive_research_only_and_not_signed_off(self):
        x = mod.inspect(self.beta, self.schema, self.dec, self.out)
        self.assertEqual(x["state"], "NOT_READY_FOR_FINAL_LAUNCH_SIGNOFF")
        self.assertGreaterEqual(x["forward"]["decision_rows"], 28)
        self.assertGreaterEqual(x["forward"]["outcome_rows"], 0)
        self.assertGreaterEqual(x["forward"]["distinct_run_ids"], 1)
        self.assertGreaterEqual(x["forward"]["unique_cutoff_instants"], 1)
        self.assertEqual(x["forward"]["decision_snapshot_hash_mismatches"], 0)
        self.assertEqual(x["forward"]["decision_snapshot_clock_invalid"], 0)
        self.assertEqual(x["forward"]["duplicate_snapshot_ids"], 0)
        if not self.out:
            self.assertIn("FORWARD_NO_REALIZED_OUTCOMES", x["blockers"])
        if len(x["forward"]["run_ids"]) == 1:
            self.assertIn("FORWARD_SMOKE_ONLY_NO_LIVE_OBSERVATION_SEQUENCE", x["blockers"])
        self.assertTrue(x["beta"]["observational_contract_present"])
        self.assertFalse(x["beta"]["strategy_beta_validated"])
        self.assertFalse(x["beta_promoted"])
        self.assertFalse(x["forward_performance_promoted"])

    def test_reference_pdf_has_ten_step_gate_not_fake_algorithm_completion(self):
        x = mod.inspect(self.beta, self.schema, self.dec, self.out)
        steps = x["beta"]["pdf_23_3_ten_step_audit"]
        self.assertEqual(len(steps), 10)
        self.assertEqual(steps[-1]["state"], "NOT_CERTIFIED")
        self.assertEqual(steps[3]["state"], "PARTIAL_52W_OLS_HC3_RESEARCH_NO_PIT_NO_HAC")
        self.assertEqual(steps[4]["state"], "HUBER_LEAVE_ONE_OUT_RESEARCH_ONLY")
        self.assertEqual(steps[5]["state"], "DIMSON_1LEAD_1LAG_RETROSPECTIVE_ONLY")
        self.assertEqual(steps[6]["state"], "ROLLING_52W_FOUR_WINDOWS_ONLY_NO_EWMA_OR_KALMAN")
        self.assertEqual(steps[1]["state"], "NOT_CERTIFIED")
        self.assertEqual(steps[2]["state"], "NOT_IMPLEMENTED")
        self.assertFalse(x["beta"]["pdf_23_4_oos_hedge_variance_reduction_validated"])
        self.assertFalse(x["beta"]["b1_b2_ready"])

    def test_missing_snapshot_field_is_reported_not_promoted(self):
        x = mod.inspect(self.beta, self.schema, self.dec, self.out)
        self.assertGreater(x["forward"]["decision_snapshot_missing_contract_fields"], 0)
        self.assertIn("FORWARD_SNAPSHOT_FIELDS_MISMATCH_CANONICAL_CONTRACT", x["blockers"])

    def test_mutated_legacy_snapshot_hash_never_accepted(self):
        rows = copy.deepcopy(self.dec)
        rows[0]["thesis_strength"] = "ALTERED"
        x = mod.inspect(self.beta, self.schema, rows, self.out)
        self.assertEqual(x["forward"]["decision_snapshot_hash_mismatches"], 1)
        self.assertIn("FORWARD_ARCHIVE_INTEGRITY_EXCEPTION", x["blockers"])

    def test_timezone_naive_cutoff_detected(self):
        rows = copy.deepcopy(self.dec)
        rows[0]["decision_cutoff"] = "2026-10-14T21:01:45"
        x = mod.inspect(self.beta, self.schema, rows, self.out)
        self.assertEqual(x["forward"]["decision_snapshot_clock_invalid"], 1)

    def test_duplicate_snapshot_rejected_as_integrity(self):
        rows = copy.deepcopy(self.dec)
        rows.append(copy.deepcopy(rows[0]))
        x = mod.inspect(self.beta, self.schema, rows, self.out)
        self.assertEqual(x["forward"]["duplicate_snapshot_ids"], 1)

    def test_unlinked_outcome_does_not_certify_forward(self):
        ghost = {
            "snapshot_id": "a"*64, "horizon": "1W",
            "available_at": "2026-10-21T22:00:00Z",
        }
        ghost["outcome_sha256"] = mod._canonical_hash(ghost)
        x = mod.inspect(self.beta, self.schema, self.dec, [ghost])
        self.assertEqual(x["forward"]["invalid_outcomes"], 1)
        self.assertIn("FORWARD_ARCHIVE_INTEGRITY_EXCEPTION", x["blockers"])
        self.assertFalse(x["forward"]["performance_verified_oos"])

    def test_beta_contract_change_requires_review(self):
        c = copy.deepcopy(self.beta)
        c["governance"]["promotion_enabled"] = True
        x = mod.inspect(c, self.schema, self.dec, self.out)
        self.assertIn("BETA_GOVERNANCE_REQUIRES_INDEPENDENT_REVIEW", x["blockers"])
        self.assertFalse(x["beta"]["observational_contract_present"])

    def test_missing_archive_has_explicit_gap(self):
        x = mod.inspect(self.beta, self.schema, [], [])
        self.assertIn("FORWARD_NO_DECISION_SNAPSHOTS", x["blockers"])
        self.assertIn("FORWARD_NO_REALIZED_OUTCOMES", x["blockers"])


if __name__ == "__main__":
    unittest.main()
