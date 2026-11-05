#!/usr/bin/env python3
"""Offline execution proofs for the REAL serialized orchestrator Bash run_phase.

No network, no external dispatch, no source edits. A mock replaces only
dispatch_and_wait, preserving actual phase sequencing and failure handling.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/daily-data-orchestrator-v2.yml"
EXPECTED_CLOSE = [
    "price-persistent-daily-v1.yml",
    "calendar-news-operational-refresh-v1.yml",
    "final-e2e-certification-gate-v3.yml",
    "publish-dashboard-pages-v1.yml",
]


def phase_shell() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.index("          run_phase() {\n")
    end = text.index("\n      - name: Retain exact child-step proof", start)
    # Discard the real GitHub dispatch code; execute ONLY the production
    # run_phase block with a deterministic no-network dispatch stub.
    body = text[start:end]
    return "\n".join(
        line[10:] if line.startswith("          ") else line
        for line in body.splitlines()
    ) + "\n"


class IndependentFailureContinuation(unittest.TestCase):
    def run_close(self, fail: str | None):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            calls = root / "calls.txt"
            summary = root / "summary.md"
            evidence = root / "evidence"
            shell = phase_shell().replace(
                "/tmp/orchestration-child-step-evidence", str(evidence)
            )
            stub = """set -euo pipefail
dispatch_and_wait() {
  printf '%s\\n' "$1" >> "$CALL_LOG"
  [[ "$1" != "$MOCK_FAIL" ]]
}
"""
            env = dict(os.environ, PHASE="close",
                       CALL_LOG=str(calls), MOCK_FAIL=fail or "__NONE__",
                       GITHUB_STEP_SUMMARY=str(summary))
            done = subprocess.run(["bash", "-c", stub + shell],
                                  text=True, capture_output=True, env=env, cwd=ROOT)
            called = calls.read_text().splitlines() if calls.exists() else []
            saved = (evidence / "source-failures.txt").read_text().splitlines() \
                    if (evidence / "source-failures.txt").exists() else []
            note = summary.read_text() if summary.exists() else ""
            return done, called, saved, note

    def test_all_green_executes_publisher(self):
        result, called, saved, note = self.run_close(None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(called, EXPECTED_CLOSE)
        self.assertEqual(saved, [])
        self.assertIn("Collector failures in close: 0", note)

    def test_failed_source_does_not_block_other_collectors_or_final_gate(self):
        result, called, saved, note = self.run_close(EXPECTED_CLOSE[0])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(called, EXPECTED_CLOSE[:-1])
        self.assertEqual(saved, [EXPECTED_CLOSE[0]])
        self.assertIn("DEGRADED:", note)
        self.assertIn("Pages: **SKIPPED**", note)
        self.assertIn("ORCHESTRATOR_DEGRADED_FAIL_CLOSED", result.stderr)

    def test_failed_structural_certification_never_publishes(self):
        result, called, saved, note = self.run_close(EXPECTED_CLOSE[-2])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(called, EXPECTED_CLOSE[:-1])
        self.assertEqual(saved, [])
        self.assertIn("FINAL CERTIFICATION: **FAILED**", note)
        self.assertIn("Pages: **SKIPPED**", note)


if __name__ == "__main__":
    unittest.main()
