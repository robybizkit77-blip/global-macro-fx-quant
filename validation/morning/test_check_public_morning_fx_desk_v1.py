#!/usr/bin/env python3
"""Public morning audit must separate on-time evidence from later existence."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
from validation.morning.check_public_morning_fx_desk_v1 import assess
from validation.morning.build_morning_fx_desk_v1 import ROOT

SEED=ROOT/"site/fx-quant-v2/next/morning-desk-current.json"
def at(hour):
    return datetime(2026,11,11,hour,0,tzinfo=timezone.utc) # Rome CET +01

class MorningPublicProofTests(unittest.TestCase):
    def setUp(self):
        self.source=json.loads(SEED.read_text(encoding="utf-8"))
        self.edition=copy.deepcopy(self.source)
        self.edition["edition_date"]="2026-11-11"
        self.edition["observation_cutoff_exclusive"]="2026-11-11"
        self.edition["edition_status"]="MORNING_SNAPSHOT"
        # The canonical site edition advances every morning. Rebase the
        # historical 11 November test fixture *entirely*, including its chart
        # source dates; otherwise an actual 13 November chart is intentionally
        # rejected as future information in the historical 11 November case.
        for chart in self.edition["charts"]:
            if chart.get("as_of", "") >= "2026-11-11":
                chart["as_of"] = "2026-11-10"
            for point in chart.get("points", []):
                if point.get("date", "") >= "2026-11-11":
                    point["date"] = "2026-11-10"

    def test_public_audit_waits_for_editorial_writer(self):
        workflow = (ROOT/".github/workflows/fxv2-morning-public-proof.yml").read_text(encoding="utf-8")
        self.assertIn("needs: [contract, morning-editorial]", workflow)
        self.assertIn("always() &&", workflow)
        self.assertIn("needs.morning-editorial.outputs.admitted == 'true'", workflow)
        self.assertIn("github.event_name == 'workflow_run'", workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", workflow)
        self.assertIn("Calendar News Operational Refresh V1", workflow)
        self.assertIn("Macro Persistent Daily V1", workflow)
        self.assertIn("python3 -m validation.morning.plan_source_triggered_morning_v1", workflow)

    def test_not_invented_delivery_time(self):
        prior=assess(self.edition,at(6))
        self.assertEqual(prior["status"],"VERIFIED_ON_PUBLIC_SITE_BEFORE_0800")
        self.assertTrue(prior["public_delivery_by_0800_proven"])
        later=assess(self.edition,at(10))
        self.assertEqual(later["status"],"PRESENT_NOW_BUT_ON_TIME_DELIVERY_NOT_PROVEN")
        self.assertFalse(later["public_delivery_by_0800_proven"])

    def test_archived_is_not_today(self):
        # Derive an archived fixture independent of the mutable current edition.
        # Yesterday's successful publication must not break tomorrow's CI.
        archived=copy.deepcopy(self.edition)
        archived["edition_date"]="2026-11-10"
        archived["observation_cutoff_exclusive"]="2026-11-10"
        for chart in archived["charts"]:
            chart["as_of"]="2026-11-09"
            for point in chart["points"]:
                if point["date"]>="2026-11-10":
                    point["date"]="2026-11-09"
        self.assertEqual(assess(archived,at(6))["status"],"ARCHIVED_AWAITING_MORNING")
        self.assertEqual(assess(archived,at(10))["status"],"STALE_AFTER_0800")

    def test_missing_and_future(self):
        self.assertEqual(assess(None,at(6))["status"],"PREDEADLINE_UNREACHABLE")
        self.assertEqual(assess(None,at(10))["status"],"MISSING_AFTER_0800")
        future=copy.deepcopy(self.edition)
        future["edition_date"]="2026-11-12"
        future["observation_cutoff_exclusive"]="2026-11-12"
        self.assertEqual(assess(future,at(6))["status"],"INVALID_FUTURE_EDITION")

    def test_reconstruction_is_not_morning_delivery(self):
        self.edition["edition_status"]="RECONSTRUCTION_NOT_POINT_IN_TIME"
        self.assertEqual(assess(self.edition,at(6))["status"],"RECONSTRUCTION_NOT_LIVE_MORNING")

    def test_future_chart_fails(self):
        self.edition["charts"][0]["points"][0]["date"]="2026-11-11"
        self.assertEqual(assess(self.edition,at(6))["status"],"POST_EVENT_LOOKAHEAD_REJECTED")

if __name__=="__main__":unittest.main()
