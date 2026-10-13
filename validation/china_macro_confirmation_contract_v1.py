#!/usr/bin/env python3
"""Fail-closed contract for a China macro confirmation lane.

China CLI is a displayed risk input and is deliberately not accepted here.  A
future adapter must provide an NBS release receipt for both activity and demand
before this lane can become active.  This validator is intentionally read-only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "validation" / "china_macro_confirmation_source_registry_v1.json"


def evaluate() -> dict:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    required = {"activity", "demand"}
    sources = registry.get("required_sources", {})
    failures = []
    if set(sources) != required:
        failures.append("required_source_set_must_be_activity_and_demand")
    for name in required:
        source = sources.get(name, {})
        for key in ("publisher", "series", "release_basis", "source_url", "pit_requirement"):
            if not source.get(key):
                failures.append(f"{name}:missing_{key}")
        if source.get("proxy_allowed") is not False:
            failures.append(f"{name}:proxy_must_be_prohibited")
    if registry.get("cli_is_not_an_input") is not True:
        failures.append("china_cli_must_be_excluded")
    if registry.get("mechanical_pair_vote") is not False:
        failures.append("mechanical_pair_vote_must_be_false")
    if registry.get("publication_permitted") is not False:
        failures.append("publication_must_remain_false")
    status = "PLANNED/NOT_WIRED" if not failures else "FAIL"
    return {"schema": "GMFQ_CHINA_MACRO_CONFIRMATION_CONTRACT_V1", "status": status,
            "validator_green": not failures, "failures": failures,
            "activation_blocker": registry.get("activation_blocker"),
            "mechanical_pair_vote": False, "publication_permitted": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    report = evaluate()
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.write:
        args.write.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["validator_green"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
