#!/usr/bin/env python3
"""Select the latest certified Macro release knowable at a decision point.

A monthly Macro permit authorizes a *series*, not a same-month observation. This
selector closes that gap: it binds the permit to the exact canonical strict-PIT
receipt and rowset, then admits only a release whose publication date is strictly
prior to the decision date. Same-day use is forbidden unless a future contract
adds a verified publication timestamp.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "GMFQ_MACRO_TEMPORAL_ROW_SELECTOR_V1"
ROW_SCHEMA = "GMFQ_MACRO_TEMPORAL_ROW_PERMIT_V1"
VERIFY_SCHEMA = "GMFQ_MACRO_TEMPORAL_ROW_PERMIT_VERIFICATION_V1"
MACRO_PERMIT_SCHEMA = "GMFQ_BACKTEST_INPUT_PERMIT_V1"
VERDICT = "STRICT_DIRECT_ARCHIVAL_PIT_CERTIFIABLE"
TARGET_SPECS = {
    "EUR.inflation": {
        "value_field": "headline_hicp_yoy_pct",
        "semantic_fields": ["reference_month", "headline_hicp_yoy_pct", "release_date", "source_route", "pit_status"],
        "required_pit_status": "STRICT_FIRST_RELEASE_FLASH",
    },
    "EUR.labour": {
        "value_field": "unemployment_rate_pct",
        "semantic_fields": ["reference_month", "unemployment_rate_pct", "release_date", "release_geo_vintage", "source_route", "pit_status"],
        "required_pit_status": "STRICT_FIRST_RELEASE",
    },
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def parse_decision_point(value: str) -> tuple[str, str]:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("decision point is required")
    value = value.strip()
    if "T" not in value:
        return value, date.fromisoformat(value).isoformat()
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise RuntimeError("timestamp decision point requires explicit timezone")
    return value, dt.date().isoformat()


def verify_macro_permit(permit: dict[str, Any], target: str, decision_date: str) -> dict[str, Any]:
    if permit.get("schema") != MACRO_PERMIT_SCHEMA or permit.get("status") != "PASS":
        raise RuntimeError("invalid Macro permit schema/status")
    supplied = permit.get("permit_semantic_sha256")
    body = {k: v for k, v in permit.items() if k != "permit_semantic_sha256"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if not isinstance(supplied, str) or hashlib.sha256(raw).hexdigest() != supplied:
        raise RuntimeError("Macro permit semantic hash mismatch")
    if permit.get("as_of") != decision_date[:7]:
        raise RuntimeError("Macro permit month does not match decision date month")
    requested = permit.get("requested_targets")
    auth = permit.get("authorizations")
    if not isinstance(requested, list) or target not in requested:
        raise RuntimeError(f"Macro target not requested by permit: {target}")
    if not isinstance(auth, dict) or set(auth) != set(requested):
        raise RuntimeError("Macro permit authorization set mismatch")
    row = auth.get(target)
    if not isinstance(row, dict) or row.get("authorization") != "ALLOW_STRICT_PIT_ONLY":
        raise RuntimeError(f"Macro target not strict-PIT authorized: {target}")
    receipt_path = row.get("receipt")
    if not isinstance(receipt_path, str) or not receipt_path.startswith("validation/macro/"):
        raise RuntimeError("invalid Macro receipt path")
    if ".." in Path(receipt_path).parts:
        raise RuntimeError("invalid Macro receipt traversal")
    return {"permit_sha256": supplied, "receipt_path": receipt_path}


def load_receipt(receipt_path: str, target: str) -> dict[str, Any]:
    path = (ROOT / receipt_path).resolve()
    if ROOT.resolve() not in path.parents:
        raise RuntimeError("receipt path escapes repository")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("target") != target or receipt.get("verdict") != VERDICT:
        raise RuntimeError("Macro receipt target/verdict mismatch")
    digest = receipt.get("semantic_rowset_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise RuntimeError("Macro receipt missing semantic rowset hash")
    return receipt


def read_rows(csv_path: Path, target: str) -> list[dict[str, Any]]:
    spec = TARGET_SPECS.get(target)
    if spec is None:
        raise RuntimeError(f"Macro temporal selector target unsupported in V1: {target}")
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = [dict(r) for r in csv.DictReader(f)]
    if not rows:
        raise RuntimeError("Macro rowset is empty")
    seen: set[str] = set()
    prior_ref: str | None = None
    value_field = spec["value_field"]
    for row in rows:
        missing = [k for k in spec["semantic_fields"] if k not in row or row[k] == ""]
        if missing:
            raise RuntimeError(f"Macro row missing semantic fields {missing}")
        ref = row["reference_month"]
        if ref in seen:
            raise RuntimeError(f"duplicate Macro reference month: {ref}")
        if prior_ref is not None and ref <= prior_ref:
            raise RuntimeError("Macro rows must be strictly increasing by reference_month")
        seen.add(ref); prior_ref = ref
        date.fromisoformat(row["release_date"])
        try:
            value = float(row[value_field])
        except (TypeError, ValueError):
            raise RuntimeError(f"invalid Macro value for {target} {ref}")
        row[value_field] = value
        if row.get("pit_status") != spec["required_pit_status"]:
            raise RuntimeError(f"unexpected PIT status for {target} {ref}")
    return rows


def semantic_rowset_hash(target: str, rows: list[dict[str, Any]]) -> str:
    spec = TARGET_SPECS[target]
    payload = [{k: r[k] for k in spec["semantic_fields"]} for r in rows]
    # Materializers use ensure_ascii=False. Current semantic fields are ASCII, but
    # preserve their exact canonicalization contract anyway.
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def select_row(permit: dict[str, Any], csv_path: Path, target: str, decision_point: str) -> dict[str, Any]:
    if target not in TARGET_SPECS:
        raise RuntimeError(f"unsupported Macro temporal target: {target}")
    decision_point, decision_date = parse_decision_point(decision_point)
    permit_info = verify_macro_permit(permit, target, decision_date)
    receipt = load_receipt(permit_info["receipt_path"], target)
    rows = read_rows(csv_path, target)
    actual_hash = semantic_rowset_hash(target, rows)
    if actual_hash != receipt["semantic_rowset_sha256"]:
        raise RuntimeError("Macro rowset semantic hash does not match canonical receipt")

    coverage = receipt.get("coverage") or {}
    if rows[0]["reference_month"] != str(coverage.get("start"))[:7] or rows[-1]["reference_month"] != str(coverage.get("end"))[:7]:
        raise RuntimeError("Macro rowset bounds do not match certified receipt coverage")

    point = date.fromisoformat(decision_date)
    eligible = [r for r in rows if date.fromisoformat(r["release_date"]) < point]
    if not eligible:
        raise RuntimeError(f"no Macro release available strictly before {decision_date}: {target}")
    selected = max(eligible, key=lambda r: (r["release_date"], r["reference_month"]))
    if sum(1 for r in eligible if r["release_date"] == selected["release_date"]) != 1:
        raise RuntimeError("ambiguous latest Macro release date")

    value_field = TARGET_SPECS[target]["value_field"]
    row_body = {
        "schema": ROW_SCHEMA,
        "layer": "Macro",
        "target": target,
        "decision_point": decision_point,
        "decision_date": decision_date,
        "reference_month": selected["reference_month"],
        "release_date": selected["release_date"],
        "value_field": value_field,
        "value": selected[value_field],
        "source_route": selected.get("source_route"),
        "page_sha256": selected.get("page_sha256"),
        "pit_status": selected.get("pit_status"),
        "receipt_path": permit_info["receipt_path"],
        "evidence_semantic_rowset_sha256": actual_hash,
        "macro_permit_semantic_sha256": permit_info["permit_sha256"],
        "selection_policy": "LATEST_RELEASE_STRICTLY_PRIOR_TO_DECISION_DATE",
        "same_day_use_allowed": False,
        "row_consumption_authorized": True,
    }
    permit_out = {**row_body, "row_permit_sha256": sha256_obj(row_body)}
    return {
        "schema": SCHEMA,
        "status": "ROW_PERMIT_ISSUED",
        "policy": {
            "fail_closed": True,
            "canonical_receipt_hash_match_required": True,
            "latest_known_release_required": True,
            "same_day_use_allowed_without_verified_timestamp": False,
            "future_release_allowed": False,
            "current_revised_history_fallback_allowed": False,
            "missing_or_invalid_row_action": "ABORT_INPUT_SNAPSHOT",
        },
        "row_permit": permit_out,
    }


def verify_row_permit(result: dict[str, Any], permit: dict[str, Any], csv_path: Path) -> dict[str, Any]:
    if result.get("schema") != SCHEMA or result.get("status") != "ROW_PERMIT_ISSUED":
        raise RuntimeError("invalid Macro temporal selector result")
    row = result.get("row_permit")
    if not isinstance(row, dict) or row.get("schema") != ROW_SCHEMA:
        raise RuntimeError("invalid Macro row permit")
    supplied = row.get("row_permit_sha256")
    body = {k: v for k, v in row.items() if k != "row_permit_sha256"}
    if not isinstance(supplied, str) or sha256_obj(body) != supplied:
        raise RuntimeError("Macro row permit hash mismatch")
    expected = select_row(permit, csv_path, row.get("target", ""), row.get("decision_point", ""))
    if expected != result:
        raise RuntimeError("Macro row permit is stale, tampered, or non-canonical")
    return {
        "schema": VERIFY_SCHEMA,
        "status": "VERIFIED",
        "target": row["target"],
        "decision_point": row["decision_point"],
        "reference_month": row["reference_month"],
        "release_date": row["release_date"],
        "row_permit_sha256": row["row_permit_sha256"],
        "row_consumption_authorized": True,
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
    sel = sub.add_parser("select")
    sel.add_argument("--macro-permit", type=Path, required=True)
    sel.add_argument("--rowset-csv", type=Path, required=True)
    sel.add_argument("--target", required=True)
    sel.add_argument("--decision-point", required=True)
    sel.add_argument("--output", type=Path)
    ver = sub.add_parser("verify")
    ver.add_argument("--selector-result", type=Path, required=True)
    ver.add_argument("--macro-permit", type=Path, required=True)
    ver.add_argument("--rowset-csv", type=Path, required=True)
    ver.add_argument("--output", type=Path)
    args = ap.parse_args()
    macro = read_json(args.macro_permit)
    if args.command == "select":
        result = select_row(macro, args.rowset_csv, args.target, args.decision_point)
    else:
        result = verify_row_permit(read_json(args.selector_result), macro, args.rowset_csv)
    emit(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
