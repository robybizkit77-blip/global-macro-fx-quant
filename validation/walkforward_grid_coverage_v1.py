#!/usr/bin/env python3
"""Audit complete monthly walk-forward snapshot coverage without running a backtest."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

SNAPSHOT_SCHEMA = "GMFQ_WALKFORWARD_INPUT_SNAPSHOT_V1"
VERIFY_SCHEMA = "GMFQ_WALKFORWARD_INPUT_SNAPSHOT_VERIFICATION_V1"
SCHEMA = "GMFQ_WALKFORWARD_GRID_COVERAGE_V1"
VERIFY_OUT_SCHEMA = "GMFQ_WALKFORWARD_GRID_COVERAGE_VERIFICATION_V1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def month_iter(start: date, end: date, day: int) -> list[str]:
    if start.day != day or end.day != day:
        raise RuntimeError("start/end must use requested grid day")
    out: list[str] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}-{day:02d}")
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return out


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_snapshot(snapshot: dict[str, Any], verification: dict[str, Any], expected_dp: str, currency: str) -> dict[str, Any]:
    if snapshot.get("schema") != SNAPSHOT_SCHEMA or snapshot.get("status") != "SNAPSHOT_MATERIALIZED":
        raise RuntimeError(f"invalid snapshot at {expected_dp}")
    supplied = snapshot.get("snapshot_sha256")
    body = {k: v for k, v in snapshot.items() if k != "snapshot_sha256"}
    if not isinstance(supplied, str) or sha256_obj(body) != supplied:
        raise RuntimeError(f"snapshot hash mismatch at {expected_dp}")
    if snapshot.get("currency") != currency or snapshot.get("decision_point") != expected_dp:
        raise RuntimeError(f"snapshot identity mismatch at {expected_dp}")
    policy = snapshot.get("policy") or {}
    required_false = ["signal_calculation_allowed", "return_label_calculation_allowed", "position_sizing_allowed", "backtest_execution_authorized"]
    if any(policy.get(k) is not False for k in required_false):
        raise RuntimeError(f"unsafe snapshot policy at {expected_dp}")
    if policy.get("input_snapshot_materialized") is not True or policy.get("fail_closed") is not True:
        raise RuntimeError(f"snapshot is not fail-closed at {expected_dp}")
    if verification.get("schema") != VERIFY_SCHEMA or verification.get("status") != "VERIFIED":
        raise RuntimeError(f"invalid snapshot verification at {expected_dp}")
    if verification.get("currency") != currency or verification.get("decision_point") != expected_dp:
        raise RuntimeError(f"verification identity mismatch at {expected_dp}")
    if verification.get("snapshot_sha256") != supplied or verification.get("backtest_execution_authorized") is not False:
        raise RuntimeError(f"verification binding mismatch at {expected_dp}")
    for row in (snapshot.get("layers", {}).get("Macro", {}).get("rows") or {}).values():
        if str(row.get("release_date")) >= expected_dp:
            raise RuntimeError(f"future/same-day Macro row at {expected_dp}")
    rates = snapshot.get("layers", {}).get("Rates", {}).get("row") or {}
    if str(rates.get("observation_date")) >= expected_dp:
        raise RuntimeError(f"future/same-day Rates row at {expected_dp}")
    return {
        "decision_point": expected_dp,
        "snapshot_sha256": supplied,
        "macro_reference_months": {k: v.get("reference_month") for k, v in sorted(snapshot["layers"]["Macro"]["rows"].items())},
        "rates_observation_date": rates.get("observation_date"),
    }


def build(directory: Path, start: date, end: date, day: int, currency: str) -> dict[str, Any]:
    expected = month_iter(start, end, day)
    entries: list[dict[str, Any]] = []
    missing: list[str] = []
    for dp in expected:
        snap_path = directory / f"{dp}-snapshot.json"
        ver_path = directory / f"{dp}-snapshot-verified.json"
        if not snap_path.exists() or not ver_path.exists():
            missing.append(dp)
            continue
        entries.append(validate_snapshot(read_json(snap_path), read_json(ver_path), dp, currency))
    if missing:
        raise RuntimeError(f"walk-forward grid has missing/ineligible dates: {missing}")
    hashes = [x["snapshot_sha256"] for x in entries]
    if len(set(hashes)) != len(hashes):
        raise RuntimeError("duplicate child snapshot hash in grid")
    body = {
        "schema": SCHEMA,
        "status": "FULL_GRID_COVERAGE_VERIFIED",
        "currency": currency,
        "grid": {"frequency": "MONTHLY", "calendar_day": day, "start": expected[0], "end": expected[-1], "expected_points": len(expected), "eligible_points": len(entries), "coverage_ratio": 1.0},
        "entries": entries,
        "policy": {
            "fail_closed": True,
            "missing_grid_points_allowed": False,
            "future_information_allowed": False,
            "same_day_unverified_information_allowed": False,
            "signal_calculation_allowed": False,
            "return_label_calculation_allowed": False,
            "position_sizing_allowed": False,
            "backtest_execution_authorized": False,
        },
    }
    return {**body, "grid_sha256": sha256_obj(body)}


def verify(grid: dict[str, Any], directory: Path, start: date, end: date, day: int, currency: str) -> dict[str, Any]:
    if grid.get("schema") != SCHEMA or grid.get("status") != "FULL_GRID_COVERAGE_VERIFIED":
        raise RuntimeError("invalid grid coverage object")
    supplied = grid.get("grid_sha256")
    body = {k: v for k, v in grid.items() if k != "grid_sha256"}
    if not isinstance(supplied, str) or sha256_obj(body) != supplied:
        raise RuntimeError("grid hash mismatch")
    expected = build(directory, start, end, day, currency)
    if expected != grid:
        raise RuntimeError("grid is stale, tampered, or non-canonical")
    return {
        "schema": VERIFY_OUT_SCHEMA,
        "status": "VERIFIED",
        "currency": currency,
        "grid_sha256": supplied,
        "eligible_points": grid["grid"]["eligible_points"],
        "coverage_ratio": grid["grid"]["coverage_ratio"],
        "backtest_execution_authorized": False,
    }


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
    for name in ("build", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--directory", type=Path, required=True)
        p.add_argument("--start", type=date.fromisoformat, required=True)
        p.add_argument("--end", type=date.fromisoformat, required=True)
        p.add_argument("--day", type=int, default=10)
        p.add_argument("--currency", default="EUR")
        if name == "verify":
            p.add_argument("--grid", type=Path, required=True)
        p.add_argument("--output", type=Path)
    args = ap.parse_args()
    if args.command == "build":
        result = build(args.directory, args.start, args.end, args.day, args.currency)
    else:
        result = verify(read_json(args.grid), args.directory, args.start, args.end, args.day, args.currency)
    emit(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
