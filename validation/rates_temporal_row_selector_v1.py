#!/usr/bin/env python3
"""Fail-closed temporal row selector for certified Rates 2Y/10Y histories.

A Rates layer permit is necessary but not sufficient. This selector verifies the
upstream permit, proves that the supplied rowset is the exact semantic rowset
bound to that permit, then selects the latest observation that was knowable at
the requested decision point. Only the resulting row permit authorizes row
consumption by a future backtest loader.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "validation" / "rates_backtest_input_contract_v1.py"
SCHEMA = "GMFQ_RATES_TEMPORAL_ROW_SELECTOR_V1"
ROW_PERMIT_SCHEMA = "GMFQ_RATES_ROW_PERMIT_V1"
GENERIC_SEMANTIC_FIELDS = (
    "currency", "observation_date", "yield_2y", "yield_10y",
    "source_basis", "first_eligible_decision_date",
)
JPY_SEMANTIC_FIELDS = (
    "currency", "observation_date", "yield_2y", "yield_10y",
    "source_basis", "first_eligible_decision_point",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_contract_module():
    spec = importlib.util.spec_from_file_location("gmfq_rates_contract", CONTRACT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Rates backtest input contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_decision_point(value: str) -> tuple[datetime | None, str]:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("decision point is required")
    value = value.strip()
    if "T" not in value:
        return None, date.fromisoformat(value).isoformat()
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise RuntimeError("timestamp decision point must include an explicit timezone offset")
    return dt, dt.date().isoformat()


def semantic_rowset_hash(target: str, rows: list[dict[str, Any]]) -> str:
    fields = JPY_SEMANTIC_FIELDS if target == "JPY.rates_2y_10y" else GENERIC_SEMANTIC_FIELDS
    payload = []
    for row in rows:
        missing = [k for k in fields if k not in row]
        if missing:
            raise RuntimeError(f"row missing semantic fields {missing}: {target}")
        payload.append({k: row[k] for k in fields})
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_rows(target: str, rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("Rates rowset must contain rows")
    currency = target.split(".", 1)[0]
    out: list[dict[str, Any]] = []
    seen = set()
    prior = None
    for raw in rows:
        if not isinstance(raw, dict):
            raise RuntimeError("Rates row must be an object")
        row = dict(raw)
        if row.get("currency") != currency:
            raise RuntimeError(f"row currency mismatch for {target}")
        obs = date.fromisoformat(str(row.get("observation_date"))).isoformat()
        if obs in seen:
            raise RuntimeError(f"duplicate Rates observation date: {obs}")
        if prior is not None and obs <= prior:
            raise RuntimeError("Rates rows must be strictly increasing by observation_date")
        seen.add(obs); prior = obs
        for key in ("yield_2y", "yield_10y"):
            v = row.get(key)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not (-5.0 < float(v) < 25.0):
                raise RuntimeError(f"invalid {key} for {target} on {obs}")
        out.append(row)
    return out


def row_is_eligible(target: str, row: dict[str, Any], decision_point: str) -> bool:
    dt, decision_date = parse_decision_point(decision_point)
    obs = date.fromisoformat(row["observation_date"])
    if target == "JPY.rates_2y_10y":
        fp = row.get("first_eligible_decision_point")
        if not isinstance(fp, str) or not fp:
            raise RuntimeError("JPY row missing first_eligible_decision_point")
        eligible_after = datetime.fromisoformat(fp.replace("Z", "+00:00"))
        if eligible_after.tzinfo is None or eligible_after.utcoffset() is None:
            raise RuntimeError("JPY first eligible decision point lacks timezone")
        if dt is None:
            # A date-only decision cannot prove it occurred after the verified 09:30 JST release.
            return False
        return dt > eligible_after

    first = row.get("first_eligible_decision_date")
    if not isinstance(first, str):
        raise RuntimeError(f"generic Rates row missing first_eligible_decision_date: {target}")
    first_date = date.fromisoformat(first)
    if first_date <= obs:
        raise RuntimeError(f"invalid same-day/future eligibility marker: {target} {obs}")
    return date.fromisoformat(decision_date) >= first_date


def select_row(bundle: dict[str, Any], rowset: dict[str, Any], target: str, decision_point: str) -> dict[str, Any]:
    contract = load_contract_module()
    verified = contract.verify_bundle(bundle)
    _, decision_date = parse_decision_point(decision_point)
    if verified.get("decision_date") != decision_date:
        raise RuntimeError("decision point date does not match verified Rates layer permit")
    if target not in verified.get("targets", []):
        raise RuntimeError(f"target not authorized by Rates layer permit: {target}")

    permits = [p for p in bundle.get("permits", []) if p.get("target") == target]
    if len(permits) != 1:
        raise RuntimeError("expected exactly one matching Rates layer permit")
    layer_permit = permits[0]
    if layer_permit.get("row_consumption_authorized") is not False:
        raise RuntimeError("upstream Rates permit already claims row authorization")

    if not isinstance(rowset, dict):
        raise RuntimeError("Rates rowset must be an object")
    if rowset.get("status") != "PASS" or rowset.get("target") != target:
        raise RuntimeError("Rates rowset status/target mismatch")
    if rowset.get("evidence_class") != "TEMPORAL_PIT_OFFICIAL_MARKET_HISTORY":
        raise RuntimeError("Rates rowset evidence class mismatch")
    rows = validate_rows(target, rowset.get("rows"))
    actual_hash = semantic_rowset_hash(target, rows)
    expected_hash = layer_permit.get("evidence_semantic_rowset_sha256")
    if actual_hash != expected_hash:
        raise RuntimeError("Rates rowset semantic hash does not match certified layer permit")
    if rowset.get("semantic_rowset_sha256") != actual_hash:
        raise RuntimeError("Rates rowset self-declared semantic hash mismatch")

    eligible = [r for r in rows if row_is_eligible(target, r, decision_point)]
    if not eligible:
        raise RuntimeError(f"no temporally eligible Rates row for {target} at {decision_point}")
    selected = eligible[-1]
    if any(r["observation_date"] > selected["observation_date"] and row_is_eligible(target, r, decision_point) for r in rows):
        raise RuntimeError("latest-eligible-row invariant failed")

    row_body = {
        "schema": ROW_PERMIT_SCHEMA,
        "layer": "Rates",
        "target": target,
        "decision_point": decision_point,
        "decision_date": decision_date,
        "observation_date": selected["observation_date"],
        "yield_2y": selected["yield_2y"],
        "yield_10y": selected["yield_10y"],
        "curve_bp": selected.get("curve_bp"),
        "source_basis": selected.get("source_basis"),
        "first_eligible_decision_date": selected.get("first_eligible_decision_date"),
        "first_eligible_decision_point": selected.get("first_eligible_decision_point"),
        "availability_rule": selected.get("availability_rule"),
        "evidence_semantic_rowset_sha256": actual_hash,
        "layer_permit_sha256": layer_permit.get("permit_sha256"),
        "layer_bundle_sha256": bundle.get("bundle_sha256"),
        "selection_policy": "LATEST_TEMPORALLY_ELIGIBLE_CERTIFIED_2Y_10Y_ROW",
        "same_day_use_allowed": False,
        "row_consumption_authorized": True,
    }
    permit = {**row_body, "row_permit_sha256": sha256_obj(row_body)}
    return {
        "schema": SCHEMA,
        "status": "ROW_PERMIT_ISSUED",
        "policy": {
            "fail_closed": True,
            "latest_eligible_row_required": True,
            "rowset_hash_must_match_layer_permit": True,
            "same_day_use_allowed": False,
            "jpy_date_only_decision_allowed": False,
            "invalid_or_missing_row_permit_action": "ABORT_BACKTEST",
        },
        "row_permit": permit,
    }


def verify_row_permit(result: dict[str, Any], bundle: dict[str, Any], rowset: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict) or result.get("schema") != SCHEMA or result.get("status") != "ROW_PERMIT_ISSUED":
        raise RuntimeError("invalid Rates row selector result")
    permit = result.get("row_permit")
    if not isinstance(permit, dict):
        raise RuntimeError("missing Rates row permit")
    supplied = permit.get("row_permit_sha256")
    body = {k: v for k, v in permit.items() if k != "row_permit_sha256"}
    if not isinstance(supplied, str) or sha256_obj(body) != supplied:
        raise RuntimeError("Rates row permit hash mismatch")
    if permit.get("row_consumption_authorized") is not True:
        raise RuntimeError("Rates row permit does not authorize row consumption")
    expected = select_row(bundle, rowset, permit.get("target"), permit.get("decision_point"))
    if expected != result:
        raise RuntimeError("Rates row permit is stale, tampered, or non-canonical")
    return {
        "schema": "GMFQ_RATES_ROW_PERMIT_VERIFICATION_V1",
        "status": "VERIFIED",
        "target": permit["target"],
        "decision_point": permit["decision_point"],
        "observation_date": permit["observation_date"],
        "row_permit_sha256": permit["row_permit_sha256"],
        "row_consumption_authorized": True,
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def emit(value: dict[str, Any], path: Path | None) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    sel = sub.add_parser("select")
    sel.add_argument("--permit", type=Path, required=True)
    sel.add_argument("--rowset", type=Path, required=True)
    sel.add_argument("--target", required=True)
    sel.add_argument("--decision-point", required=True)
    sel.add_argument("--output", type=Path)
    ver = sub.add_parser("verify")
    ver.add_argument("--selector-result", type=Path, required=True)
    ver.add_argument("--permit", type=Path, required=True)
    ver.add_argument("--rowset", type=Path, required=True)
    ver.add_argument("--output", type=Path)
    args = ap.parse_args()
    if args.command == "select":
        result = select_row(read_json(args.permit), read_json(args.rowset), args.target, args.decision_point)
    else:
        result = verify_row_permit(read_json(args.selector_result), read_json(args.permit), read_json(args.rowset))
    emit(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
