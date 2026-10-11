#!/usr/bin/env python3
"""Fail-closed input authorization contract for future walk-forward backtests.

This module deliberately does *not* run a backtest or load economic history.
It issues a deterministic permit only when every requested Macro target is
eligible at the requested information month according to the canonical Macro
walk-forward eligibility gate.

Future backtest/data-loader code must verify a permit before reading Macro
inputs. A permit can never authorize runtime-history fallback, future-revised
history, an unknown target, a WITHHELD target, or a date outside certified
coverage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from macro_walkforward_eligibility_gate_v1 import EXPECTED_SET, build, ym

SCHEMA = "GMFQ_BACKTEST_INPUT_PERMIT_V1"
ELIGIBILITY_SCHEMA = "GMFQ_MACRO_WALKFORWARD_ELIGIBILITY_GATE_V1"


def semantic_hash(payload: dict[str, Any]) -> str:
    body = {k: v for k, v in payload.items() if k != "permit_semantic_sha256"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def normalize_targets(values: list[str]) -> list[str]:
    if not values:
        raise RuntimeError("at least one --target is required")
    if len(values) != len(set(values)):
        raise RuntimeError("duplicate targets are forbidden")
    unknown = sorted(set(values) - EXPECTED_SET)
    if unknown:
        raise RuntimeError(f"unknown Macro target(s): {unknown}")
    return sorted(values)


def issue_permit(as_of: str, targets: list[str]) -> dict[str, Any]:
    point = ym(as_of)
    requested = normalize_targets(targets)
    eligibility = build(point)

    if eligibility.get("schema") != ELIGIBILITY_SCHEMA or eligibility.get("status") != "PASS":
        raise RuntimeError("Macro eligibility gate is not in PASS state")
    policy = eligibility.get("policy", {})
    if policy.get("fail_closed") is not True:
        raise RuntimeError("Macro eligibility gate is not fail-closed")
    if policy.get("runtime_history_fallback_allowed") is not False:
        raise RuntimeError("runtime history fallback must be forbidden")
    if policy.get("future_revision_fallback_allowed") is not False:
        raise RuntimeError("future revision fallback must be forbidden")

    authorizations: dict[str, dict[str, Any]] = {}
    denied: list[dict[str, str]] = []
    for target in requested:
        row = eligibility["targets"][target]
        if row.get("certification") != "CERTIFIED" or row.get("backtest_eligible") is not True:
            denied.append({"target": target, "reason": str(row.get("reason", "NOT_ELIGIBLE"))})
            continue
        receipt = row.get("receipt")
        coverage = row.get("coverage")
        if not isinstance(receipt, str) or not receipt.startswith("validation/macro/"):
            raise RuntimeError(f"invalid canonical receipt path for {target}: {receipt!r}")
        if not isinstance(coverage, dict) or not coverage.get("start") or not coverage.get("end"):
            raise RuntimeError(f"invalid certified coverage for {target}")
        authorizations[target] = {
            "receipt": receipt,
            "coverage": {"start": ym(coverage["start"]), "end": ym(coverage["end"])},
            "authorization": "ALLOW_STRICT_PIT_ONLY",
        }

    if denied:
        raise RuntimeError(f"backtest input authorization denied: {denied}")

    permit: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "PASS",
        "as_of": point,
        "requested_targets": requested,
        "authorized_target_count": len(authorizations),
        "authorizations": authorizations,
        "eligibility_contract": {
            "schema": ELIGIBILITY_SCHEMA,
            "certified_targets_seen": eligibility["certified_targets"],
            "eligible_targets_seen": eligibility["eligible_targets"],
        },
        "consumer_requirements": {
            "permit_verification_required_before_macro_load": True,
            "only_authorized_targets_may_be_loaded": True,
            "strict_pit_materialization_required": True,
            "runtime_history_archive_allowed": False,
            "future_revised_history_allowed": False,
            "silent_target_substitution_allowed": False,
            "silent_date_substitution_allowed": False,
            "missing_or_invalid_permit_action": "ABORT_BACKTEST",
        },
    }
    permit["permit_semantic_sha256"] = semantic_hash(permit)
    return permit


def verify_permit(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema") != SCHEMA or payload.get("status") != "PASS":
        raise RuntimeError("invalid backtest permit schema/status")
    supplied_hash = payload.get("permit_semantic_sha256")
    if not isinstance(supplied_hash, str) or len(supplied_hash) != 64:
        raise RuntimeError("missing/invalid permit semantic hash")
    if semantic_hash(payload) != supplied_hash:
        raise RuntimeError("permit semantic hash mismatch")

    as_of = ym(payload.get("as_of"))
    targets = normalize_targets(list(payload.get("requested_targets") or []))
    fresh = issue_permit(as_of, targets)

    # Verification is intentionally exact. If canonical receipt selection,
    # coverage, target set, policy, or semantic content changes, an old permit
    # becomes stale and the future backtest must stop and rematerialize it.
    if fresh != payload:
        raise RuntimeError("permit is stale relative to current canonical eligibility state")
    return payload


def write_json(payload: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--as-of", help="Issue permit for information month YYYY-MM")
    mode.add_argument("--verify-permit", type=Path, help="Verify an existing permit against canonical state")
    parser.add_argument("--target", action="append", default=[], help="Macro target, repeatable (e.g. EUR.inflation)")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.verify_permit:
        if args.target:
            raise RuntimeError("--target cannot be combined with --verify-permit")
        payload = json.loads(args.verify_permit.read_text(encoding="utf-8"))
        verified = verify_permit(payload)
        write_json(verified, args.output)
        return 0

    permit = issue_permit(args.as_of, args.target)
    write_json(permit, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
