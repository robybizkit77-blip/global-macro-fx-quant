"""Macro runtime publication must survive independent writers, never merge overlapping data.

Tests use a real isolated Git remote; no production network or publisher values.
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from validation.macro.persist_calendar_news_safe_v12 import persist

MACRO = "live_data/sections/MACRO_SERIES.json"
HEAT = "live_data/sections/MACRO_THERMOMETER_DATA.json"
MANIFEST = "live_data/manifest.v2.json"
PART0 = "payload/part-00.txt"
PART1 = "payload/part-01.txt"
MANAGED = (MACRO, HEAT, MANIFEST, PART0, PART1)
MESSAGE = "Refresh daily Macro runtime from official sources"


def git(folder, *args):
    p = subprocess.run(["git", *args], cwd=folder, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise AssertionError(f"git {args!r} failed: {p.stderr}")
    return p.stdout.strip()


def put(folder, path, content):
    target = Path(folder) / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


class MacroConcurrentWriterTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.origin = root / "origin.git"
        seed = root / "seed"
        self.macro = root / "macro"
        self.other = root / "other"
        git(root, "init", "--bare", str(self.origin))
        git(root, "init", "-b", "main", str(seed))
        git(seed, "config", "user.name", "Test")
        git(seed, "config", "user.email", "test@example.com")
        put(seed, "README.md", "baseline\n")
        for name in MANAGED:
            put(seed, name, "baseline " + name + "\n")
        git(seed, "add", ".")
        git(seed, "commit", "-m", "initial")
        git(seed, "remote", "add", "origin", str(self.origin))
        git(seed, "push", "-u", "origin", "main")
        git(self.origin, "symbolic-ref", "HEAD", "refs/heads/main")
        git(root, "clone", "--branch", "main", str(self.origin), str(self.macro))
        git(root, "clone", "--branch", "main", str(self.origin), str(self.other))
        for folder in (self.macro, self.other):
            git(folder, "config", "user.name", "Test")
            git(folder, "config", "user.email", "test@example.com")

    def other_commit(self, filename, content):
        put(self.other, filename, content)
        git(self.other, "add", "--", filename)
        git(self.other, "commit", "-m", "independent writer")
        git(self.other, "push", "origin", "HEAD:main")

    def remote_file(self, filename):
        git(self.macro, "fetch", "origin", "main")
        return git(self.macro, "show", "origin/main:" + filename)

    def test_independent_main_advance_preserves_both_updates_without_force(self):
        put(self.macro, MACRO, "new certified macro series\n")
        put(self.macro, HEAT, "new certified heatmap\n")
        self.other_commit("README.md", "new independent news\n")
        receipt = persist(self.macro, managed=MANAGED, max_attempts=4,
                          commit_message=MESSAGE)
        self.assertEqual(receipt["status"], "PERSISTED")
        self.assertGreaterEqual(receipt["attempts"], 2)
        self.assertTrue(receipt["rebased_onto_latest_main"])
        self.assertEqual(self.remote_file(MACRO), "new certified macro series")
        self.assertEqual(self.remote_file(HEAT), "new certified heatmap")
        self.assertEqual(self.remote_file("README.md"), "new independent news")
        self.assertEqual(git(self.macro, "log", "-1", "--format=%s"), MESSAGE)

    def test_overlap_on_macro_series_fails_closed(self):
        put(self.macro, MACRO, "local older series\n")
        self.other_commit(MACRO, "remote newer series\n")
        with self.assertRaisesRegex(RuntimeError,
                                    "REMOTE_MANAGED_FILES_MOVED_FAIL_CLOSED"):
            persist(self.macro, managed=MANAGED, commit_message=MESSAGE)
        self.assertEqual(self.remote_file(MACRO), "remote newer series")

    def test_overlap_on_payload_fails_closed(self):
        put(self.macro, PART1, "stale runtime payload\n")
        self.other_commit(PART1, "new runtime payload\n")
        with self.assertRaisesRegex(RuntimeError,
                                    "REMOTE_MANAGED_FILES_MOVED_FAIL_CLOSED"):
            persist(self.macro, managed=MANAGED, commit_message=MESSAGE)
        self.assertEqual(self.remote_file(PART1), "new runtime payload")

    def test_never_commits_unexpected_or_untested_changes(self):
        put(self.macro, MACRO, "candidate macro\n")
        put(self.macro, "README.md", "unexpected untested write\n")
        with self.assertRaisesRegex(ValueError, "UNEXPECTED_WORKTREE_CHANGE"):
            persist(self.macro, managed=MANAGED, commit_message=MESSAGE)
        self.assertEqual(self.remote_file(MACRO), "baseline " + MACRO)

    def test_noop_and_message_constraints(self):
        self.assertEqual(persist(self.macro, managed=MANAGED,
                                 commit_message=MESSAGE)["status"],
                         "NO_TRACKED_CHANGES")
        put(self.macro, MACRO, "candidate\n")
        for invalid in ("", "bad\ncommit", "bad\rcommit"):
            with self.subTest(invalid=repr(invalid)), self.assertRaises(ValueError):
                persist(self.macro, managed=MANAGED, commit_message=invalid)


if __name__ == "__main__":
    unittest.main()
