#!/usr/bin/env python3
"""Fail-closed contract for the China macro confirmation lane.

China CLI is deliberately excluded. The lane may become READY only as a
context-only confirmation layer when BOTH official NBS releases have strict PIT
receipts and the documented direction rule evaluates deterministically.
It can never cast a mechanical G8 pair vote and cannot publish independently.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "validation" / "china_macro_confirmation_source_registry_v1.json"
RECEIPTS = ROOT / "validation" / "china_macro_confirmation_pit_receipts_v1.json"


def series_direction(value, prior):
    if value is None or prior is None:
        return "WITHHELD"
    if value > prior:
        return "IMPROVING"
    if value < prior:
        return "WEAKENING"
    return "STABLE"


def combined_direction(activity: str, demand: str) -> str:
    if "WITHHELD" in (activity, demand):
        return "WITHHELD"
    if activity == demand:
        return activity
    return "MIXED"


def evaluate() -> dict:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    receipts_doc = json.loads(RECEIPTS.read_text(encoding="utf-8"))
    required = {"activity", "demand"}
    sources = registry.get("required_sources", {})
    receipts = receipts_doc.get("receipts", {})
    failures = []

    if set(sources) != required:
        failures.append("required_source_set_must_be_activity_and_demand")
    if set(receipts) != required:
        failures.append("receipt_set_must_be_activity_and_demand")

    for name in required:
        source = sources.get(name, {})
        receipt = receipts.get(name, {})
        for key in ("publisher", "series", "release_basis", "source_url", "pit_requirement"):
            if not source.get(key):
                failures.append(f"{name}:missing_source_{key}")
        if source.get("proxy_allowed") is not False:
            failures.append(f"{name}:proxy_must_be_prohibited")

        for key in ("publisher", "series", "source_url", "release_period", "release_timestamp", "raw_sha256", "value", "prior_value", "unit", "direction"):
            if receipt.get(key) in (None, ""):
                failures.append(f"{name}:missing_receipt_{key}")
        if receipt.get("publisher") != source.get("publisher"):
            failures.append(f"{name}:publisher_mismatch")
        if receipt.get("series") != source.get("series"):
            failures.append(f"{name}:series_mismatch")
        if not str(receipt.get("source_url", "")).startswith("https://www.stats.gov.cn/"):
            failures.append(f"{name}:source_url_not_official_nbs")
        raw_hash = str(receipt.get("raw_sha256", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", raw_hash):
            failures.append(f"{name}:invalid_sha256")

        expected_direction = series_direction(receipt.get("value"), receipt.get("prior_value"))
        if receipt.get("direction") != expected_direction:
            failures.append(f"{name}:direction_mismatch:{expected_direction}")

    activity = receipts.get("activity", {}).get("direction", "WITHHELD")
    demand = receipts.get("demand", {}).get("direction", "WITHHELD")
    combined = combined_direction(activity, demand)
    if receipts_doc.get("combined_direction") != combined:
        failures.append(f"combined_direction_mismatch:{combined}")

    if registry.get("cli_is_not_an_input") is not True:
        failures.append("china_cli_must_be_excluded")
    if registry.get("mechanical_pair_vote") is not False or receipts_doc.get("mechanical_pair_vote") is not False:
        failures.append("mechanical_pair_vote_must_be_false")
    if registry.get("publication_permitted") is not False or receipts_doc.get("publication_permitted") is not False:
        failures.append("publication_must_remain_false")
    if registry.get("activation_scope") != "CONTEXT_ONLY" or receipts_doc.get("activation_scope") != "CONTEXT_ONLY":
        failures.append("activation_scope_must_be_context_only")
    if not registry.get("direction_rule"):
        failures.append("direction_rule_missing")
    if registry.get("activation_blocker") is not None:
        failures.append("activation_blocker_must_be_null_when_ready")

    status = "READY/CONTEXT_ONLY" if not failures else "FAIL"
    return {
        "schema": "GMFQ_CHINA_MACRO_CONFIRMATION_CONTRACT_V1",
        "status": status,
        "validator_green": not failures,
        "failures": failures,
        "activity_direction": activity,
        "demand_direction": demand,
        "combined_direction": combined,
        "activation_scope": "CONTEXT_ONLY" if not failures else "WITHHELD",
        "mechanical_pair_vote": False,
        "publication_permitted": False,
    }


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
