#!/usr/bin/env python3
"""Schema-only adapter contract for future licensed bank-research ingestion."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "validation" / "bank_research_ingestion_schema_v1.json"


def evaluate() -> dict:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    failures = []
    required = {"provider", "report_id", "published_at", "retrieved_at", "license_basis", "source_uri", "content_sha256", "coverage", "claims"}
    if set(schema.get("required_record_fields", [])) != required: failures.append("record_schema_fields_mismatch")
    if schema.get("status") != "PLANNED/NOT_WIRED": failures.append("status_must_be_planned")
    if schema.get("mechanical_pair_vote") is not False: failures.append("mechanical_vote_must_be_false")
    if schema.get("publication_permitted") is not False: failures.append("publication_must_be_false")
    if schema.get("existing_artifacts_linked") != []: failures.append("unproven_existing_artifacts_must_not_be_linked")
    return {"schema":"GMFQ_BANK_RESEARCH_ADAPTER_CONTRACT_V1", "status":"PLANNED/NOT_WIRED" if not failures else "FAIL",
            "validator_green":not failures, "failures":failures, "mechanical_pair_vote":False, "publication_permitted":False}


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--write", type=Path); args=parser.parse_args()
    report=evaluate(); text=json.dumps(report,indent=2,ensure_ascii=False)+"\n"
    if args.write: args.write.write_text(text,encoding="utf-8")
    print(text,end=""); return 0 if report["validator_green"] else 2


if __name__ == "__main__": raise SystemExit(main())
