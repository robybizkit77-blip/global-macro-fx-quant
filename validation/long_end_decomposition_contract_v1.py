#!/usr/bin/env python3
"""Methodology and fail-closed registry contract for long-end diagnostics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "validation" / "long_end_decomposition_source_registry_v1.json"
COMPONENTS = ("real_yield", "breakeven", "term_premium", "fiscal_supply")


def evaluate() -> dict:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    failures = []
    if data.get("mechanical_pair_vote") is not False or data.get("publication_permitted") is not False:
        failures.append("non_voting_no_publication_policy_broken")
    if set(data.get("components", {})) != set(COMPONENTS):
        failures.append("component_set_mismatch")
    for component in COMPONENTS:
        row = data.get("components", {}).get(component, {})
        if row.get("status") not in {"WITHHELD/EXPLICIT", "PLANNED/NOT_WIRED"}:
            failures.append(f"{component}:invalid_pre_activation_status")
        if not row.get("methodology") or not row.get("activation_blocker"):
            failures.append(f"{component}:missing_methodology_or_blocker")
        if row.get("runtime_value") is not None:
            failures.append(f"{component}:runtime_value_must_be_null_before_certification")
    if data.get("separate_from_2y_10y_curve") is not True:
        failures.append("must_remain_separate_from_native_rates")
    return {"schema": "GMFQ_LONG_END_DECOMPOSITION_CONTRACT_V1", "status": "PLANNED/NOT_WIRED" if not failures else "FAIL",
            "validator_green": not failures, "failures": failures, "mechanical_pair_vote": False,
            "publication_permitted": False}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--write", type=Path); args = parser.parse_args()
    report = evaluate(); text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.write: args.write.write_text(text, encoding="utf-8")
    print(text, end=""); return 0 if report["validator_green"] else 2


if __name__ == "__main__": raise SystemExit(main())
