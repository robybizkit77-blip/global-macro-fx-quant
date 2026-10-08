#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from typing import Any

from macro_safe_publication import validate as validate_safe_publication

RECEIPT_SCHEMA = "GMFQ_MACRO_SAFE_PUBLICATION_RECEIPT_V1"
EVIDENCE_SCHEMA = "GMFQ_MACRO_PIT_ANCHOR_EVIDENCE_V1"


def load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def one(root: pathlib.Path, name: str) -> pathlib.Path:
    matches = [p for p in root.rglob(name) if p.is_file()]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {name}, found {len(matches)}")
    return matches[0]


def verify(root: pathlib.Path, expected_base_sha: str) -> dict[str, Any]:
    receipt_path = one(root, "receipt.json")
    candidate_path = one(root, "candidate.json")
    evidence_path = one(root, "macro-pit-anchor-evidence.json")
    request_path = one(root, "publication-request.json")
    patch_path = one(root, "proposal.patch")
    manifest_path = one(root, "file-sha256.json")

    receipt = load(receipt_path)
    candidate = load(candidate_path)
    evidence = load(evidence_path)
    request = load(request_path)
    manifest = load(manifest_path)

    failures: list[str] = []
    if receipt.get("schema") != RECEIPT_SCHEMA:
        failures.append("unexpected receipt schema")
    if receipt.get("status") != "READY_FOR_REVIEW":
        failures.append("receipt is not READY_FOR_REVIEW")
    if receipt.get("base_sha") != expected_base_sha:
        failures.append("receipt base_sha does not match current main SHA")
    for key, wanted in {
        "automatic_publication": False,
        "commit_performed": False,
        "main_modified": False,
        "gh_pages_published": False,
        "review_required": True,
    }.items():
        if receipt.get(key) is not wanted:
            failures.append(f"receipt policy violation: {key}")

    expected_hashes = receipt.get("artifact_sha256") or {}
    actual_hashes = {
        "candidate_json": sha256(candidate_path),
        "pit_evidence_json": sha256(evidence_path),
        "publication_request_json": sha256(request_path),
        "proposal_patch": sha256(patch_path),
        "file_sha256_json": sha256(manifest_path),
    }
    if expected_hashes != actual_hashes:
        failures.append(f"artifact hash mismatch: expected={expected_hashes!r} actual={actual_hashes!r}")

    if evidence.get("schema") != EVIDENCE_SCHEMA or evidence.get("status") != "PASS":
        failures.append("PIT evidence is not certified PASS")

    rebuilt = validate_safe_publication(candidate, evidence)
    for key in ("status", "target", "candidate", "pit_anchor", "publication_policy"):
        if request.get(key) != rebuilt.get(key):
            failures.append(f"publication request mismatch at {key}")
    if request.get("status") != "READY_FOR_RUNTIME_PROPOSAL":
        failures.append("publication request is not READY_FOR_RUNTIME_PROPOSAL")
    if receipt.get("target") != request.get("target"):
        failures.append("receipt target differs from publication request target")

    changed_files = receipt.get("changed_files") or []
    if not changed_files or len(changed_files) != len(set(changed_files)):
        failures.append("receipt changed_files is empty or contains duplicates")
    allowed_prefixes = ("live_data/", "payload/")
    forbidden = [p for p in changed_files if not isinstance(p, str) or not p.startswith(allowed_prefixes)]
    if forbidden:
        failures.append(f"receipt diff scope contains forbidden paths: {forbidden!r}")
    if set(manifest) != set(changed_files):
        failures.append("file-sha256 manifest paths differ from receipt changed_files")

    files_root = manifest_path.parent / "files"
    for rel, expected in manifest.items():
        p = files_root / rel
        if not p.is_file():
            failures.append(f"proposal file missing: {rel}")
        elif sha256(p) != expected:
            failures.append(f"proposal file hash mismatch: {rel}")

    if failures:
        raise ValueError("FINAL_APPLY_REJECTED: " + " | ".join(failures))

    return {
        "schema": "GMFQ_MACRO_FINAL_APPLY_VERIFICATION_V1",
        "status": "PASS",
        "base_sha": expected_base_sha,
        "target": receipt.get("target"),
        "changed_files": changed_files,
        "artifact_sha256": actual_hashes,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-root", required=True)
    ap.add_argument("--expected-base-sha", required=True)
    ap.add_argument("--output")
    args = ap.parse_args()
    result = verify(pathlib.Path(args.artifact_root), args.expected_base_sha)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        pathlib.Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
