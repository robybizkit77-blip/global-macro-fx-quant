#!/usr/bin/env python3
"""Adversarial tests for the 32-part preview HTTP/Git-byte proof; no network."""
from __future__ import annotations

import datetime as dt
import unittest
from pathlib import Path
from unittest.mock import patch

from verify_control_room_v10_preview_parts_v1 import (
    BASE, MANIFEST_PATH, PARTS, SCHEMA, evaluate, git_blob, load_manifest,
    verify_parts,
)

UTC = dt.timezone.utc
NOW = dt.datetime.fromisoformat("2026-10-27T06:58:00Z")


def fixtures():
    bodies = {p: (p + "<script>frozen-design-only</script>").encode("utf-8")
              for p in PARTS}
    meta = {p.rsplit("/", 1)[-1]: {
        "git_blob_sha1": git_blob(b), "bytes": len(b)
    } for p, b in bodies.items()}
    manifest = {"files": meta}
    branch = {p: git_blob(body) for p, body in bodies.items()}
    downloaded = {p: {"status": 200, "data": body} for p, body in bodies.items()}
    return manifest, branch, downloaded


class FrozenPreview32PartTests(unittest.TestCase):
    def test_frozen_manifest_identifies_exactly_32_original_ghpages_parts(self):
        original = load_manifest(Path("."))
        self.assertEqual(original["schema"], SCHEMA)
        self.assertEqual(len(original["files"]), 32)
        self.assertEqual(original["files"]["part-00.txt"]["bytes"], 200009)
        self.assertGreater(original["files"]["part-31.txt"]["bytes"], 1000)
        self.assertEqual(PARTS[0], BASE + "part-00.txt")
        self.assertEqual(PARTS[-1], BASE + "part-31.txt")
        self.assertFalse((Path(".") / PARTS[0]).exists(),
                         "These design files are owned by gh-pages, NOT main")

    def test_all_32_verified_in_public_http(self):
        m, b, d = fixtures()
        proof = evaluate(m, b, d, NOW)
        self.assertEqual(proof["status"], "PASS")
        self.assertEqual(proof["verified_count"], 32)
        self.assertEqual(len(proof["checks"]), 32)
        self.assertEqual(proof["conclusion"], "ALL_PUBLIC_FILES_MATCH")
        self.assertTrue(all(x["http_200_and_sha256_match"] for x in proof["checks"]))
        self.assertTrue(all(x["expected_sha256"] == x["public_sha256"]
                            and len(x["public_sha256"]) == 64
                            for x in proof["checks"]))

    def test_missing_middle_part_fails_even_if_loader_and_part0_exist(self):
        m, b, d = fixtures()
        del d[PARTS[17]]
        proof = evaluate(m, b, d, NOW)
        self.assertEqual(proof["status"], "FAIL")
        self.assertEqual(proof["verified_count"], 31)
        self.assertFalse(proof["checks"][17]["http_200_and_sha256_match"])

    def test_changed_identical_length_fails_frozen_blob_pin(self):
        m, b, d = fixtures()
        original = d[PARTS[31]]["data"]
        d[PARTS[31]]["data"] = original[:-1] + bytes([original[-1] ^ 1])
        self.assertEqual(len(original), len(d[PARTS[31]]["data"]))
        proof = evaluate(m, b, d, NOW)
        self.assertEqual(proof["status"], "FAIL")
        self.assertNotEqual(proof["checks"][-1]["observed_git_blob_sha1"],
                            proof["checks"][-1]["expected_git_blob_sha1"])

    def test_ghpages_changed_while_cdn_still_old_also_fails(self):
        m, b, d = fixtures()
        b[PARTS[8]] = "f" * 40
        self.assertEqual(evaluate(m, b, d, NOW)["status"], "FAIL")

    def test_extra_branch_parts_cannot_be_ignored(self):
        m, b, d = fixtures()
        b[BASE + "part-32.txt"] = "f" * 40
        self.assertEqual(evaluate(m, b, d, NOW)["status"], "FAIL")

    def test_http404_on_one_file_never_succeeds(self):
        m, b, d = fixtures()
        d[PARTS[0]]["status"] = 404
        self.assertEqual(evaluate(m, b, d, NOW)["verified_count"], 31)

    def test_unaware_observation_time_rejected(self):
        m, b, d = fixtures()
        with self.assertRaises(ValueError):
            evaluate(m, b, d, dt.datetime(2026,10,27,7,59))

    def test_readonly_main_loader_must_still_fetch_all_32(self):
        # The frozen manifest does not license an unrelated truncated loader.
        code=(Path(".") / "site/control-room-preview/index.html").read_text()
        for marker in ("Array.from({length:32}", "paths.map(async path",
                       "if(!response.ok)throw"):
            self.assertIn(marker,code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
