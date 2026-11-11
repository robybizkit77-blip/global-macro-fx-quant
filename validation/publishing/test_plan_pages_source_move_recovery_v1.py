"""Pages recovery is bounded to verified Git revision races.

No test invokes the GitHub API; delivery still requires independent
published-file and public HTTP checks in the existing workflow.
"""
from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from validation.publishing.plan_pages_source_move_recovery_v1 import plan,main

WORKFLOW=Path(__file__).resolve().parents[2]/".github/workflows/publish-dashboard-pages-v1.yml"


class PagesSourceMoveRecoveryTests(unittest.TestCase):
    def test_known_races_retry_at_most_twice(self):
        for marker in ("MAIN_MOVED", "PAGES_MOVED"):
            self.assertEqual(plan(marker,"0")["next_attempt"],1)
            self.assertEqual(plan(marker,"1")["next_attempt"],2)
            self.assertTrue(plan(marker,"0")["dispatch"])
            self.assertEqual(plan(marker,"2")["status"],"RETRY_BUDGET_EXHAUSTED")
            self.assertFalse(plan(marker,"2")["dispatch"])

    def test_unknown_failures_and_invalid_counter_not_retried(self):
        for marker in (None,"", "HTTP_NOT_CERTIFIED","WRONG_SOURCE", "FAKE_MAIN_MOVED"):
            self.assertFalse(plan(marker,"0")["dispatch"])
        for attempt in ("3", "-1", "03", "NaN", "999"):
            self.assertEqual(plan("MAIN_MOVED",attempt)["status"],"INVALID_RECOVERY_COUNT")

    def test_existing_workflow_only_and_readonly_rechecks(self):
        content=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:",content)
        self.assertIn("recovery_attempt:",content)
        self.assertIn("actions: write",content)
        self.assertIn("python3 -m validation.publishing.plan_pages_source_move_recovery_v1",content)
        self.assertIn("steps.race-plan.outputs.should_dispatch == 'true'",content)
        self.assertIn("publish-dashboard-pages-v1.yml/dispatches",content)
        self.assertIn("Verify published files against validated main",content)
        self.assertIn("Verify public Pages HTTP delivery after bounded CDN propagation",content)
        self.assertIn("PAGES_SOURCE_MAIN_MOVED",content)
        self.assertIn("git push --force-with-lease=refs/heads/gh-pages:",content)
        self.assertNotIn("git push --force origin",content)


if __name__=="__main__":
    unittest.main()
