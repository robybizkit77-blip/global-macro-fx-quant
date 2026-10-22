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


def live_inputs():
    """Actual frozen October checkpoint compared with latest canonical sources."""
    return (
        json.loads(CHECKPOINT.read_text(encoding="utf-8")),
        *(json.loads((ROOT / path).read_text(encoding="utf-8"))
          for path in PATHS.values()),
    )


def original():
    """Synthetic no-delta fixture for isolating *one* source mutation.

    Do not rewrite the real checkpoint or live source data. Advancing Rates,
    OIS and New Zealand inflation can all legitimately affect the real
    reapproval queue, so a 2026-10-20 checkpoint is not a no-delta fixture.
    """
    values = list(live_inputs())
    checkpoint, _model, series, heat, _registry, rates, ois, _setup = values
    checkpoint = copy.deepcopy(checkpoint)
    for ccy, frozen in checkpoint["currencies"].items():
        rows = {row["id"]: row for row in series[ccy]}
        for dim in ("inflation", "labour"):
            target = frozen["core"][dim]
            row = rows[target["id"]]
            current = heat["currencies"][ccy][dim]
            target["dates"] = list(row["dates"])
            target["values"] = list(row["values"])
            target["heat_asof"] = current["as_of"]
            target["heat_value"] = current["latest_value"]
        for row_id, target in frozen["growth"].items():
            row = rows[row_id]
            target["dates"] = list(row["dates"])
            target["values"] = list(row["values"])
            target["frequency"] = row.get("frequency") or "M"
            target["source_file"] = row.get("source_file") or None
        rate = rates[ccy]
        frozen["rates"] = {
            "date": rate["date"], "quality": rate["quality"],
            "two_y": rate.get("2Y"), "ten_y": rate.get("10Y"),
        }
        pricing = ois["currencies"][ccy]
        frozen["ois"] = {
            "date": pricing["as_of"],
            "operational": pricing["operational_status"],
            "official_status": pricing["official_status"],
            "quality": pricing["quality"],
        }
    values[0] = checkpoint
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

    def test_actual_checkpoint_detects_source_changes_without_promotion(self):
        # In particular, September NZD CPI moved from 4.1% to 3.7%;
        # the pinned October 20 checkpoint must not be silently rebased.
        actual = build(*live_inputs(), self.today)
        self.assertEqual(actual["status"], "REVIEW_REQUIRED")
        self.assertIn("NZD", actual["changed_currencies"])
        nz_events = actual["currencies"]["NZD"]["changed_inputs"]
        self.assertTrue(any(
            e["category"] == "CORE" and e.get("dimension") == "inflation"
            and "NEW_OBSERVATION" in e["flags"]
            for e in nz_events), nz_events)
        self.assertEqual(
            sum("NZD" in (pair[:3], pair[3:]) for pair in actual["impacted_pairs"]), 7)
        self.assertFalse(actual["safe_to_publish_new_D"])
        self.assertFalse(actual["eligible_for_structural_rebase"])
        self.assertTrue(all(
            not row["bias_promoted"] for row in actual["currencies"].values()))

    def test_baseline_has_no_new_alert_but_macro_model_remains_stale(self):
        # Synthetic *source-equal* baseline for adversarial single-change tests.
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
            prior = date.fromisoformat(x[6]["currencies"]["USD"]["as_of"])
            x[6]["currencies"]["USD"]["as_of"] = (prior - timedelta(days=1)).isoformat()
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
