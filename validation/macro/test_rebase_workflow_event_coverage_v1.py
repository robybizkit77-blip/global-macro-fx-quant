"""Regression: a real source/official evidence edit cannot bypass Macro rebase QA.

Checks the PR and main push events independently. It does not authorize a
Macro rebase or modify source files, scores or rankings.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/macro-g8-rebase-readiness-v1.yml"

REQUIRED = (
    "validation/macro/rebase_readiness_v1.py",
    "validation/macro/test_rebase_readiness_v1.py",
    "validation/macro/rebase_joint_gate_v1.py",
    "validation/macro/test_rebase_joint_gate_v1.py",
    "validation/macro/score_formula_provenance_v1.py",
    "validation/macro/test_score_formula_provenance_v1.py",
    "validation/macro/latest_release_pit_ledger_v1.py",
    "validation/macro/test_latest_release_pit_ledger_v1.py",
    "validation/macro/test_rebase_workflow_event_coverage_v1.py",
    "validation/macro/legacy_v2_score_evidence_bridge_v1.py",
    "validation/macro/test_legacy_v2_score_evidence_bridge_v1.py",
    "validation/macro/v2_g8_quarterly_gdp_research_target_v1.py",
    "validation/macro/test_v2_g8_quarterly_gdp_research_target_v1.py",
    "validation/macro/CORE_G8_OFFICIAL_RELEASE_WEB_ATTESTATIONS_2026-10-20.json",
    "validation/macro/CORE_G8_OFFICIAL_RELEASE_WEB_ATTESTATIONS_2026-10-22.json",
    "validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json",
    ".github/workflows/macro-g8-rebase-readiness-v1.yml",
    "live_data/sections/D.json",
    "live_data/sections/MACRO_SERIES.json",
    "live_data/sections/MACRO_THERMOMETER_DATA.json",
    "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
    "live_data/sections/NATIVE_RATES_DATA.json",
    "live_data/sections/OIS_OPERATIONAL_VIEW.json",
)


def event_paths(workflow: str, event: str, following: str) -> list[str]:
    prefix = "  " + event + ":\n"
    after = "\n  " + following + ":\n"
    assert workflow.count(prefix) == 1, event
    segment = workflow.split(prefix, 1)[1].split(after, 1)[0]
    assert "branches: [main]" in segment, event
    return re.findall(r"^      - '([^']+)'$", segment, re.M)


class RebaseWorkflowCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_all_real_source_and_audit_changes_trigger_both_ci_events(self):
        pr = event_paths(self.workflow, "pull_request", "push")
        push = event_paths(self.workflow, "push", "workflow_run")
        for event, actual in (("PR", pr), ("MAIN_PUSH", push)):
            with self.subTest(event=event):
                self.assertEqual(len(actual), len(set(actual)),
                                 "duplicate paths mask missing latest evidence")
                self.assertEqual(set(actual), set(REQUIRED))
                for path in REQUIRED:
                    self.assertTrue((ROOT / path).is_file(), path)

    def test_ongoing_morning_and_manual_checks_remain(self):
        work = self.workflow.split("  workflow_run:\n", 1)[1].split(
            "\npermissions:\n", 1)[0]
        for event in ("Macro Persistent Daily V1", "Rates Persistent Daily V1",
                      "Pair Setup Operational View V1"):
            self.assertIn("'"+event+"'", work)
        self.assertIn("  workflow_dispatch:", work)
        self.assertIn("    - cron: '0 8 * * 1-5'", work)

    def test_read_only_strict_rebase_remains_blocked(self):
        content = self.workflow
        for required in (
            "assert x['structural_rebase']=='BLOCKED_SCORE_CONTRACT'",
            "assert x['safe_to_publish_D'] is False",
            "assert x['safe_to_publish_new_D'] is False",
            "x['safe_to_update_pair_thesis'] is False",
            "assert x['writes_live_data'] is False",
            "git diff --exit-code -- live_data/sections/D.json",
        ):
            self.assertIn(required, content)
        self.assertIn("python -m unittest validation.macro.test_rebase_workflow_event_coverage_v1 -v", content)


if __name__ == "__main__":
    unittest.main()
