"""Exercise Calendar/News archive persistence against a real local Git remote.

No network access; regression proves unrelated upstream commits can be
rebased without force and overlapping macro/archive changes fail closed.
"""
from __future__ import annotations

import tempfile
import unittest
import subprocess
from pathlib import Path

from validation.macro.persist_calendar_news_safe_v12 import persist

CALENDAR = "live_data/sections/CALENDAR_OPERATIONAL_VIEW.json"
LEDGER = "validation/macro/MACRO_BLS_CPI_EXACT_ACTUAL_FIRST_SEEN_V10.jsonl"
MANAGED = (CALENDAR, LEDGER)


def run(cwd, *args, check=True):
    p = subprocess.run(
        ["git", *args], cwd=cwd, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and p.returncode:
        raise AssertionError(
            f"git {args} failed: stdout={p.stdout}, stderr={p.stderr}")
    return p.stdout.strip()


def write(repo, name, text):
    path = Path(repo) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class CalendarConcurrentPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        root = Path(self.t.name)
        self.origin = root / "origin.git"
        self.seed = root / "seed"
        self.a = root / "calendar"
        self.b = root / "other-worker"
        root.mkdir(parents=True, exist_ok=True)
        run(root, "init", "--bare", str(self.origin))
        run(root, "init", "-b", "main", str(self.seed))
        run(self.seed, "config", "user.name", "Test")
        run(self.seed, "config", "user.email", "test@example.com")
        write(self.seed, "README.md", "baseline\n")
        write(self.seed, CALENDAR, "base-calendar\n")
        write(self.seed, LEDGER, "")
        run(self.seed, "add", ".")
        run(self.seed, "commit", "-m", "initial")
        run(self.seed, "remote", "add", "origin", str(self.origin))
        run(self.seed, "push", "-u", "origin", "main")
        run(self.origin, "symbolic-ref", "HEAD", "refs/heads/main")
        run(root, "clone", "--branch", "main", str(self.origin), str(self.a))
        run(root, "clone", "--branch", "main", str(self.origin), str(self.b))
        for path in (self.a, self.b):
            run(path, "config", "user.name", "Test")
            run(path, "config", "user.email", "test@example.com")

    def push_remote(self, filename, text):
        write(self.b, filename, text)
        run(self.b, "add", filename)
        run(self.b, "commit", "-m", "outside writer")
        run(self.b, "push", "origin", "HEAD:main")

    def assert_remote(self, name, expected):
        got = run(self.a, "show", "origin/main:" + name)
        # Fetch before reading remote, unless the tested function already did.
        self.assertEqual(got, expected.strip())

    def test_no_change_is_noop(self):
        result = persist(self.a, managed=MANAGED)
        self.assertEqual(result, {"status": "NO_TRACKED_CHANGES", "attempts": 0})

    def test_one_uncontested_commit_persists(self):
        write(self.a, LEDGER, '{"metric_id":"CPI"}\n')
        result = persist(self.a, managed=MANAGED)
        self.assertEqual(result["status"], "PERSISTED")
        self.assertEqual(result["attempts"], 1)
        run(self.a, "fetch", "origin", "main")
        self.assert_remote(LEDGER, '{"metric_id":"CPI"}')

    def test_unrelated_main_movement_retries_and_preserves_both_writers(self):
        write(self.a, LEDGER, '{"metric_id":"CPI"}\n')
        self.push_remote("README.md", "remote updated independently\n")
        result = persist(self.a, managed=MANAGED)
        self.assertEqual(result["status"], "PERSISTED")
        self.assertGreaterEqual(result["attempts"], 2)
        self.assertTrue(result["rebased_onto_latest_main"])
        run(self.a, "fetch", "origin", "main")
        self.assert_remote(LEDGER, '{"metric_id":"CPI"}')
        self.assert_remote("README.md", "remote updated independently")

    def test_other_managed_file_moves_but_is_not_locally_changed(self):
        write(self.a, LEDGER, '{"metric_id":"CPI"}\n')
        self.push_remote(CALENDAR, "newer calendar published elsewhere\n")
        result = persist(self.a, managed=MANAGED)
        self.assertEqual(result["status"], "PERSISTED")
        run(self.a, "fetch", "origin", "main")
        self.assert_remote(LEDGER, '{"metric_id":"CPI"}')
        self.assert_remote(CALENDAR, "newer calendar published elsewhere")

    def test_same_calendar_file_conflict_fails_closed_no_remote_overwrite(self):
        write(self.a, CALENDAR, "local-calendar-older\n")
        self.push_remote(CALENDAR, "newer-calendar-remote\n")
        with self.assertRaisesRegex(RuntimeError,
                                    "REMOTE_MANAGED_FILES_MOVED_FAIL_CLOSED"):
            persist(self.a, managed=MANAGED)
        self.assertEqual(
            run(self.b, "show", "HEAD:"+CALENDAR), "newer-calendar-remote")

    def test_same_immutable_ledger_conflict_fails_closed(self):
        write(self.a, LEDGER, "first-observed-runner-A\n")
        self.push_remote(LEDGER, "first-observed-runner-B\n")
        with self.assertRaisesRegex(RuntimeError,
                                    "REMOTE_MANAGED_FILES_MOVED_FAIL_CLOSED"):
            persist(self.a, managed=MANAGED)
        self.assertEqual(
            run(self.b, "show", "HEAD:"+LEDGER), "first-observed-runner-B")

    def test_unexpected_file_modification_refused(self):
        write(self.a, "README.md", "do not publish this\n")
        write(self.a, LEDGER, "important\n")
        with self.assertRaisesRegex(ValueError, "UNEXPECTED_WORKTREE_CHANGE"):
            persist(self.a, managed=MANAGED)
        self.assertEqual(run(self.a, "log", "-1", "--format=%s"), "initial")

    def test_requires_valid_paths_and_retry_limit(self):
        with self.assertRaises(ValueError):
            persist(self.a, managed=("../outside",))
        with self.assertRaises(ValueError):
            persist(self.a, managed=MANAGED, max_attempts=11)


if __name__=="__main__":
    unittest.main()
