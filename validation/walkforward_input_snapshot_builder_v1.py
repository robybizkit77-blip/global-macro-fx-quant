#!/usr/bin/env python3
"""Build a deterministic point-in-time Macro + Rates input snapshot.

This consumes already-authorized cross-layer inputs and independently verified
Macro/Rates row permits. It does not score, trade, label returns, or authorize a
backtest. Its only job is to freeze exactly what the model was allowed to know at
one decision point.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA = "GMFQ_WALKFORWARD_INPUT_SNAPSHOT_V1"
VERIFY_SCHEMA = "GMFQ_WALKFORWARD_INPUT_SNAPSHOT_VERIFICATION_V1"
CROSS_SCHEMA = "GMFQ_CROSS_LAYER_BACKTEST_INPUT_BUNDLE_V1"
MACRO_RESULT_SCHEMA = "GMFQ_MACRO_TEMPORAL_ROW_SELECTOR_V1"
MACRO_VERIFY_SCHEMA = "GMFQ_MACRO_TEMPORAL_ROW_PERMIT_VERIFICATION_V1"
RATES_RESULT_SCHEMA = "GMFQ_RATES_TEMPORAL_ROW_SELECTOR_V1"
RATES_VERIFY_SCHEMA = "GMFQ_RATES_ROW_PERMIT_VERIFICATION_V1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def verify_cross_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    if bundle.get("schema") != CROSS_SCHEMA or bundle.get("status") != "INPUT_LOAD_AUTHORIZED":
        raise RuntimeError("invalid cross-layer bundle")
    supplied = bundle.get("bundle_sha256")
    body = {k: v for k, v in bundle.items() if k != "bundle_sha256"}
    if not isinstance(supplied, str) or sha256_obj(body) != supplied:
        raise RuntimeError("cross-layer bundle hash mismatch")
    policy = bundle.get("policy") or {}
    required = {
        "fail_closed": True,
        "partial_layer_bundle_allowed": False,
        "runtime_history_fallback_allowed": False,
        "future_revision_fallback_allowed": False,
        "layer_substitution_allowed": False,
        "currency_substitution_allowed": False,
        "date_substitution_allowed": False,
        "input_load_authorized": True,
        "backtest_execution_authorized": False,
    }
    if any(policy.get(k) != v for k, v in required.items()):
        raise RuntimeError("cross-layer policy is not fail-closed")
    if policy.get("required_layers") != ["Macro", "Rates"]:
        raise RuntimeError("cross-layer required layer set mismatch")
    return {
        "currency": bundle["currency"],
        "decision_point": bundle["decision_point"],
        "decision_date": bundle["decision_date"],
        "macro_targets": sorted(bundle["layers"]["Macro"]["targets"]),
        "rates_target": bundle["layers"]["Rates"]["target"],
        "bundle_sha256": supplied,
    }


def validate_macro_pair(result: dict[str, Any], verification: dict[str, Any], decision_point: str) -> dict[str, Any]:
    if result.get("schema") != MACRO_RESULT_SCHEMA or result.get("status") != "ROW_PERMIT_ISSUED":
        raise RuntimeError("invalid Macro row selector result")
    row = result.get("row_permit")
    if not isinstance(row, dict) or row.get("layer") != "Macro":
        raise RuntimeError("invalid Macro row permit")
    supplied = row.get("row_permit_sha256")
    body = {k: v for k, v in row.items() if k != "row_permit_sha256"}
    if not isinstance(supplied, str) or sha256_obj(body) != supplied:
        raise RuntimeError("Macro row permit hash mismatch")
    if row.get("decision_point") != decision_point:
        raise RuntimeError("Macro decision point mismatch")
    if row.get("row_consumption_authorized") is not True or row.get("same_day_use_allowed") is not False:
        raise RuntimeError("Macro row is not conservatively authorized")
    if not date.fromisoformat(str(row.get("release_date"))) < date.fromisoformat(str(row.get("decision_date"))):
        raise RuntimeError("Macro release is not strictly prior to decision date")
    if verification.get("schema") != MACRO_VERIFY_SCHEMA or verification.get("status") != "VERIFIED":
        raise RuntimeError("invalid Macro row verification")
    exact = {
        "target": row["target"],
        "decision_point": row["decision_point"],
        "reference_month": row["reference_month"],
        "release_date": row["release_date"],
        "row_permit_sha256": row["row_permit_sha256"],
        "row_consumption_authorized": True,
    }
    if any(verification.get(k) != v for k, v in exact.items()):
        raise RuntimeError("Macro verification does not exactly bind row permit")
    return {
        "target": row["target"],
        "reference_month": row["reference_month"],
        "release_date": row["release_date"],
        "value_field": row["value_field"],
        "value": row["value"],
        "source_route": row.get("source_route"),
        "pit_status": row.get("pit_status"),
        "evidence_semantic_rowset_sha256": row.get("evidence_semantic_rowset_sha256"),
        "row_permit_sha256": row["row_permit_sha256"],
    }


def validate_rates_pair(result: dict[str, Any], verification: dict[str, Any], decision_point: str) -> dict[str, Any]:
    if result.get("schema") != RATES_RESULT_SCHEMA or result.get("status") != "ROW_PERMIT_ISSUED":
        raise RuntimeError("invalid Rates row selector result")
    row = result.get("row_permit")
    if not isinstance(row, dict) or row.get("layer") != "Rates":
        raise RuntimeError("invalid Rates row permit")
    supplied = row.get("row_permit_sha256")
    body = {k: v for k, v in row.items() if k != "row_permit_sha256"}
    if not isinstance(supplied, str) or sha256_obj(body) != supplied:
        raise RuntimeError("Rates row permit hash mismatch")
    if row.get("decision_point") != decision_point:
        raise RuntimeError("Rates decision point mismatch")
    if verification.get("schema") != RATES_VERIFY_SCHEMA or verification.get("status") != "VERIFIED":
        raise RuntimeError("invalid Rates row verification")
    exact = {
        "target": row["target"],
        "decision_point": row["decision_point"],
        "observation_date": row["observation_date"],
        "row_permit_sha256": row["row_permit_sha256"],
        "row_consumption_authorized": True,
    }
    if any(verification.get(k) != v for k, v in exact.items()):
        raise RuntimeError("Rates verification does not exactly bind row permit")
    if row.get("row_consumption_authorized") is not True or row.get("same_day_use_allowed") is not False:
        raise RuntimeError("Rates row is not safely authorized")
    return {
        "target": row["target"],
        "observation_date": row["observation_date"],
        "yield_2y": row["yield_2y"],
        "yield_10y": row["yield_10y"],
        "curve_bp": row.get("curve_bp"),
        "source_basis": row.get("source_basis"),
        "evidence_semantic_rowset_sha256": row.get("evidence_semantic_rowset_sha256"),
        "row_permit_sha256": row["row_permit_sha256"],
    }


def build_snapshot(bundle: dict[str, Any], macro_pairs: list[tuple[dict[str, Any], dict[str, Any]]], rates_result: dict[str, Any], rates_verification: dict[str, Any]) -> dict[str, Any]:
    cross = verify_cross_bundle(bundle)
    if not macro_pairs:
        raise RuntimeError("at least one Macro row pair is required")
    macro_rows: dict[str, dict[str, Any]] = {}
    for result, verification in macro_pairs:
        row = validate_macro_pair(result, verification, cross["decision_point"])
        target = row.pop("target")
        if target in macro_rows:
            raise RuntimeError(f"duplicate Macro row target: {target}")
        macro_rows[target] = row
    if sorted(macro_rows) != cross["macro_targets"]:
        raise RuntimeError("snapshot Macro target set does not exactly match cross-layer authorization")

    rates = validate_rates_pair(rates_result, rates_verification, cross["decision_point"])
    if rates["target"] != cross["rates_target"]:
        raise RuntimeError("snapshot Rates target does not match cross-layer authorization")
    rates.pop("target")

    body = {
        "schema": SCHEMA,
        "status": "SNAPSHOT_MATERIALIZED",
        "currency": cross["currency"],
        "decision_point": cross["decision_point"],
        "decision_date": cross["decision_date"],
        "source_cross_layer_bundle_sha256": cross["bundle_sha256"],
        "layers": {
            "Macro": {"rows": {k: macro_rows[k] for k in sorted(macro_rows)}},
            "Rates": {"row": rates},
        },
        "policy": {
            "fail_closed": True,
            "snapshot_only": True,
            "all_authorized_layers_required": True,
            "all_authorized_targets_required": True,
            "future_information_allowed": False,
            "same_day_macro_release_without_verified_timestamp_allowed": False,
            "runtime_history_fallback_allowed": False,
            "future_revision_fallback_allowed": False,
            "signal_calculation_allowed": False,
            "return_label_calculation_allowed": False,
            "position_sizing_allowed": False,
            "input_snapshot_materialized": True,
            "backtest_execution_authorized": False,
        },
    }
    return {**body, "snapshot_sha256": sha256_obj(body)}


def verify_snapshot(snapshot: dict[str, Any], bundle: dict[str, Any], macro_pairs: list[tuple[dict[str, Any], dict[str, Any]]], rates_result: dict[str, Any], rates_verification: dict[str, Any]) -> dict[str, Any]:
    if snapshot.get("schema") != SCHEMA or snapshot.get("status") != "SNAPSHOT_MATERIALIZED":
        raise RuntimeError("invalid walk-forward snapshot")
    supplied = snapshot.get("snapshot_sha256")
    body = {k: v for k, v in snapshot.items() if k != "snapshot_sha256"}
    if not isinstance(supplied, str) or sha256_obj(body) != supplied:
        raise RuntimeError("walk-forward snapshot hash mismatch")
    expected = build_snapshot(bundle, macro_pairs, rates_result, rates_verification)
    if expected != snapshot:
        raise RuntimeError("walk-forward snapshot is stale, tampered, or non-canonical")
    return {
        "schema": VERIFY_SCHEMA,
        "status": "VERIFIED",
        "currency": snapshot["currency"],
        "decision_point": snapshot["decision_point"],
        "snapshot_sha256": snapshot["snapshot_sha256"],
        "input_snapshot_materialized": True,
        "backtest_execution_authorized": False,
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def macro_pairs(results: list[Path], verifications: list[Path]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if len(results) != len(verifications):
        raise RuntimeError("Macro selector result/verification counts differ")
    return [(read_json(a), read_json(b)) for a, b in zip(results, verifications)]


def emit(value: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def configure(p: argparse.ArgumentParser, verify: bool = False) -> None:
    if verify:
        p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--cross-layer-bundle", type=Path, required=True)
    p.add_argument("--macro-row-result", type=Path, action="append", required=True)
    p.add_argument("--macro-row-verification", type=Path, action="append", required=True)
    p.add_argument("--rates-row-result", type=Path, required=True)
    p.add_argument("--rates-row-verification", type=Path, required=True)
    p.add_argument("--output", type=Path)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build"); configure(b)
    v = sub.add_parser("verify"); configure(v, True)
    args = ap.parse_args()
    bundle = read_json(args.cross_layer_bundle)
    pairs = macro_pairs(args.macro_row_result, args.macro_row_verification)
    rates_result = read_json(args.rates_row_result)
    rates_verification = read_json(args.rates_row_verification)
    if args.command == "build":
        result = build_snapshot(bundle, pairs, rates_result, rates_verification)
    else:
        result = verify_snapshot(read_json(args.snapshot), bundle, pairs, rates_result, rates_verification)
    emit(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
