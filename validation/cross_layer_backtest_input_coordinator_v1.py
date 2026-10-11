#!/usr/bin/env python3
"""Fail-closed binder for already-verified Macro + Rates backtest inputs.

This module does not run a backtest and does not materialize source data. It binds
an upstream verified Macro permit to an upstream verified Rates row permit for one
currency and one decision point. Any layer/date/currency mismatch aborts input
loading; partial bundles and silent substitutions are forbidden.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

SCHEMA = "GMFQ_CROSS_LAYER_BACKTEST_INPUT_BUNDLE_V1"
MACRO_SCHEMA = "GMFQ_BACKTEST_INPUT_PERMIT_V1"
RATES_SELECTOR_SCHEMA = "GMFQ_RATES_TEMPORAL_ROW_SELECTOR_V1"
RATES_ROW_SCHEMA = "GMFQ_RATES_ROW_PERMIT_V1"
RATES_VERIFY_SCHEMA = "GMFQ_RATES_ROW_PERMIT_VERIFICATION_V1"
CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def parse_decision_point(value: str) -> tuple[str, str]:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("decision point is required")
    value = value.strip()
    if "T" not in value:
        d = date.fromisoformat(value)
        return value, d.isoformat()
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise RuntimeError("timestamp decision point must include explicit timezone")
    return value, dt.date().isoformat()


def verify_macro_permit(permit: dict[str, Any], currency: str, macro_as_of: str) -> dict[str, Any]:
    if not isinstance(permit, dict) or permit.get("schema") != MACRO_SCHEMA or permit.get("status") != "PASS":
        raise RuntimeError("invalid Macro permit schema/status")
    supplied = permit.get("permit_semantic_sha256")
    if not isinstance(supplied, str) or len(supplied) != 64:
        raise RuntimeError("invalid Macro permit semantic hash")
    body = {k: v for k, v in permit.items() if k != "permit_semantic_sha256"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if hashlib.sha256(raw).hexdigest() != supplied:
        raise RuntimeError("Macro permit semantic hash mismatch")
    if permit.get("as_of") != macro_as_of:
        raise RuntimeError("Macro permit month does not match decision point month")

    requested = permit.get("requested_targets")
    auth = permit.get("authorizations")
    if not isinstance(requested, list) or not requested or len(requested) != len(set(requested)):
        raise RuntimeError("Macro permit requires a non-empty unique target set")
    if not isinstance(auth, dict) or set(auth) != set(requested):
        raise RuntimeError("Macro authorization set does not exactly match requested targets")
    if permit.get("authorized_target_count") != len(requested):
        raise RuntimeError("Macro authorized target count mismatch")

    prefix = currency + "."
    for target in requested:
        if not isinstance(target, str) or not target.startswith(prefix):
            raise RuntimeError(f"Macro target currency mismatch: {target}")
        row = auth[target]
        if not isinstance(row, dict) or row.get("authorization") != "ALLOW_STRICT_PIT_ONLY":
            raise RuntimeError(f"Macro target lacks strict-PIT authorization: {target}")
        receipt = row.get("receipt")
        coverage = row.get("coverage")
        if not isinstance(receipt, str) or not receipt.startswith("validation/macro/"):
            raise RuntimeError(f"invalid Macro receipt reference: {target}")
        if not isinstance(coverage, dict) or not coverage.get("start") or not coverage.get("end"):
            raise RuntimeError(f"invalid Macro coverage: {target}")
        if not (coverage["start"] <= macro_as_of <= coverage["end"]):
            raise RuntimeError(f"Macro as-of outside authorized coverage: {target}")

    req = permit.get("consumer_requirements")
    required_policy = {
        "permit_verification_required_before_macro_load": True,
        "only_authorized_targets_may_be_loaded": True,
        "strict_pit_materialization_required": True,
        "runtime_history_archive_allowed": False,
        "future_revised_history_allowed": False,
        "silent_target_substitution_allowed": False,
        "silent_date_substitution_allowed": False,
        "missing_or_invalid_permit_action": "ABORT_BACKTEST",
    }
    if not isinstance(req, dict) or any(req.get(k) != v for k, v in required_policy.items()):
        raise RuntimeError("Macro permit consumer policy is not fail-closed")
    return {"targets": sorted(requested), "permit_sha256": supplied}


def verify_rates(result: dict[str, Any], verification: dict[str, Any], currency: str, decision_point: str, decision_date: str) -> dict[str, Any]:
    if not isinstance(result, dict) or result.get("schema") != RATES_SELECTOR_SCHEMA or result.get("status") != "ROW_PERMIT_ISSUED":
        raise RuntimeError("invalid Rates selector result")
    row = result.get("row_permit")
    if not isinstance(row, dict) or row.get("schema") != RATES_ROW_SCHEMA:
        raise RuntimeError("invalid Rates row permit schema")
    supplied = row.get("row_permit_sha256")
    body = {k: v for k, v in row.items() if k != "row_permit_sha256"}
    if not isinstance(supplied, str) or sha256_obj(body) != supplied:
        raise RuntimeError("Rates row permit hash mismatch")

    target = f"{currency}.rates_2y_10y"
    if row.get("target") != target:
        raise RuntimeError("Rates target currency mismatch")
    if row.get("decision_point") != decision_point or row.get("decision_date") != decision_date:
        raise RuntimeError("Rates decision point/date mismatch")
    if row.get("row_consumption_authorized") is not True or row.get("same_day_use_allowed") is not False:
        raise RuntimeError("Rates row is not safely authorized")
    obs = date.fromisoformat(str(row.get("observation_date")))
    if not obs < date.fromisoformat(decision_date):
        raise RuntimeError("Rates observation is not strictly prior to decision date")

    if not isinstance(verification, dict) or verification.get("schema") != RATES_VERIFY_SCHEMA or verification.get("status") != "VERIFIED":
        raise RuntimeError("invalid Rates row verification")
    exact = {
        "target": row["target"],
        "decision_point": row["decision_point"],
        "observation_date": row["observation_date"],
        "row_permit_sha256": row["row_permit_sha256"],
        "row_consumption_authorized": True,
    }
    if any(verification.get(k) != v for k, v in exact.items()):
        raise RuntimeError("Rates verification does not exactly bind the row permit")
    return {
        "target": target,
        "observation_date": row["observation_date"],
        "row_permit_sha256": supplied,
        "evidence_semantic_rowset_sha256": row.get("evidence_semantic_rowset_sha256"),
    }


def bind(currency: str, decision_point: str, macro_permit: dict[str, Any], rates_result: dict[str, Any], rates_verification: dict[str, Any]) -> dict[str, Any]:
    currency = currency.strip().upper()
    if currency not in CURRENCIES:
        raise RuntimeError(f"unsupported currency: {currency}")
    decision_point, decision_date = parse_decision_point(decision_point)
    macro_as_of = decision_date[:7]
    macro = verify_macro_permit(macro_permit, currency, macro_as_of)
    rates = verify_rates(rates_result, rates_verification, currency, decision_point, decision_date)

    body = {
        "schema": SCHEMA,
        "status": "INPUT_LOAD_AUTHORIZED",
        "currency": currency,
        "decision_point": decision_point,
        "decision_date": decision_date,
        "macro_as_of": macro_as_of,
        "layers": {
            "Macro": {
                "authorized": True,
                "targets": macro["targets"],
                "permit_semantic_sha256": macro["permit_sha256"],
            },
            "Rates": {
                "authorized": True,
                **rates,
            },
        },
        "policy": {
            "fail_closed": True,
            "required_layers": ["Macro", "Rates"],
            "partial_layer_bundle_allowed": False,
            "runtime_history_fallback_allowed": False,
            "future_revision_fallback_allowed": False,
            "layer_substitution_allowed": False,
            "currency_substitution_allowed": False,
            "date_substitution_allowed": False,
            "upstream_macro_verification_required": True,
            "upstream_rates_row_verification_required": True,
            "missing_or_invalid_layer_action": "ABORT_INPUT_LOAD",
            "input_load_authorized": True,
            "backtest_execution_authorized": False,
        },
    }
    return {**body, "bundle_sha256": sha256_obj(body)}


def verify_bundle(bundle: dict[str, Any], macro_permit: dict[str, Any], rates_result: dict[str, Any], rates_verification: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, dict) or bundle.get("schema") != SCHEMA or bundle.get("status") != "INPUT_LOAD_AUTHORIZED":
        raise RuntimeError("invalid cross-layer bundle")
    supplied = bundle.get("bundle_sha256")
    body = {k: v for k, v in bundle.items() if k != "bundle_sha256"}
    if not isinstance(supplied, str) or sha256_obj(body) != supplied:
        raise RuntimeError("cross-layer bundle hash mismatch")
    expected = bind(bundle.get("currency", ""), bundle.get("decision_point", ""), macro_permit, rates_result, rates_verification)
    if expected != bundle:
        raise RuntimeError("cross-layer bundle is stale, tampered, or non-canonical")
    return {
        "schema": "GMFQ_CROSS_LAYER_BACKTEST_INPUT_VERIFICATION_V1",
        "status": "VERIFIED",
        "currency": bundle["currency"],
        "decision_point": bundle["decision_point"],
        "bundle_sha256": bundle["bundle_sha256"],
        "input_load_authorized": True,
        "backtest_execution_authorized": False,
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def emit(value: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("bind")
    b.add_argument("--currency", required=True)
    b.add_argument("--decision-point", required=True)
    b.add_argument("--macro-permit", type=Path, required=True)
    b.add_argument("--rates-row-result", type=Path, required=True)
    b.add_argument("--rates-row-verification", type=Path, required=True)
    b.add_argument("--output", type=Path)
    v = sub.add_parser("verify")
    v.add_argument("--bundle", type=Path, required=True)
    v.add_argument("--macro-permit", type=Path, required=True)
    v.add_argument("--rates-row-result", type=Path, required=True)
    v.add_argument("--rates-row-verification", type=Path, required=True)
    v.add_argument("--output", type=Path)
    args = ap.parse_args()

    macro = read_json(args.macro_permit)
    rates = read_json(args.rates_row_result)
    verification = read_json(args.rates_row_verification)
    if args.command == "bind":
        result = bind(args.currency, args.decision_point, macro, rates, verification)
    else:
        result = verify_bundle(read_json(args.bundle), macro, rates, verification)
    emit(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
