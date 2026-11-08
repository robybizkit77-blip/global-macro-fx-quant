#!/usr/bin/env python3
"""Adversarial, side-effect-free tests for Pages Control Room no-op gating."""
from __future__ import annotations

import unittest
from pathlib import Path

from validation.publishing.check_dashboard_pages_mirror_noop_v1 import (
    WORKFLOW, copied_paths, inspect,
)


class DashboardPagesMirrorNoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.paths = copied_paths(cls.workflow)
        cls.complete = {path: "a" * 40 for path in cls.paths}

    def test_real_scope_contains_all_copied_assets(self):
        paths = set(self.paths)
        self.assertGreaterEqual(len(paths), 55)
        for path in (
            "index.html", "payload/part-00.txt", "payload/part-15.txt",
            "dashboard/pairs-operational-v1.js",
            "dashboard/ois-operational-monitor-v1.js",
            "live_data/sections/OIS_OPERATIONAL_VIEW.json",
            "live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json",
            "live_data/sections/CB_PRICING_ESTIMATED_LIVE_QUOTES.json",
            "live_data/manifest.v2.json",
        ):
            self.assertIn(path, paths)

    def test_identical_branch_files_are_only_a_noop_not_http_proof(self):
        result = inspect(self.workflow, self.complete, dict(self.complete))
        self.assertEqual(result["status"], "PUBLICATION_BRANCH_NOOP")
        self.assertFalse(result["publish_needed"])
        self.assertFalse(result["public_http_certified"])
        self.assertTrue(result["branch_parity_only_not_public_http"])

    def test_change_in_any_published_file_requires_publish(self):
        for path in self.paths:
            with self.subTest(path=path):
                pages = dict(self.complete)
                pages[path] = "b" * 40
                result = inspect(self.workflow, self.complete, pages)
                self.assertTrue(result["publish_needed"])
                self.assertEqual(result["different_assets"], 1)

    def test_missing_pages_asset_requires_publish(self):
        pages = dict(self.complete)
        pages.pop("live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json")
        result = inspect(self.workflow, self.complete, pages)
        self.assertTrue(result["publish_needed"])

    def test_missing_source_fails_closed(self):
        source = dict(self.complete)
        source.pop("dashboard/pairs-operational-v1.js")
        with self.assertRaisesRegex(ValueError, "MAIN_COPIED_ASSET_MISSING"):
            inspect(self.workflow, source, self.complete)

    def test_new_copy_command_cannot_silently_bypass_noop(self):
        altered = self.workflow.replace(
            "          cp index.html /tmp/gmfq-pages/index.html",
            "          cp index.html /tmp/gmfq-pages/index.html\n"
            "          cp dashboard/new-ui.js /tmp/gmfq-pages/dashboard/new-ui.js",
        )
        with self.assertRaisesRegex(ValueError, "Unlisted Pages copy command"):
            copied_paths(altered)

    def test_removed_copy_scope_is_fail_closed(self):
        altered = self.workflow.replace(
            "cp live_data/manifest.v2.json /tmp/gmfq-pages/live_data/manifest.v2.json",
            "echo skipped-manifest",
        )
        with self.assertRaisesRegex(ValueError, "copy scope"):
            copied_paths(altered)

    def test_production_workflow_keeps_lease_and_public_http_gate(self):
        wf = self.workflow
        self.assertIn("queue: max", wf)
        self.assertIn("cancel-in-progress: false", wf)
        self.assertIn("id: pages-mirror", wf)
        self.assertIn("check_dashboard_pages_mirror_noop_v1.py --github-output", wf)
        self.assertIn("git checkout --detach origin/main", wf)
        self.assertIn("assert_source_main_current", wf)
        self.assertIn("git push --force-with-lease=", wf)
        self.assertIn("Verify public Pages HTTP delivery after bounded CDN propagation", wf)
        self.assertIn("verify_pages_http_delivery_v1.py", wf)
        self.assertIn("PAGES_DASHBOARD_BRANCH_PARITY", (
            Path(__file__).parent / "check_dashboard_pages_mirror_noop_v1.py"
        ).read_text(encoding="utf-8"))
        for name in (
            "Verify current dashboard runtime before publication",
            "Publish dashboard runtime and operational assets to gh-pages with lease",
            "Ensure actual Pages build follows automated gh-pages push",
            "Verify published files against validated main",
        ):
            section = wf.split(f"      - name: {name}\n", 1)[1].split("\n      - name:", 1)[0]
            self.assertIn("steps.pages-mirror.outputs.publish_needed == 'true'", section)
        for name in (
            "Block incomplete morning sources before any Pages write",
            "Verify public Pages HTTP delivery after bounded CDN propagation",
        ):
            section = wf.split(f"      - name: {name}\n", 1)[1].split("\n      - name:", 1)[0]
            self.assertNotIn("steps.pages-mirror.outputs.publish_needed", section)


if __name__ == "__main__":
    unittest.main(verbosity=2)
