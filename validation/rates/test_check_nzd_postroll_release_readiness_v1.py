#!/usr/bin/env python3
import copy
import json
import unittest
from datetime import date, timedelta
from check_nzd_postroll_release_readiness_v1 import build, isolated_candidate, RESEARCH, NATIVE

class Preflight(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(RESEARCH.read_text())
        self.native = json.loads(NATIVE.read_text())
        self.asof = date.fromisoformat(self.doc["publication_date"])
        # Exercise initial release independent of the deployed canonical date.
        self.native["NZD"]["date"] = "2026-10-16"

    def test_reference_and_no_promotion(self):
        original = copy.deepcopy(self.native)
        receipt = build(self.doc, self.native, self.asof)
        self.assertEqual(self.native, original)
        self.assertFalse(receipt["writes_live_data"])
        self.assertFalse(receipt["eligible_for_automatic_promotion"])
        self.assertGreaterEqual(receipt["weekly_reference"]["date"], self.doc["benchmark_roll_date"])
        self.assertLessEqual(receipt["weekly_reference"]["date"], receipt["weekly_cutoff"])
        self.assertEqual(receipt["latest"], self.doc["observations"][-1])

    def test_isolated_candidate_preserves_roll_and_native(self):
        original = copy.deepcopy(self.native)
        candidate = isolated_candidate(self.doc, self.native, self.asof)
        self.assertEqual(self.native, original)
        self.assertEqual(candidate["history2"]["dates"][0], self.doc["benchmark_roll_date"])
        self.assertEqual(candidate["history2"]["dates"], candidate["history10"]["dates"])
        self.assertEqual(candidate["history2"]["values"], [r["2Y"] for r in self.doc["observations"]])
        self.assertEqual(candidate["history10"]["values"], [r["10Y"] for r in self.doc["observations"]])
        self.assertGreaterEqual(candidate["weekly_reference"]["date"], self.doc["benchmark_roll_date"])
        self.assertFalse(candidate["writes_live_data"])
        self.assertFalse(candidate["cross_roll_change_allowed"])
        with self.assertRaises(ValueError):
            isolated_candidate(self.doc, self.native, self.asof + timedelta(days=15))

    def test_protected_contract(self):
        for key, value in (("eligible_for_core", True),
                           ("benchmark_2Y", "different bond"),
                           ("html_sha256", "bad"),
                           ("publication_date", "2099-01-01")):
            changed = dict(self.doc, **{key:value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                build(changed, self.native, self.asof)

    def test_stale_not_ready(self):
        result = build(self.doc, self.native, self.asof + timedelta(days=15))
        self.assertEqual(result["status"], "RETAINED_OR_STALE_REVIEW_ONLY")

    def test_missing_latest_html_match(self):
        changed = copy.deepcopy(self.doc)
        changed["html_xlsx_matched_dates"].remove(self.doc["last_observation_date"])
        with self.assertRaises(ValueError):
            build(changed, self.native, self.asof)

    def test_duplicate_observation(self):
        changed = copy.deepcopy(self.doc)
        changed["observations"].insert(1, changed["observations"][0])
        with self.assertRaises(ValueError):
            build(changed, self.native, self.asof)

if __name__ == "__main__":
    unittest.main()
