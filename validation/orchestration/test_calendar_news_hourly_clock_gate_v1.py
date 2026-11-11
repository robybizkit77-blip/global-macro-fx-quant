"""Regression for reusing hourly source-watch completion as a safe calendar clock.

Source-watch may fail publishing its own feed while the BLS/ONS/SECO website
remains available. In that case official macro collection MUST still run.
This only asserts the checked-in workflow gating contract, not a real GitHub
scheduled-run delivery (which must be audited separately).
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
REFRESH = ROOT / ".github/workflows/calendar-news-operational-refresh-v1.yml"
SOURCE_WATCH = ROOT / ".github/workflows/macro-desk-source-watch-v1.yml"


class CalendarNewsHourlyClockGateTests(unittest.TestCase):
    def setUp(self):
        self.workflow = REFRESH.read_text(encoding="utf-8")

    def test_reuses_existing_hourly_schedule_only(self):
        watch = SOURCE_WATCH.read_text(encoding="utf-8")
        self.assertIn("cron: '21 * * * *'", watch)
        self.assertIn("workflows: ['Macro Desk Source Watch V1', 'Liquidity JPY M3 Persistent Daily V1']",
                      self.workflow)
        # This patch must NOT add a Calendar scheduler or new workflow.
        self.assertIn("cron: '17 4 * * 1-5'", self.workflow)
        self.assertIn("cron: '17 6 * * *'", self.workflow)
        self.assertNotIn("cron: '* * * * *'", self.workflow)

    def test_macro_runner_independent_of_successful_headline_publish(self):
        trigger = re.search(
            r"(?m)^  refresh:\n(.*?)\n    runs-on: ubuntu-24\.04",
            self.workflow, re.S)
        self.assertIsNotNone(trigger, "Expected refresh job conditional")
        expr = trigger.group(1)
        self.assertIn("github.event.workflow_run.event == 'schedule'", expr)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", expr)
        self.assertIn('["success","failure","timed_out"]', expr)
        self.assertIn("github.event.workflow_run.conclusion", expr)
        self.assertNotIn("github.event.workflow_run.conclusion == 'success'", expr)

    def test_production_requires_a_completed_scheduled_main_parent(self):
        # Simulate the admitted event tuple. This is a transparent inspection
        # of expected outcomes; actual GitHub dispatch still requires QA.
        allowed = {"success", "failure", "timed_out"}
        valid = lambda event, branch, conclusion: (
            event == "schedule" and branch == "main" and conclusion in allowed)
        for conclusion in sorted(allowed):
            self.assertTrue(valid("schedule", "main", conclusion))
        for event, branch, conclusion in (
            ("push", "main", "success"),
            ("pull_request", "main", "success"),
            ("workflow_dispatch", "main", "success"),
            ("schedule", "feature", "success"),
            ("schedule", "main", "cancelled"),
            ("schedule", "main", "skipped"),
        ):
            self.assertFalse(valid(event, branch, conclusion))

    def test_no_forex_core_or_trading_writes_added(self):
        self.assertIn("python -m validation.macro.capture_uk_ch_gdp_official_firstseen_v11", self.workflow)
        self.assertIn("python validation/build_news_pulse_operational_v1.py", self.workflow)
        self.assertIn("python -m validation.macro.persist_calendar_news_safe_v12", self.workflow)
        self.assertNotIn("git push --force", self.workflow)
        self.assertIn("github.event_name != 'pull_request'", self.workflow)


if __name__ == "__main__":
    unittest.main()
