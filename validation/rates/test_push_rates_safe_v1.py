#!/usr/bin/env python3
"""Offline Git integration tests: moving-main publish never overwrites Rates."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from validation.rates.push_rates_safe_v1 import (
    inspect_new_main_files, publish, verify_local_scope,
)


def git(folder: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=folder, capture_output=True,
                          text=True, check=True).stdout.strip()


class RatesSafePublishTests(unittest.TestCase):
    def test_remote_file_overlap_is_fail_closed(self):
        for name in (
            "live_data/sections/NATIVE_RATES_DATA.json",
            "live_data/manifest.v2.json",
            "payload/part-15.txt",
        ):
            with self.subTest(file=name):
                with self.assertRaisesRegex(RuntimeError, "FAIL_CLOSED"):
                    inspect_new_main_files({name})

    def test_non_rates_changes_are_allowed_without_a_force_push(self):
        inspect_new_main_files({"docs/notes.md", "site/fx-quant-v2/index.html"})
        verify_local_scope(
            {"live_data/sections/NATIVE_RATES_DATA.json",
             "live_data/manifest.v2.json"}, "rates")

    def test_scope_refuses_publishing_unexpected_files(self):
        with self.assertRaisesRegex(RuntimeError, "SCOPE_VIOLATION"):
            verify_local_scope(
                {"site/fx-quant-v2/tassi.html",
                 "live_data/sections/NATIVE_RATES_DATA.json"}, "rates")
        with self.assertRaisesRegex(RuntimeError, "CANONICAL_CHANGE_MISSING"):
            verify_local_scope({"live_data/manifest.v2.json"}, "rates")

    def setup_repos(self, root: Path):
        remote, seed, writer, producer = (
            root / "remote.git", root / "seed", root / "writer", root / "producer"
        )
        remote.mkdir()
        git(root, "init", "--bare", str(remote))
        seed.mkdir()
        git(seed, "init", "-b", "main")
        git(seed, "config", "user.name", "Test")
        git(seed, "config", "user.email", "test@example.invalid")
        p = seed / "live_data/sections/NATIVE_RATES_DATA.json"
        p.parent.mkdir(parents=True)
        p.write_text("source-date=2026-11-04\n")
        (seed / "docs").mkdir()
        (seed / "docs/info.md").write_text("old notes\n")
        git(seed, "add", ".")
        git(seed, "commit", "-m", "baseline")
        git(seed, "remote", "add", "origin", str(remote))
        git(seed, "push", "origin", "HEAD:main")
        for target in (writer, producer):
            git(root, "clone", "-b", "main", str(remote), str(target))
            git(target, "config", "user.name", "Test")
            git(target, "config", "user.email", "test@example.invalid")
        return remote, writer, producer

    def test_unrelated_new_commit_is_preserved_and_rates_are_pushed(self):
        with tempfile.TemporaryDirectory() as td:
            remote, writer, producer = self.setup_repos(Path(td))
            base = git(producer, "rev-parse", "HEAD")
            source = producer / "live_data/sections/NATIVE_RATES_DATA.json"
            source.write_text("source-date=2026-11-05\n")
            git(producer, "add", ".")
            git(producer, "commit", "-m", "validated rates")
            # The production audit creates untracked evidence. Such files are
            # not staged, do not enter a push, and must not block the retry.
            scratch = producer / "local-audit-evidence.json"
            scratch.write_text('{"status":"PASS"}\n')
            (writer / "docs/info.md").write_text("new notes\n")
            git(writer, "add", ".")
            git(writer, "commit", "-m", "unrelated docs")
            git(writer, "push", "origin", "HEAD:main")
            result = publish(base_sha=base, mode="rates", cwd=producer,
                             validate=lambda _: None, sleep=lambda _: None)
            self.assertEqual(result["status"], "RATES_SAFE_PUSH_CONFIRMED")
            self.assertTrue(result["disjoint_remote_rebase"])
            self.assertFalse(result["force_push"])
            self.assertTrue(scratch.exists())
            self.assertNotIn("local-audit-evidence.json", result["changed_files"])
            git(producer, "fetch", "origin", "main")
            self.assertEqual(source.read_text(), "source-date=2026-11-05\n")
            git(writer, "pull", "--ff-only", "origin", "main")
            self.assertEqual((writer / "docs/info.md").read_text(), "new notes\n")
            self.assertEqual((writer / "live_data/sections/NATIVE_RATES_DATA.json").read_text(),
                             "source-date=2026-11-05\n")

    def test_overlapping_remote_rates_never_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            remote, writer, producer = self.setup_repos(Path(td))
            base = git(producer, "rev-parse", "HEAD")
            source = producer / "live_data/sections/NATIVE_RATES_DATA.json"
            source.write_text("producer-candidate\n")
            git(producer, "add", ".")
            git(producer, "commit", "-m", "validated producer candidate")
            remote_rates = writer / "live_data/sections/NATIVE_RATES_DATA.json"
            remote_rates.write_text("newer-official-source\n")
            git(writer, "add", ".")
            git(writer, "commit", "-m", "competing source")
            git(writer, "push", "origin", "HEAD:main")
            with self.assertRaisesRegex(RuntimeError, "SOURCE_CHANGED_FAIL_CLOSED"):
                publish(base_sha=base, mode="rates", cwd=producer,
                        validate=lambda _: None, sleep=lambda _: None)
            git(writer, "fetch", "origin", "main")
            self.assertEqual(remote_rates.read_text(), "newer-official-source\n")


if __name__ == "__main__":
    unittest.main()
