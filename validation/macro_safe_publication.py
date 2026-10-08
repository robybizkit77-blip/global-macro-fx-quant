#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
from typing import Any

SCHEMA = "GMFQ_MACRO_SAFE_PUBLICATION_REQUEST_V1"
PIT_SCHEMA = "GMFQ_MACRO_PIT_ANCHOR_EVIDENCE_V1"
IDENTITY_KEYS = (
    "currency",
    "dimension",
    "macro_series_id",
    "observation_date",
    "value",
    "source",
    "series_id",
    "frequency",
    "transformation",
)


def load(path: str | pathlib.Path) -> Any:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def dump(path: str | pathlib.Path, value: Any) -> None:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate(candidate: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if evidence.get("schema") != PIT_SCHEMA:
        failures.append("unexpected PIT evidence schema")
    if evidence.get("status") != "PASS":
        failures.append("PIT evidence is not PASS")
    if evidence.get("macro_series_exact_match") is not True:
        failures.append("MACRO_SERIES exact match is not true")
    if evidence.get("heatmap_exact_match") is not True:
        failures.append("MACRO_THERMOMETER_DATA exact match is not true")
    if evidence.get("live_data_written_by_replay") is not False:
        failures.append("PIT replay wrote live_data")
    if evidence.get("engine_or_source_infrastructure_changed") is not False:
        failures.append("engine/source infrastructure changed during PIT anchor")
    if evidence.get("registry_promotion") not in {"NOT_ATTEMPTED", "REVIEW_REQUIRED"}:
        failures.append("unexpected registry promotion state")

    target = evidence.get("target") or {}
    expected_target = {k: candidate.get(k) for k in ("currency", "dimension", "macro_series_id")}
    if target != expected_target:
        failures.append(f"PIT target mismatch: evidence={target!r} candidate={expected_target!r}")

    evidence_candidate = evidence.get("candidate") or {}
    mismatch = {
        key: {"candidate": candidate.get(key), "evidence": evidence_candidate.get(key)}
        for key in IDENTITY_KEYS
        if candidate.get(key) != evidence_candidate.get(key)
    }
    if mismatch:
        failures.append(f"candidate differs from PIT evidence candidate: {mismatch}")

    changed_rows = ((evidence.get("atomic_delta") or {}).get("changed_rows") or [])
    if len(changed_rows) != 1:
        failures.append("PIT evidence is not an atomic single-row delta")
    elif changed_rows[0].get("currency") != candidate.get("currency") or changed_rows[0].get("macro_series_id") != candidate.get("macro_series_id"):
        failures.append("atomic changed row does not match publication target")

    required_candidate = ("currency", "dimension", "macro_series_id", "observation_date", "value", "source", "series_id", "frequency", "transformation")
    missing = [k for k in required_candidate if candidate.get(k) is None]
    if missing:
        failures.append(f"candidate missing required fields: {missing}")

    status = "READY_FOR_RUNTIME_PROPOSAL" if not failures else "REJECTED"
    return {
        "schema": SCHEMA,
        "status": status,
        "failures": failures,
        "target": expected_target,
        "candidate": candidate,
        "pit_anchor": {
            "schema": evidence.get("schema"),
            "status": evidence.get("status"),
            "anchor": evidence.get("anchor"),
        },
        "publication_policy": {
            "automatic_publication": False,
            "commit_performed": False,
            "gh_pages_published": False,
            "review_required": True,
        },
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate one macro PIT evidence before building a publication proposal")
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--pit-evidence", required=True)
    ap.add_argument("--output")
    args = ap.parse_args()
    result = validate(load(args.candidate), load(args.pit_evidence))
    if args.output:
        dump(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "READY_FOR_RUNTIME_PROPOSAL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
