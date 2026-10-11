#!/usr/bin/env python3
"""Build a deterministic chronological series of already-verified walk-forward snapshots.

This composes point-in-time Macro + Rates snapshots into an ordered historical
sequence. It does not calculate signals, returns, position sizes, or authorize a
backtest. Every child snapshot must already be independently verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

SERIES_SCHEMA = "GMFQ_WALKFORWARD_SNAPSHOT_SERIES_V1"
VERIFY_SCHEMA = "GMFQ_WALKFORWARD_SNAPSHOT_SERIES_VERIFICATION_V1"
SNAPSHOT_SCHEMA = "GMFQ_WALKFORWARD_INPUT_SNAPSHOT_V1"
SNAPSHOT_VERIFY_SCHEMA = "GMFQ_WALKFORWARD_INPUT_SNAPSHOT_VERIFICATION_V1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_snapshot_pair(snapshot: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
    if snapshot.get("schema") != SNAPSHOT_SCHEMA or snapshot.get("status") != "SNAPSHOT_MATERIALIZED":
        raise RuntimeError("invalid child walk-forward snapshot")
    supplied = snapshot.get("snapshot_sha256")
    body = {k: v for k, v in snapshot.items() if k != "snapshot_sha256"}
    if not isinstance(supplied, str) or sha256_obj(body) != supplied:
        raise RuntimeError("child snapshot hash mismatch")

    policy = snapshot.get("policy") or {}
    required = {
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
    }
    if any(policy.get(k) != v for k, v in required.items()):
        raise RuntimeError("child snapshot policy is not fail-closed")

    if verification.get("schema") != SNAPSHOT_VERIFY_SCHEMA or verification.get("status") != "VERIFIED":
        raise RuntimeError("invalid child snapshot verification")
    exact = {
        "currency": snapshot.get("currency"),
        "decision_point": snapshot.get("decision_point"),
        "snapshot_sha256": supplied,
        "input_snapshot_materialized": True,
        "backtest_execution_authorized": False,
    }
    if any(verification.get(k) != v for k, v in exact.items()):
        raise RuntimeError("child snapshot verification does not exactly bind snapshot")

    decision_point = str(snapshot.get("decision_point"))
    decision_date = str(snapshot.get("decision_date"))
    if date.fromisoformat(decision_point) != date.fromisoformat(decision_date):
        raise RuntimeError("child snapshot decision point/date mismatch")

    macro_rows = ((snapshot.get("layers") or {}).get("Macro") or {}).get("rows")
    rates_row = ((snapshot.get("layers") or {}).get("Rates") or {}).get("row")
    if not isinstance(macro_rows, dict) or not macro_rows or not isinstance(rates_row, dict):
        raise RuntimeError("child snapshot missing Macro or Rates content")
    for target, row in macro_rows.items():
        if not isinstance(target, str) or not isinstance(row, dict):
            raise RuntimeError("invalid Macro child row")
        if not date.fromisoformat(str(row.get("release_date"))) < date.fromisoformat(decision_date):
            raise RuntimeError("Macro child row is not strictly prior to decision date")
    if not date.fromisoformat(str(rates_row.get("observation_date"))) < date.fromisoformat(decision_date):
        raise RuntimeError("Rates child row is not strictly prior to decision date")

    return snapshot


def build_series(pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    if len(pairs) < 2:
        raise RuntimeError("walk-forward series requires at least two snapshots")

    snapshots = [validate_snapshot_pair(s, v) for s, v in pairs]
    currencies = {str(s["currency"]) for s in snapshots}
    if len(currencies) != 1:
        raise RuntimeError("walk-forward series cannot mix currencies")
    currency = next(iter(currencies))

    decision_points = [str(s["decision_point"]) for s in snapshots]
    dates = [date.fromisoformat(x) for x in decision_points]
    if any(b <= a for a, b in zip(dates, dates[1:])):
        raise RuntimeError("decision points must be unique and strictly increasing")
    hashes = [str(s["snapshot_sha256"]) for s in snapshots]
    if len(set(hashes)) != len(hashes):
        raise RuntimeError("duplicate child snapshot hash")

    macro_target_sets = [tuple(sorted(s["layers"]["Macro"]["rows"])) for s in snapshots]
    if len(set(macro_target_sets)) != 1:
        raise RuntimeError("Macro target set must remain constant across series")
    rates_shapes = [tuple(sorted(s["layers"]["Rates"]["row"])) for s in snapshots]
    if len(set(rates_shapes)) != 1:
        raise RuntimeError("Rates row schema must remain constant across series")

    entries = []
    for s in snapshots:
        entries.append({
            "decision_point": s["decision_point"],
            "decision_date": s["decision_date"],
            "snapshot_sha256": s["snapshot_sha256"],
            "source_cross_layer_bundle_sha256": s["source_cross_layer_bundle_sha256"],
            "layers": s["layers"],
        })

    body = {
        "schema": SERIES_SCHEMA,
        "status": "SERIES_MATERIALIZED",
        "currency": currency,
        "coverage": {
            "start_decision_point": decision_points[0],
            "end_decision_point": decision_points[-1],
            "snapshot_count": len(entries),
        },
        "macro_targets": list(macro_target_sets[0]),
        "snapshots": entries,
        "policy": {
            "fail_closed": True,
            "strict_chronology_required": True,
            "duplicate_decision_points_allowed": False,
            "mixed_currency_allowed": False,
            "future_information_allowed": False,
            "same_day_macro_release_without_verified_timestamp_allowed": False,
            "runtime_history_fallback_allowed": False,
            "future_revision_fallback_allowed": False,
            "signal_calculation_allowed": False,
            "return_label_calculation_allowed": False,
            "position_sizing_allowed": False,
            "series_materialized": True,
            "backtest_execution_authorized": False,
        },
    }
    return {**body, "series_sha256": sha256_obj(body)}


def verify_series(series: dict[str, Any], pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    if series.get("schema") != SERIES_SCHEMA or series.get("status") != "SERIES_MATERIALIZED":
        raise RuntimeError("invalid walk-forward snapshot series")
    supplied = series.get("series_sha256")
    body = {k: v for k, v in series.items() if k != "series_sha256"}
    if not isinstance(supplied, str) or sha256_obj(body) != supplied:
        raise RuntimeError("walk-forward series hash mismatch")
    expected = build_series(pairs)
    if expected != series:
        raise RuntimeError("walk-forward series is stale, tampered, or non-canonical")
    return {
        "schema": VERIFY_SCHEMA,
        "status": "VERIFIED",
        "currency": series["currency"],
        "start_decision_point": series["coverage"]["start_decision_point"],
        "end_decision_point": series["coverage"]["end_decision_point"],
        "snapshot_count": series["coverage"]["snapshot_count"],
        "series_sha256": series["series_sha256"],
        "series_materialized": True,
        "backtest_execution_authorized": False,
    }


def load_pairs(snapshot_paths: list[Path], verification_paths: list[Path]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if len(snapshot_paths) != len(verification_paths):
        raise RuntimeError("snapshot/verification counts differ")
    return [(read_json(s), read_json(v)) for s, v in zip(snapshot_paths, verification_paths)]


def emit(value: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def configure(p: argparse.ArgumentParser, verify: bool = False) -> None:
    if verify:
        p.add_argument("--series", type=Path, required=True)
    p.add_argument("--snapshot", type=Path, action="append", required=True)
    p.add_argument("--snapshot-verification", type=Path, action="append", required=True)
    p.add_argument("--output", type=Path)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build"); configure(b)
    v = sub.add_parser("verify"); configure(v, True)
    args = ap.parse_args()
    pairs = load_pairs(args.snapshot, args.snapshot_verification)
    if args.command == "build":
        result = build_series(pairs)
    else:
        result = verify_series(read_json(args.series), pairs)
    emit(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
