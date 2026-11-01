#!/usr/bin/env python3
"""Prevent overlapping and feedback-loop writes to ESTIMATED_RESIDUAL_GAPS."""
from __future__ import annotations
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = "residual-proxy-shared-writers-v1"
JOBS = {
    "CHF": ".github/workflows/chf-residual-proxy-refresh-v1.yml",
    "JPY": ".github/workflows/jpy-reserve-balances-proxy-refresh-v1.yml",
    "Brent": ".github/workflows/brent-market-proxy-refresh-v1.yml",
    "Gold": ".github/workflows/gold-secondary-market-proxy-refresh-v1.yml",
}

class ResidualSharedWriterTests(unittest.TestCase):
    def test_one_production_queue_and_existing_schedules(self):
        for key, path in JOBS.items():
            with self.subTest(job=key):
                s = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn("  group:", s)
                self.assertIn(SHARED, s)
                self.assertIn("  queue: max", s)
                self.assertIn("  cancel-in-progress: false", s)
                self.assertIn("workflow_dispatch:", s)
                self.assertRegex(s, r"(?m)^    - cron: '")
                self.assertIn("contents: write", s)
                self.assertIn("ESTIMATED_RESIDUAL_GAPS.json", s)
        gold = (ROOT / JOBS["Gold"]).read_text(encoding="utf-8")
        brent = (ROOT / JOBS["Brent"]).read_text(encoding="utf-8")
        self.assertIn("residual-proxy-gold-pr-{0}", gold)
        self.assertIn("residual-proxy-brent-pr-{0}", brent)
        for s in (gold, brent):
            self.assertIn("github.event_name == 'pull_request'", s)

    def test_shared_json_changes_do_not_retrigger_three_sources(self):
        for key in ("CHF", "JPY", "Brent"):
            with self.subTest(job=key):
                s = (ROOT / JOBS[key]).read_text(encoding="utf-8")
                block = s.split("  push:", 1)[1].split("  schedule:", 1)[0]
                self.assertNotIn("- live_data/sections/ESTIMATED_RESIDUAL_GAPS.json", block)
                self.assertIn("validation/estimated/", block)
                self.assertIn("  schedule:", s)
                self.assertIn("git push origin HEAD:main", s)
                self.assertIn("REMOTE_SHA", s)

    def test_main_only_and_pages_owner_unchanged(self):
        for key, path in JOBS.items():
            with self.subTest(job=key):
                s = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn("live_data/sections/ESTIMATED_RESIDUAL_GAPS.json", s)
                guard = "github.ref == 'refs/heads/main'" if key == "Gold" else "github.ref_name == 'main'"
                self.assertIn(guard, s)
                self.assertIn("git push", s)
        pub = (ROOT / ".github/workflows/publish-dashboard-pages-v1.yml").read_text(encoding="utf-8")
        for key in JOBS:
            self.assertIn(f"'{key} ", pub)
        self.assertIn("verify_pages_http_delivery_v1.py", pub)
        self.assertIn("ESTIMATED_RESIDUAL_GAPS.json", pub)

if __name__ == "__main__":
    unittest.main()
