#!/usr/bin/env python3
"""Fail-closed Rates backtest input contract.

This contract issues deterministic *layer permits* only. A layer permit proves that
one Rates target is certified and eligible for the requested decision date under
the canonical Rates walk-forward gate. It does NOT authorize a particular market
row. A downstream temporal row selector must separately prove that the selected
observation satisfies the evidence-specific publication/availability rule.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = ROOT / "validation" / "rates_walkforward_eligibility_gate_v1.py"
SCHEMA = "GMFQ_RATES_BACKTEST_INPUT_CONTRACT_V1"
PERMIT_SCHEMA = "GMFQ_RATES_LAYER_PERMIT_V1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_gate_module():
    spec = importlib.util.spec_from_file_location("gmfq_rates_gate", GATE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Rates eligibility gate")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def gate_fingerprint(gate_result: dict[str, Any]) -> str:
    stable = {
        "schema": gate_result.get("schema"),
        "status": gate_result.get("status"),
        "decision_date": gate_result.get("decision_date"),
        "policy": gate_result.get("policy"),
        "expected_targets": gate_result.get("expected_targets"),
        "certified_targets": gate_result.get("certified_targets"),
        "eligible_targets": gate_result.get("eligible_targets"),
        "withheld_targets": gate_result.get("withheld_targets"),
        "targets": gate_result.get("targets"),
    }
    return sha256_obj(stable)


def normalized_targets(targets: list[str]) -> list[str]:
    if not targets:
        raise RuntimeError("at least one Rates target is required")
    clean = []
    seen = set()
    for target in targets:
        if not isinstance(target, str) or not target.strip():
            raise RuntimeError("invalid empty Rates target")
        target = target.strip()
        if target in seen:
            raise RuntimeError(f"duplicate Rates target requested: {target}")
        seen.add(target)
        clean.append(target)
    return sorted(clean)


def issue_bundle(decision_date: str, targets: list[str]) -> dict[str, Any]:
    targets = normalized_targets(targets)
    gate = load_gate_module()
    gate_result = gate.build(decision_date)
    if gate_result.get("schema") != "GMFQ_RATES_WALKFORWARD_ELIGIBILITY_GATE_V1":
        raise RuntimeError("unexpected Rates gate schema")
    if gate_result.get("status") != "PASS":
        raise RuntimeError("Rates eligibility gate is not PASS")
    if gate_result.get("decision_date") != decision_date:
        raise RuntimeError("Rates gate silently changed requested decision date")

    ghash = gate_fingerprint(gate_result)
    permits = []
    for target in targets:
        row = gate_result.get("targets", {}).get(target)
        if row is None:
            raise RuntimeError(f"unknown Rates target: {target}")
        if row.get("certification") != "CERTIFIED" or row.get("backtest_eligible") is not True:
            raise RuntimeError(f"Rates target is not backtest eligible at {decision_date}: {target}")
        if row.get("same_day_use_allowed") is not False:
            raise RuntimeError(f"same-day Rates use is not explicitly forbidden: {target}")
        evidence = row.get("evidence")
        evidence_hash = row.get("semantic_rowset_sha256")
        temporal_rule = row.get("temporal_eligibility_rule")
        if not isinstance(evidence, str) or not evidence:
            raise RuntimeError(f"missing Rates evidence reference: {target}")
        if not isinstance(evidence_hash, str) or len(evidence_hash) != 64:
            raise RuntimeError(f"missing/invalid Rates evidence semantic hash: {target}")
        if not isinstance(temporal_rule, str) or not temporal_rule:
            raise RuntimeError(f"missing Rates temporal eligibility rule: {target}")

        permit_body = {
            "schema": PERMIT_SCHEMA,
            "layer": "Rates",
            "target": target,
            "decision_date": decision_date,
            "gate_schema": gate_result["schema"],
            "gate_fingerprint_sha256": ghash,
            "evidence": evidence,
            "evidence_semantic_rowset_sha256": evidence_hash,
            "temporal_eligibility_rule": temporal_rule,
            "same_day_use_allowed": False,
            "layer_eligible": True,
            "row_consumption_authorized": False,
            "row_selector_requirement": "SEPARATE_TEMPORAL_ROW_VALIDATION_REQUIRED_BEFORE_ANY_RATE_OBSERVATION_CAN_ENTER_BACKTEST",
        }
        permits.append({**permit_body, "permit_sha256": sha256_obj(permit_body)})

    bundle_body = {
        "schema": SCHEMA,
        "status": "PERMIT_ISSUED",
        "decision_date": decision_date,
        "policy": {
            "fail_closed": True,
            "missing_or_invalid_permit_action": "ABORT_BACKTEST",
            "runtime_history_fallback_allowed": False,
            "secondary_source_fallback_allowed": False,
            "silent_target_substitution_allowed": False,
            "silent_date_substitution_allowed": False,
            "same_day_use_allowed": False,
            "layer_permit_is_not_row_permit": True,
            "row_consumption_requires_separate_temporal_selector": True,
        },
        "requested_targets": targets,
        "gate_fingerprint_sha256": ghash,
        "permits": permits,
    }
    return {**bundle_body, "bundle_sha256": sha256_obj(bundle_body)}


def verify_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise RuntimeError("Rates permit bundle must be an object")
    if bundle.get("schema") != SCHEMA:
        raise RuntimeError("unexpected Rates permit bundle schema")
    supplied_bundle_hash = bundle.get("bundle_sha256")
    if not isinstance(supplied_bundle_hash, str):
        raise RuntimeError("missing Rates bundle hash")
    unhashed = {k: v for k, v in bundle.items() if k != "bundle_sha256"}
    if sha256_obj(unhashed) != supplied_bundle_hash:
        raise RuntimeError("Rates permit bundle hash mismatch")

    permits = bundle.get("permits")
    if not isinstance(permits, list) or not permits:
        raise RuntimeError("Rates permit bundle contains no permits")
    permit_targets = []
    for permit in permits:
        if not isinstance(permit, dict):
            raise RuntimeError("invalid Rates permit")
        psha = permit.get("permit_sha256")
        pbody = {k: v for k, v in permit.items() if k != "permit_sha256"}
        if not isinstance(psha, str) or sha256_obj(pbody) != psha:
            raise RuntimeError("Rates permit hash mismatch")
        if permit.get("row_consumption_authorized") is not False:
            raise RuntimeError("Rates layer permit was escalated to row authorization")
        permit_targets.append(permit.get("target"))

    requested = normalized_targets(list(bundle.get("requested_targets") or []))
    if sorted(permit_targets) != requested:
        raise RuntimeError("Rates permit target set mismatch")
    if bundle.get("decision_date") is None:
        raise RuntimeError("Rates permit bundle missing decision date")

    expected = issue_bundle(bundle["decision_date"], requested)
    if expected != bundle:
        raise RuntimeError("Rates permit is stale, mismatched, or no longer canonical")
    return {
        "schema": "GMFQ_RATES_BACKTEST_INPUT_VERIFICATION_V1",
        "status": "VERIFIED",
        "decision_date": bundle["decision_date"],
        "targets": requested,
        "bundle_sha256": bundle["bundle_sha256"],
        "row_consumption_authorized": False,
        "next_required_gate": "TEMPORAL_RATE_ROW_SELECTOR",
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    issue = sub.add_parser("issue")
    issue.add_argument("--decision-date", required=True)
    issue.add_argument("--target", action="append", required=True)
    issue.add_argument("--output", type=Path)

    verify = sub.add_parser("verify")
    verify.add_argument("--permit", required=True, type=Path)
    verify.add_argument("--output", type=Path)

    args = parser.parse_args()
    if args.command == "issue":
        result = issue_bundle(args.decision_date, args.target)
    else:
        result = verify_bundle(read_json(args.permit))

    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
