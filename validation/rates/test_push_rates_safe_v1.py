#!/usr/bin/env python3
"""Offline Git integration tests: moving-main publish never overwrites Rates."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from validation.rates.push_rates_safe_v1 import (
    RATES_DATA, RATES_METADATA, inspect_new_main_files, publish, verify_local_scope,
)

ROOT = Path(__file__).resolve().parents[2]
OTHER = "live_data/sections/MACRO_EXAMPLE.json"


def git(folder: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=folder, capture_output=True,
                          text=True, check=True).stdout.strip()

def generator(folder: Path, script: str, *args: str) -> dict:
    result = subprocess.run([sys.executable, f"validation/{script}", *args],
                            cwd=folder, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


class RatesSafePublishTests(unittest.TestCase):
    def test_remote_rates_source_overlap_is_fail_closed(self):
        for name in (
            RATES_DATA, RATES_METADATA,
        ):
            with self.subTest(file=name):
                with self.assertRaisesRegex(RuntimeError, "FAIL_CLOSED"):
                    inspect_new_main_files({name})

    def test_non_rates_changes_are_allowed_without_a_force_push(self):
        inspect_new_main_files({"docs/notes.md", "site/fx-quant-v2/index.html",
                                "live_data/manifest.v2.json", "payload/part-15.txt"})
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

    def setup_repos(self, root: Path, *, shared_runtime=False):
        remote, seed, writer, producer = (
            root / "remote.git", root / "seed", root / "writer", root / "producer"
        )
        remote.mkdir()
        git(root, "init", "--bare", str(remote))
        seed.mkdir()
        git(seed, "init", "-b", "main")
        git(seed, "config", "user.name", "Test")
        git(seed, "config", "user.email", "test@example.invalid")
        p = seed / RATES_DATA
        p.parent.mkdir(parents=True)
        p.write_text("source-date=2026-11-04\n")
        if shared_runtime:
            self.seed_shared_runtime(seed)
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

    def seed_shared_runtime(self, seed: Path) -> None:
        (seed / "validation").mkdir()
        for script in ("update_live_direct_section.py", "update_live_derived_sections.py",
                       "build_live_manifest_v2.py", "rebuild_live_data_runtime.py"):
            shutil.copyfile(ROOT / "validation" / script, seed / "validation" / script)
        (seed / RATES_DATA).write_text('{"rates":"old"}', encoding="utf-8")
        (seed / OTHER).write_text('{"macro":"old"}', encoding="utf-8")
        metadata = (ROOT / RATES_METADATA).read_text()
        (seed / RATES_METADATA).write_text(metadata)
        (seed / "live_data/manifest.json").write_text(json.dumps({
            "sections": [{"key": Path(path).stem, "file": Path(path).name}
                         for path in (RATES_DATA, OTHER, RATES_METADATA)]
        }))
        payload = seed / "payload"
        payload.mkdir()
        for i in range(16):
            (payload / f"part-{i:02d}.txt").write_text("\n")
        (payload / "part-00.txt").write_text(
            'window.__GMFQ_DATA.NATIVE_RATES_DATA={"rates":"old"};\n'
            'window.__GMFQ_DATA.MACRO_EXAMPLE={"macro":"old"};\n'
        )
        (payload / "part-15.txt").write_text(
            "window.__GMFQ_DATA.RATES_AUDIT_METADATA=" + metadata.strip() + ";\n"
        )
        generator(seed, "build_live_manifest_v2.py", "--write", "live_data/manifest.v2.json")

    def test_shared_runtime_rebuild_keeps_the_other_writer_and_exact_rates(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            remote, writer, producer = self.setup_repos(root, shared_runtime=True)
            base = git(producer, "rev-parse", "HEAD")
            new_rates = root / "rates.json"
            new_rates.write_text('{"rates":"validated update"}')
            generator(producer, "update_live_direct_section.py", "--section",
                      "NATIVE_RATES_DATA", "--replacement", str(new_rates), "--apply")
            metadata = json.loads((producer / RATES_METADATA).read_bytes())
            next_audit = date.fromisoformat(metadata["audit_date"]) + timedelta(days=1)
            metadata["audit_date"] = next_audit.isoformat()
            new_metadata = root / "metadata.json"
            new_metadata.write_text(json.dumps(metadata))
            generator(producer, "update_live_derived_sections.py",
                      "--rates", str(new_metadata), "--apply")
            generator(producer, "build_live_manifest_v2.py", "--write", "live_data/manifest.v2.json")
            git(producer, "add", ".")
            git(producer, "commit", "-m", "validated rates and metadata")
            candidate_sha = git(producer, "rev-parse", "HEAD")
            candidate_metadata = (producer / RATES_METADATA).read_bytes()

            new_macro = root / "macro.json"
            new_macro.write_text('{"macro":"latest concurrent source"}')
            generator(writer, "update_live_direct_section.py", "--section",
                      "MACRO_EXAMPLE", "--replacement", str(new_macro), "--apply")
            generator(writer, "build_live_manifest_v2.py", "--write", "live_data/manifest.v2.json")
            git(writer, "add", ".")
            git(writer, "commit", "-m", "independent macro refresh in the same payload")
            git(writer, "push", "origin", "HEAD:main")
            writer_sha = git(writer, "rev-parse", "HEAD")

            def reject_runtime(_):
                raise RuntimeError("invalid runtime receipt")

            with self.assertRaisesRegex(RuntimeError, "invalid runtime receipt"):
                publish(base_sha=base, mode="rates", cwd=producer, validate=reject_runtime)
            self.assertEqual(git(producer, "rev-parse", "HEAD"), candidate_sha)
            self.assertEqual(git(remote, "rev-parse", "main"), writer_sha)
            self.assertEqual(git(producer, "status", "--porcelain"), "")

            def validate_runtime(folder):
                receipt = generator(folder, "rebuild_live_data_runtime.py", "--verify-only")
                self.assertEqual(receipt["status"], "PASS")
                self.assertTrue(receipt["noop_roundtrip_byte_identical"])

            result = publish(base_sha=base, mode="rates", cwd=producer, validate=validate_runtime)
            self.assertEqual(result["status"], "RATES_SAFE_PUSH_CONFIRMED")
            self.assertTrue(result["shared_runtime_rebuilt"])
            self.assertFalse(result["force_push"])
            self.assertIn(RATES_METADATA, result["changed_files"])
            git(writer, "pull", "--ff-only", "origin", "main")
            self.assertEqual((writer / OTHER).read_bytes(), new_macro.read_bytes())
            self.assertEqual((writer / RATES_DATA).read_bytes(), new_rates.read_bytes())
            self.assertEqual((writer / RATES_METADATA).read_bytes(), candidate_metadata)
            part = (writer / "payload/part-00.txt").read_bytes()
            self.assertIn(new_macro.read_bytes(), part)
            self.assertIn(new_rates.read_bytes(), part)

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

    def test_two_collectors_with_identical_official_close_are_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            remote, writer, producer = self.setup_repos(Path(td))
            base = git(producer, "rev-parse", "HEAD")
            same = "source-date=2026-11-18; 2Y=4.80; 10Y=5.07\n"
            canonical = "live_data/sections/NATIVE_RATES_DATA.json"
            for checkout in (writer, producer):
                (checkout / canonical).write_text(same)
                git(checkout, "add", canonical)
                git(checkout, "commit", "-m", "same independently verified close")
            git(writer, "push", "origin", "HEAD:main")
            first_writer_sha = git(writer, "rev-parse", "HEAD")
            result = publish(base_sha=base, mode="rates", cwd=producer,
                             validate=lambda _: None, sleep=lambda _: None)
            self.assertEqual(result["status"], "RATES_ALREADY_PUBLISHED_IDENTICAL")
            self.assertTrue(result["canonical_blob_identical"])
            self.assertFalse(result["force_push"])
            self.assertEqual(result["published_commit"], first_writer_sha)
            git(writer, "fetch", "origin", "main")
            self.assertEqual(git(writer, "rev-parse", "origin/main"), first_writer_sha)
            self.assertEqual((writer / canonical).read_text(), same)

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
