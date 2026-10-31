#!/usr/bin/env python3
"""Read-only PUBLIC HTTP proof for the 32 frozen Control Room v10 design parts.

The 32 originals are intentionally NOT in main; only gh-pages owns them.
The pinned design Git blob hashes below are a review/immutability boundary:
a gh-pages change alone does not authorize a new official design. Never
treat an HTTP 200 or an intact loader as proof that its 32 fetches succeeded.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

BASE = "site/control-room-preview/parts/"
PARTS = tuple(BASE + f"part-{i:02d}.txt" for i in range(32))
MANIFEST_PATH = Path("validation/publishing/control_room_v10_frozen_preview_parts_v1.json")
SCHEMA = "GMFQ_V10_FROZEN_PREVIEW_PART_BLOB_MANIFEST_V1"


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\x00" + data).hexdigest()


def load_manifest(root: Path) -> dict:
    d = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    expected = {f"part-{i:02d}.txt" for i in range(32)}
    if (d.get("schema") != SCHEMA or d.get("source_ref") != "gh-pages"
        or d.get("source_path") != BASE.rstrip("/") or d.get("automatic_promotion") is not False
        or not isinstance(d.get("files"), dict) or set(d["files"]) != expected):
        raise ValueError("V10_PREVIEW_MANIFEST_REJECTED: missing/extra original part")
    for name, row in d["files"].items():
        if (not isinstance(row, dict)
            or not isinstance(row.get("git_blob_sha1"), str)
            or re.fullmatch(r"[0-9a-f]{40}", row["git_blob_sha1"]) is None
            or type(row.get("bytes")) is not int
            or row["bytes"] < 1000):
            raise ValueError("V10_PREVIEW_MANIFEST_REJECTED: " + name)
    return d


def branch_parts(root: Path) -> dict:
    """Read only the actual branch tree. Git blob hashes cost no network reads."""
    out = subprocess.check_output(
        ["git", "ls-tree", "-r", "origin/gh-pages", "--", BASE.rstrip("/")],
        cwd=root, text=True, timeout=15
    )
    rows = {}
    for line in out.splitlines():
        left, sep, path = line.partition("\t")
        meta = left.split()
        if not sep or len(meta) != 3 or meta[1] != "blob" or path in rows:
            raise ValueError("V10_PREVIEW_GH_PAGES_TREE_REJECTED")
        rows[path] = meta[2]
    return rows


def evaluate(manifest: dict, branches: dict, downloads: dict,
             observed: dt.datetime) -> dict:
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("V10_PREVIEW_OBSERVATION_REQUIRES_AWARE_CLOCK")
    if not isinstance(downloads, dict) or not isinstance(branches, dict):
        raise ValueError("V10_PREVIEW_INVALID_SOURCE")
    files = manifest["files"]
    checks = []
    for path in PARTS:
        name = path.rsplit("/", 1)[-1]
        pinned = files[name]
        actual = downloads.get(path)
        if not isinstance(actual, dict):
            actual = {}
        data = actual.get("data")
        if not isinstance(data, bytes):
            data = None
        status = actual.get("status")
        local_sha = git_blob(data) if data is not None else None
        branch_match = branches.get(path) == pinned["git_blob_sha1"]
        passed = bool(
            branch_match and status == 200 and data is not None
            and len(data) == pinned["bytes"]
            and local_sha == pinned["git_blob_sha1"]
        )
        # A digest obtained from a verified frozen Git blob is authoritative.
        digest = hashlib.sha256(data).hexdigest() if data is not None else None
        checks.append({
            "path": path,
            "http_status": status,
            "http_200_and_sha256_match": passed,
            "expected_sha256": digest if passed else None,
            "public_sha256": digest,
            "expected_git_blob_sha1": pinned["git_blob_sha1"],
            "observed_git_blob_sha1": local_sha,
            "gh_pages_blob_matches_pinned": branch_match,
            "byte_length_matches_pinned": data is not None and len(data) == pinned["bytes"],
            "error": actual.get("error") if not passed else None,
        })
    all_ok = (set(branches) == set(PARTS)
              and len(checks) == 32 and all(x["http_200_and_sha256_match"] for x in checks))
    return {
        "schema": "GMFQ_V10_PUBLIC_FROZEN_32_PARTS_HTTP_PROOF_V1",
        "status": "PASS" if all_ok else "FAIL",
        "basis": "PUBLIC_HTTP_200_EXACT_SHA256",
        "conclusion": "ALL_PUBLIC_FILES_MATCH" if all_ok else "PREVIEW_PART_MISSING_OR_CHANGED",
        "checks": checks,
        "expected_count": len(PARTS),
        "verified_count": sum(row["http_200_and_sha256_match"] for row in checks),
        "verified_at_utc": observed.astimezone(dt.timezone.utc).isoformat(),
        "source_grade": "FROZEN_DESIGN_BYTES_ONLY",
        "core_model_effect": "NONE",
    }


def verify_parts(root: Path, base_url: str, *,
                 fetcher=None, branch_reader=None,
                 clock=None) -> dict:
    root = Path(root)
    manifest = load_manifest(root)
    loader = (root / "site/control-room-preview/index.html").read_text(encoding="utf-8")
    if ('Array.from({length:32}' not in loader
        or 'paths.map(async path' not in loader
        or 'if(!response.ok)throw' not in loader):
        raise ValueError("V10_PREVIEW_LOADER_NOT_FETCHING_FROZEN_32")
    if not base_url.startswith("https://") or not base_url.endswith("/"):
        raise ValueError("V10_PREVIEW_REQUIRE_HTTPS_BASE_URL")
    branches = branch_reader(root) if branch_reader else branch_parts(root)
    if fetcher is None:
        def fetcher(path):
            req = urllib.request.Request(
                base_url + path,
                headers={"User-Agent": "GMFQ-Pages-Preview-32-Part-Audit/1.0",
                         "Cache-Control": "no-cache", "Pragma": "no-cache"},
            )
            with urllib.request.urlopen(req, timeout=3.0) as response:
                return response.status, response.read()
    downloads = {}
    for path in PARTS:
        try:
            status, data = fetcher(path)
            downloads[path] = {"status": status, "data": data}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            downloads[path] = {"status": None, "data": None,
                               "error": type(exc).__name__ + ": " + str(exc)[:150]}
    now = clock() if clock is not None else dt.datetime.now(dt.timezone.utc)
    return evaluate(manifest, branches, downloads, now)
