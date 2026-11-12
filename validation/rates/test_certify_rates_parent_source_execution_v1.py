#!/usr/bin/env python3
"""Adversarial evidence regression: green/skipped Rates is NOT source refresh."""
from __future__ import annotations
import copy
import unittest
from certify_rates_parent_source_execution_v1 import certify, REQUIRED, FINISHERS


def fixture():
    names = (*REQUIRED, FINISHERS[0], "Other test")
    return {"jobs": [{"name": "persist-rates", "status": "completed",
                      "conclusion": "success",
                      "steps": [{"name": name, "status": "completed",
                                 "conclusion": "success"} for name in names]}]}


class RatesSourceExecutedProof(unittest.TestCase):
    def test_real_completed_source_and_validated_no_update(self):
        result = certify(fixture())
        self.assertTrue(result["source_verified"])
        self.assertFalse(result["new_market_observations_certified"])
        self.assertEqual(result["reason"], "UPSTREAM_RATES_SOURCE_AUDIT_ACTUALLY_EXECUTED")

    def test_real_completed_update_branch(self):
        payload = fixture()
        payload["jobs"][0]["steps"][3]["name"] = FINISHERS[1]
        self.assertTrue(certify(payload)["source_verified"])

    def test_green_noop_run_skipping_source_steps_fails_closed(self):
        payload = fixture()
        for step in payload["jobs"][0]["steps"]:
            if step["name"] in REQUIRED or step["name"] in FINISHERS:
                step.update(status="completed", conclusion="skipped")
        self.assertFalse(certify(payload)["source_verified"])
        self.assertIn("SOURCE_STEP_NOT_EXECUTED", certify(payload)["reason"])

    def test_each_required_source_step_can_fail_independently(self):
        for idx in range(len(REQUIRED)):
            with self.subTest(required=REQUIRED[idx]):
                payload=fixture()
                payload["jobs"][0]["steps"][idx]["conclusion"]="skipped"
                self.assertFalse(certify(payload)["source_verified"])

    def test_successful_source_but_no_validation_is_not_certified(self):
        payload=fixture()
        payload["jobs"][0]["steps"][3]["conclusion"]="skipped"
        self.assertEqual(certify(payload)["reason"],"RATES_CANDIDATE_NOT_VALIDATED")

    def test_wrong_job_failure_incomplete_duplicates_and_tampering(self):
        invalid = [None, {}, {"jobs": []}, {"jobs": [{}]}, {"jobs": "invalid"}]
        for value in invalid:
            self.assertFalse(certify(value)["source_verified"])
        for field, new in [("name","contract-only"),("status","in_progress"),
                           ("conclusion","failure")]:
            payload=fixture()
            payload["jobs"][0][field]=new
            self.assertFalse(certify(payload)["source_verified"])
        duplicated=fixture()
        duplicated["jobs"].append(copy.deepcopy(duplicated["jobs"][0]))
        self.assertFalse(certify(duplicated)["source_verified"])
        repeated=fixture()
        repeated["jobs"][0]["steps"].append(
            copy.deepcopy(repeated["jobs"][0]["steps"][0]))
        self.assertFalse(certify(repeated)["source_verified"])
        missing=fixture()
        missing["jobs"][0]["steps"]=[]
        self.assertFalse(certify(missing)["source_verified"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
