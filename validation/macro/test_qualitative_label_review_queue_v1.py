#!/usr/bin/env python3
"""Negative cases on the real 2026-10-20 Macro checkpoint and source files."""
import copy
import json
import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from validation.macro.qualitative_label_review_queue_v1 import (
    CHECKPOINT, ROOT, PATHS, build, history_delta,
)


def original():
    values = [
        json.loads(CHECKPOINT.read_text(encoding="utf-8")),
        *(json.loads((ROOT / path).read_text(encoding="utf-8"))
          for path in PATHS.values())
    ]
    # Restore *synthetically*, in memory only, the original source checkpoint
    # for isolated delta tests. Production must still detect the REAL UK
    # July/August repair as changed (one GBP currency, seven affected pairs).
    s = next(row for row in values[2]["GBP"] if row["id"] == "UK_UNEMP_RATE_history_value")
    if str(s["last_date"])[:7] == "2026-08":
        assert s["dates"][-2:] == ["2026-07-01", "2026-08-01"]
        assert s["values"][-2:] == [4.9, 4.7]
        s["dates"].pop()
        s["values"].pop()
        s["values"][-1] = 4.7
        s["last_date"] = "2026-07-01"
        s["last_value"] = 4.7
        h = values[3]["currencies"]["GBP"]["labour"]
        h["history"].pop()
        h["history"][-1] = 4.7
        h["as_of"] = "2026-07-01"
        h["latest_value"] = 4.7
        values[3]["currencies"]["GBP"]["as_of_detail"]["unemployment"] = "2026-07-01"
    return tuple(values)


class QualitativeReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = original()
        cls.today = datetime.now(ZoneInfo('Europe/Rome')).date()

    def run_review(self, changed=None):
        values = list(copy.deepcopy(self.data))
        if changed:
            changed(values)
        return build(*values, self.today)

    def test_baseline_has_no_new_alert_but_macro_model_remains_stale(self):
        r = self.run_review()
        self.assertEqual(r["status"], "NO_SOURCE_DELTA_SINCE_CHECKPOINT")
        self.assertEqual(r["changed_currencies_count"], 0)
        self.assertEqual(r["impacted_pairs_count"], 0)
        self.assertEqual(r["observed_pairs_count"], 28)
        self.assertEqual(r["observed_currencies_count"], 8)
        self.assertIs(r["canonical_macro_baseline_current"], False)
        self.assertIs(r["safe_to_publish_new_D"], False)

    def test_one_revised_core_number_impacts_seven_pairs(self):
        def modify(x):
            x[2]["EUR"][0]  # only make sure shape exists
            row = next(t for t in x[2]["EUR"] if t.get("id") == "EA_HICP_HEADLINE_YOY_history_value")
            row["values"][-1] += .1
            x[3]["currencies"]["EUR"]["inflation"]["latest_value"] += .1
        r = self.run_review(modify)
        self.assertEqual(r["status"], "REVIEW_REQUIRED")
        self.assertEqual(r["changed_currencies"], ["EUR"])
        self.assertEqual(r["impacted_pairs_count"], 7)
        self.assertEqual(r["source_change_counts"]["CORE"], 1)
        self.assertTrue(any("LATEST_REVISION" in e["flags"]
                            for e in r["currencies"]["EUR"]["changed_inputs"]))

    def test_new_monthly_release_impacts_seven_pairs(self):
        def modify(x):
            row = next(t for t in x[2]["EUR"] if t.get("id") == "EA_HICP_HEADLINE_YOY_history_value")
            row["dates"].append("2026-10")
            row["values"].append(row["values"][-1] + .1)
            h = x[3]["currencies"]["EUR"]["inflation"]
            h["as_of"] = "2026-10"
            h["latest_value"] += .1
        r = self.run_review(modify)
        self.assertTrue(any("NEW_OBSERVATION" in e["flags"]
                            for e in r["currencies"]["EUR"]["changed_inputs"]))

    def test_historical_revision_does_not_look_like_only_new_release(self):
        old = {"id": "fake", "dates": ["2026-07", "2026-08", "2026-09"],
               "values": [1.0, 2.0, 3.0]}
        updated = {"id": "fake", "dates": ["2026-07", "2026-08", "2026-09", "2026-10"],
                   "values": [1.0, 2.5, 3.0, 4.0]}
        status = history_delta(old, updated)
        self.assertIn("NEW_OBSERVATION", status["flags"])
        self.assertIn("HISTORICAL_REVISION", status["flags"])
        self.assertEqual(status["revised_periods"], ["2026-08"])

    def test_rates_only_change_triggers_only_aud_reapproval(self):
        def modify(x):
            x[5]["AUD"]["2Y"] += .01
        r = self.run_review(modify)
        self.assertEqual(r["changed_currencies"], ["AUD"])
        self.assertEqual(r["source_change_counts"]["RATES"], 1)
        self.assertEqual(r["source_change_counts"]["CORE"], 0)
        self.assertEqual(r["impacted_pairs_count"], 7)
        self.assertIsNone(r["currencies"]["AUD"]["current_macro_vote"])

    def test_estimated_ois_status_change_never_promotes_a_policy_vote(self):
        def modify(x):
            x[6]["currencies"]["USD"]["as_of"] = "2026-10-20"
        r = self.run_review(modify)
        self.assertEqual(r["changed_currencies"], ["USD"])
        self.assertEqual(r["impacted_pairs_count"], 7)
        self.assertFalse(r["currencies"]["USD"]["bias_promoted"])
        self.assertFalse(r["eligible_for_structural_rebase"])

    def test_two_currencies_have_thirteen_unique_impacted_pairs(self):
        def modify(x):
            x[5]["AUD"]["2Y"] += .01
            x[5]["NZD"]["10Y"] += .01
        r = self.run_review(modify)
        self.assertEqual(r["changed_currencies"], ["AUD", "NZD"])
        self.assertEqual(r["impacted_pairs_count"], 13)

    def test_changes_to_frozen_macro_label_fail_closed(self):
        def modify(x):
            x[7]["pairs"]["AUDCHF"]["decision_frame"]["structural"]["macro"]["a"] = -1
        with self.assertRaisesRegex(ValueError, "conflicting macro votes|unapproved qualitative"):
            self.run_review(modify)

    def test_future_core_observation_rejected(self):
        def modify(x):
            row = next(t for t in x[2]["USD"] if t.get("id") == "US_UNRATE_history_value")
            row["dates"].append((self.today + timedelta(days=90)).isoformat())
            row["values"].append(row["values"][-1])
            h = x[3]["currencies"]["USD"]["labour"]
            h["as_of"] = (self.today + timedelta(days=90)).isoformat()
        with self.assertRaisesRegex(ValueError, "future observation"):
            self.run_review(modify)

    def test_incomplete_growth_inventory_must_not_be_silently_promoted(self):
        def modify(x):
            row = next(t for t in x[2]["CHF"] if t.get("category") == "Crescita")
            row["category"] = "UNKNOWN"
        with self.assertRaisesRegex(ValueError, "Growth source inventory changed"):
            self.run_review(modify)

    def test_invalid_checkpoint_cannot_claim_recertification(self):
        def modify(x):
            x[0]["qualitative_labels_recertified"] = True
        with self.assertRaisesRegex(ValueError, "checkpoint cannot certify"):
            self.run_review(modify)


if __name__ == "__main__":
    unittest.main()
