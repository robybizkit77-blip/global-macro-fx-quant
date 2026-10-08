#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile

from macro_final_apply_gate import verify
from macro_safe_publication import validate

BASE = "a" * 40
CANDIDATE = {
    "currency": "JPY",
    "dimension": "labour",
    "macro_series_id": "JP_UNEMP_RATE_history_value",
    "observation_date": "2026-09-01",
    "value": 2.5,
    "source": "e-Stat",
    "series_id": "JP_UNEMP_RATE",
    "frequency": "monthly",
    "transformation": "level",
}
EVIDENCE = {
    "schema": "GMFQ_MACRO_PIT_ANCHOR_EVIDENCE_V1",
    "status": "PASS",
    "macro_series_exact_match": True,
    "heatmap_exact_match": True,
    "live_data_written_by_replay": False,
    "engine_or_source_infrastructure_changed": False,
    "registry_promotion": "NOT_ATTEMPTED",
    "target": {"currency": "JPY", "dimension": "labour", "macro_series_id": "JP_UNEMP_RATE_history_value"},
    "candidate": CANDIDATE,
    "anchor": {"kind": "synthetic-test"},
    "atomic_delta": {"changed_rows": [{"currency": "JPY", "macro_series_id": "JP_UNEMP_RATE_history_value"}]},
}


def dump(path: pathlib.Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(root: pathlib.Path) -> None:
    source = root / "source"
    proposal = root / "proposal"
    dump(source / "candidate.json", CANDIDATE)
    dump(source / "macro-pit-anchor-evidence.json", EVIDENCE)
    request = validate(CANDIDATE, EVIDENCE)
    dump(root / "publication-request.json", request)

    rels = [
        "live_data/sections/MACRO_SERIES.json",
        "live_data/sections/MACRO_THERMOMETER_DATA.json",
        "live_data/manifest.v2.json",
        "payload/part-01.txt",
        "payload/part-02.txt",
    ]
    manifest = {}
    for i, rel in enumerate(rels):
        p = proposal / "files" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"test-{i}\n", encoding="utf-8")
        manifest[rel] = sha(p)
    dump(proposal / "file-sha256.json", manifest)
    (proposal / "proposal.patch").write_text("synthetic patch\n", encoding="utf-8")

    hashes = {
        "candidate_json": sha(source / "candidate.json"),
        "pit_evidence_json": sha(source / "macro-pit-anchor-evidence.json"),
        "publication_request_json": sha(root / "publication-request.json"),
        "proposal_patch": sha(proposal / "proposal.patch"),
        "file_sha256_json": sha(proposal / "file-sha256.json"),
    }
    receipt = {
        "schema": "GMFQ_MACRO_SAFE_PUBLICATION_RECEIPT_V1",
        "status": "READY_FOR_REVIEW",
        "target": request["target"],
        "base_sha": BASE,
        "changed_files": rels,
        "automatic_publication": False,
        "commit_performed": False,
        "main_modified": False,
        "gh_pages_published": False,
        "review_required": True,
        "artifact_sha256": hashes,
    }
    dump(proposal / "receipt.json", receipt)


def expect_fail(root: pathlib.Path, label: str) -> None:
    try:
        verify(root, BASE)
    except ValueError:
        return
    raise AssertionError(f"negative mutation did not fail closed: {label}")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        build(root)
        result = verify(root, BASE)
        assert result["status"] == "PASS"

        receipt_path = root / "proposal" / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["base_sha"] = "b" * 40
        dump(receipt_path, receipt)
        expect_fail(root, "stale base SHA")

    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        build(root)
        p = root / "source" / "candidate.json"
        c = json.loads(p.read_text())
        c["value"] = 9.9
        dump(p, c)
        expect_fail(root, "candidate tamper")

    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        build(root)
        receipt_path = root / "proposal" / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["changed_files"].append(".github/workflows/evil.yml")
        dump(receipt_path, receipt)
        expect_fail(root, "forbidden diff scope")

    print(json.dumps({"schema": "GMFQ_MACRO_FINAL_APPLY_SELFTEST_V1", "status": "PASS", "negative_tests": 3}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
