#!/usr/bin/env python3
"""Select one temporally eligible canonical 2Y/10Y Rates row, fail closed.

The selector consumes only the frozen canonical Rates rowset store. It never
refetches market data and never falls back to live/runtime history.

Important: a row-selection receipt is NOT sufficient to authorize backtest
consumption. It must later be cryptographically/semantically bound to a valid
Rates layer permit from the Rates Backtest Input Contract.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "validation"
STORE = VALIDATION / "rates_pit_rowsets"
MANIFEST_PATH = STORE / "manifest_v1.json"
BUILDER_PATH = VALIDATION / "build_rates_canonical_rowset_store_v1.py"
SCHEMA = "GMFQ_TEMPORAL_RATE_ROW_SELECTION_V1"
VERIFY_SCHEMA = "GMFQ_TEMPORAL_RATE_ROW_SELECTION_VERIFICATION_V1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_builder():
    spec = importlib.util.spec_from_file_location("gmfq_rates_store", BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load canonical Rates rowset verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_store() -> dict[str, Any]:
    result = load_builder().verify()
    if result.get("status") != "VERIFIED":
        raise RuntimeError("canonical Rates rowset store is not VERIFIED")
    return result


def load_manifest() -> dict[str, Any]:
    verify_store()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("schema") != "GMFQ_RATES_CANONICAL_ROWSET_STORE_V1" or manifest.get("status") != "PASS":
        raise RuntimeError("invalid canonical Rates rowset manifest")
    return manifest


def iso_day(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except Exception as exc:
        raise RuntimeError(f"invalid ISO decision date: {value!r}") from exc


def jst_timestamp(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except Exception as exc:
        raise RuntimeError(f"invalid ISO decision timestamp: {value!r}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise RuntimeError("JPY decision timestamp must be timezone-aware")
    if dt.utcoffset() != timedelta(hours=9):
        raise RuntimeError("JPY decision timestamp must be expressed explicitly in JST (+09:00)")
    return dt


def load_evidence(entry: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / entry["canonical_evidence"]
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "PASS" or data.get("semantic_rowset_sha256") != entry.get("semantic_rowset_sha256"):
        raise RuntimeError("canonical Rates evidence no longer matches rowset manifest")
    return data


def enforce_certified_window(evidence: dict[str, Any], decision_date: str) -> None:
    coverage = evidence.get("coverage", {})
    end = coverage.get("end_date")
    if not isinstance(end, str) or decision_date > end:
        raise RuntimeError("decision point is after certified Rates coverage")
    if "start_date" in coverage:
        start = iso_day(coverage["start_date"])
        if decision_date <= start:
            raise RuntimeError("no prior certified Rates observation is temporally eligible")
        return
    if "start_year" in coverage:
        start_year = coverage["start_year"]
        if not isinstance(start_year, int):
            raise RuntimeError("invalid start_year in canonical Rates evidence")
        # Preserve the same fail-closed boundary rule as the walk-forward gate:
        # year-only evidence does not prove an exact first usable date.
        if int(decision_date[:4]) <= start_year:
            raise RuntimeError("boundary year is WITHHELD because coverage start is only proven at year resolution")
        return
    raise RuntimeError("canonical Rates evidence lacks certified coverage start")


def read_rows(entry: dict[str, Any]) -> list[dict[str, Any]]:
    path = ROOT / entry["rowset_file"]
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != entry["observations"]:
        raise RuntimeError("canonical Rates row count changed")
    for r in rows:
        r["yield_2y"] = float(r["yield_2y"])
        r["yield_10y"] = float(r["yield_10y"])
    return rows


def target_entry(manifest: dict[str, Any], target: str) -> tuple[str, dict[str, Any]]:
    matches = [(ccy, e) for ccy, e in manifest.get("entries", {}).items() if e.get("target") == target]
    if len(matches) != 1:
        raise RuntimeError(f"Rates target is not in canonical rowset store: {target}")
    return matches[0]


def select_row(target: str, decision_date: str | None, decision_timestamp: str | None) -> dict[str, Any]:
    manifest = load_manifest()
    ccy, entry = target_entry(manifest, target)
    evidence = load_evidence(entry)
    rows = read_rows(entry)

    if ccy == "JPY":
        if decision_date is not None or decision_timestamp is None:
            raise RuntimeError("JPY row selection requires --decision-timestamp in JST and forbids date-only mode")
        decision_dt = jst_timestamp(decision_timestamp)
        point_date = decision_dt.date().isoformat()
        enforce_certified_window(evidence, point_date)
        eligible = []
        for row in rows:
            boundary = jst_timestamp(row["first_eligible_decision_point"])
            if boundary < decision_dt:  # strict: decision_timestamp > 09:30 JST boundary
                eligible.append(row)
        selector_mode = "VERIFIED_TIMESTAMP_JST_STRICT_AFTER"
        normalized_decision = decision_dt.isoformat()
        boundary_field = "first_eligible_decision_point"
    else:
        if decision_timestamp is not None or decision_date is None:
            raise RuntimeError(f"{ccy} row selection requires --decision-date and forbids timestamp mode")
        point_date = iso_day(decision_date)
        enforce_certified_window(evidence, point_date)
        eligible = [r for r in rows if r["first_eligible_decision_date"] <= point_date]
        selector_mode = "CONSERVATIVE_DATE_ONLY"
        normalized_decision = point_date
        boundary_field = "first_eligible_decision_date"

    if not eligible:
        raise RuntimeError(f"no temporally eligible canonical Rates row for {target} at {normalized_decision}")
    selected = eligible[-1]
    if selected["observation_date"] >= point_date:
        raise RuntimeError("selector attempted same-day/future observation use")

    selected_row = {
        "observation_date": selected["observation_date"],
        "yield_2y": selected["yield_2y"],
        "yield_10y": selected["yield_10y"],
        "curve_bp": round((selected["yield_10y"] - selected["yield_2y"]) * 100.0, 6),
        "first_eligible_decision_date": selected["first_eligible_decision_date"],
    }
    if ccy == "JPY":
        selected_row["first_eligible_decision_point"] = selected["first_eligible_decision_point"]

    row_body = {
        "target": target,
        "source_basis": entry["source_basis"],
        **selected_row,
    }
    body = {
        "schema": SCHEMA,
        "status": "ROW_SELECTED",
        "target": target,
        "currency": ccy,
        "selector_mode": selector_mode,
        "decision_point": normalized_decision,
        "decision_date": point_date,
        "selection_policy": {
            "fail_closed": True,
            "canonical_frozen_rowset_only": True,
            "runtime_history_fallback_allowed": False,
            "secondary_source_fallback_allowed": False,
            "same_day_use_allowed": False,
            "eligibility_boundary_field": boundary_field,
            "jpy_strict_timestamp_comparison": ccy == "JPY",
        },
        "rowset": {
            "file": entry["rowset_file"],
            "file_sha256": entry["rowset_file_sha256"],
            "semantic_rowset_sha256": entry["semantic_rowset_sha256"],
            "canonical_evidence": entry["canonical_evidence"],
        },
        "selected_row": {**selected_row, "row_sha256": sha256_obj(row_body)},
        "backtest_consumption_authorized": False,
        "next_required_binding": "BIND_ROW_SELECTION_TO_VALID_RATES_LAYER_PERMIT",
    }
    return {**body, "selection_receipt_sha256": sha256_obj(body)}


def verify_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("schema") != SCHEMA or receipt.get("status") != "ROW_SELECTED":
        raise RuntimeError("invalid Rates row-selection receipt schema/status")
    supplied = receipt.get("selection_receipt_sha256")
    body = {k: v for k, v in receipt.items() if k != "selection_receipt_sha256"}
    if not isinstance(supplied, str) or sha256_obj(body) != supplied:
        raise RuntimeError("Rates row-selection receipt hash mismatch")
    if receipt.get("backtest_consumption_authorized") is not False:
        raise RuntimeError("row-selection receipt illegally authorizes backtest consumption")

    if receipt.get("currency") == "JPY":
        expected = select_row(receipt["target"], None, receipt["decision_point"])
    else:
        expected = select_row(receipt["target"], receipt["decision_date"], None)
    if expected != receipt:
        raise RuntimeError("Rates row-selection receipt is stale, tampered, or non-canonical")
    return {
        "schema": VERIFY_SCHEMA,
        "status": "VERIFIED",
        "target": receipt["target"],
        "decision_point": receipt["decision_point"],
        "selection_receipt_sha256": receipt["selection_receipt_sha256"],
        "backtest_consumption_authorized": False,
        "next_required_binding": receipt["next_required_binding"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("select")
    s.add_argument("--target", required=True)
    s.add_argument("--decision-date")
    s.add_argument("--decision-timestamp")
    s.add_argument("--output", type=Path)
    v = sub.add_parser("verify")
    v.add_argument("--receipt", type=Path, required=True)
    v.add_argument("--output", type=Path)
    args = ap.parse_args()

    if args.command == "select":
        result = select_row(args.target, args.decision_date, args.decision_timestamp)
    else:
        result = verify_receipt(json.loads(args.receipt.read_text(encoding="utf-8")))
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
