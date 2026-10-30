#!/usr/bin/env python3
"""Regression: CET/CEST real-time recovery, no duplicate V1/V2, no new cron."""
import datetime as dt
import itertools
import json
import tempfile
import unittest
from pathlib import Path

from validation.forward.hourly_recovery_gate_v1 import (
    HOURLY, completed_v1, completed_v2, evaluate,
)


def at(text):
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


class HourlyForwardRecoveryTests(unittest.TestCase):
    def ev(self, when, v1=False, v2=False, event="workflow_run",
           upstream=HOURLY, upstream_event="schedule"):
        return evaluate(at(when), event, upstream, upstream_event, v1, v2)

    def test_cet_same_day_after_seven_allows_recovery(self):
        x = self.ev("2026-10-28T18:46:00Z")
        self.assertTrue(x["eligible"])
        self.assertEqual(x["local_time"][-6:], "+01:00")
        self.assertEqual(x["reason"], "HOURLY_SAME_DAY_FORWARD_RECOVERY")

    def test_cest_same_day_after_seven_allows_recovery(self):
        x = self.ev("2026-10-19T17:15:00Z")
        self.assertTrue(x["eligible"])
        self.assertEqual(x["local_time"][-6:], "+02:00")

    def test_early_and_weekend_hourly_skipped(self):
        self.assertFalse(self.ev("2026-10-28T17:59:00Z")["eligible"])
        self.assertFalse(self.ev("2026-10-31T20:00:00Z")["eligible"])

    def test_existing_both_ledgers_never_recaptured(self):
        x = self.ev("2026-10-28T20:20:00Z", True, True)
        self.assertFalse(x["eligible"])
        self.assertEqual(x["reason"], "BOTH_PROSPECTIVE_LEDGERS_ALREADY_CAPTURED_TODAY")
        self.assertTrue(self.ev("2026-10-28T20:20:00Z", True, False)["eligible"])

    def test_future_quality_aware_missing_reopens_existing_hourly_recovery(self):
        from validation.forward.hourly_recovery_gate_v1 import QUALITY_FIRST_DAY
        self.assertEqual(QUALITY_FIRST_DAY, dt.date(2026,11,2))
        after = at("2026-11-02T20:20:00Z")
        missing = evaluate(after,"workflow_run",HOURLY,"schedule",
                           True,True,False)
        self.assertTrue(missing["eligible"])
        self.assertEqual(missing["reason"],"HOURLY_SAME_DAY_FORWARD_RECOVERY")
        complete = evaluate(after,"workflow_run",HOURLY,"schedule",
                            True,True,True)
        self.assertFalse(complete["eligible"])
        self.assertEqual(complete["reason"],
                         "ALL_FUTURE_PROSPECTIVE_LEDGER_CLASSES_CAPTURED_TODAY")
        prior = evaluate(at("2026-10-30T20:20:00Z"),"workflow_run",
                         HOURLY,"schedule",True,True,False)
        self.assertFalse(prior["eligible"])
        self.assertEqual(prior["reason"],
                         "BOTH_PROSPECTIVE_LEDGERS_ALREADY_CAPTURED_TODAY")

    def test_future_quality_only_does_not_skip_missing_core_or_original_v2(self):
        after=at("2026-11-02T20:20:00Z")
        for a,b in ((False,True),(True,False),(False,False)):
            self.assertTrue(evaluate(after,"workflow_run",HOURLY,"schedule",
                                     a,b,True)["eligible"])
        self.assertFalse(evaluate(after,"workflow_run",HOURLY,
                                  "pull_request",True,True,False)["eligible"])

    def test_hourly_pr_or_push_never_triggers(self):
        self.assertFalse(self.ev("2026-10-28T20:20:00Z",
                                 upstream_event="push")["eligible"])

    def test_prior_pair_setup_dispatch_and_pr_validation_unchanged(self):
        for event, up in (("pull_request", ""), ("workflow_dispatch", ""),
                          ("schedule", ""), ("workflow_run", "Pair Setup Operational View V1")):
            x = self.ev("2026-10-28T08:00:00Z", event=event, upstream=up)
            self.assertTrue(x["eligible"])

    def test_both_ledger_completion_requires_full_original_day_coverage(self):
        names = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"]
        pairs = [a + "/" + b for a,b in itertools.combinations(names,2)]
        self.assertEqual(len(pairs),28)
        with tempfile.TemporaryDirectory() as tmp:
            v1=Path(tmp)/"v1.jsonl"
            v2=Path(tmp)/"v2.jsonl"
            today="2026-10-28"
            rows=[{"capture_class":"FROZEN_CORE_BASELINE_OBSERVATION",
                   "decision_cutoff":today+"T20:08:06Z",
                   "pair":p,"t0_fx_reference":{"state":"OBSERVED_AT_CAPTURE"}}
                  for p in pairs]
            v1.write_text("".join(json.dumps(r)+"\n" for r in rows), encoding="utf-8")
            self.assertTrue(completed_v1(v1,today))
            self.assertFalse(completed_v1(v1,"2026-10-27"))
            v2.write_text(json.dumps({"local_date_rome":today,
                "official_ecb_t0_date":today,
                "snapshot_sha256":"abc",
                "domestic_v2_features":{x:{} for x in names},
                "observed_t0_ref":{p:{} for p in pairs}})+"\n",encoding="utf-8")
            self.assertTrue(completed_v2(v2,today))
            self.assertFalse(completed_v2(v2,"2026-10-27"))
            rows.pop()
            v1.write_text("".join(json.dumps(r)+"\n" for r in rows), encoding="utf-8")
            self.assertFalse(completed_v1(v1,today))


if __name__ == "__main__":
    unittest.main()
