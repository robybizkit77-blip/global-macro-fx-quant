#!/usr/bin/env python3
"""Deterministic tests for V2-only no-op publishing and fail-closed evidence."""
from __future__ import annotations

import unittest
from pathlib import Path

from validation.publishing.check_fxv2_publication_tree_v1 import inspect, tree_oid

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/publish-fx-quant-v2.yml"
A = "a" * 40
B = "b" * 40


class V2PublicationTreeTests(unittest.TestCase):
    def test_identical_complete_subtrees_do_not_write(self):
        observed = []
        def resolve(ref):
            observed.append(ref)
            return A
        result = inspect(resolve)
        self.assertEqual(observed, ["origin/main", "origin/gh-pages"])
        self.assertEqual(result["status"], "NO_V2_BRANCH_WRITE_NEEDED")
        self.assertFalse(result["publish_needed"])
        self.assertFalse(result["public_delivery_certified"])
        self.assertTrue(result["branch_parity_only_not_public_http"])

    def test_any_changed_nested_asset_requires_publication(self):
        result = inspect(lambda ref: A if ref == "origin/main" else B)
        self.assertTrue(result["publish_needed"])
        self.assertEqual(result["status"], "V2_BRANCH_WRITE_REQUIRED")

    def test_missing_or_invalid_evidence_fails_closed(self):
        for value in ("", None, "0" * 8, "no-proof", "Z" * 40):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    inspect(lambda ref, value=value: A if ref == "origin/main" else value)

    def test_tree_oid_rejects_unexpected_reference(self):
        with self.assertRaisesRegex(ValueError, "unexpected Git ref"):
            tree_oid("HEAD")

    def test_live_workflow_safely_guards_all_heavy_steps(self):
        s = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("queue: max", s)
        self.assertIn("cancel-in-progress: false", s)
        self.assertIn("id: v2-tree", s)
        self.assertIn(
            "python3 validation/publishing/check_fxv2_publication_tree_v1.py --github-output",
            s)
        for name in (
            "Wait until preceding official Pages build/deployment has finished",
            "Re-fetch the latest approved main after deployment queue wait",
            "Publish only site/fx-quant-v2 without altering V10 or any other path",
        ):
            section = s.split(f"      - name: {name}\n", 1)[1].split("\n      - name:", 1)[0]
            self.assertIn(
                "if: steps.v2-tree.outputs.publish_needed == 'true'", section, name)
        self.assertIn("git checkout --detach origin/main", s)
        self.assertIn('git add -A -- site/fx-quant-v2', s)
        self.assertIn("git push origin HEAD:gh-pages", s)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", s)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
