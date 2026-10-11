#!/usr/bin/env python3
"""Fail-closed eligibility gate for Macro walk-forward/backtest use.

The gate only admits a Macro series when main contains exactly one canonical
strict-PIT receipt for that target with verdict
STRICT_DIRECT_ARCHIVAL_PIT_CERTIFIABLE and the requested as-of month lies
inside the receipt's certified coverage window.

Missing receipts are WITHHELD, never silently backfilled from runtime history.
Malformed/duplicate/unknown receipts fail the gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MACRO_DIR = ROOT / "validation" / "macro"
VERDICT = "STRICT_DIRECT_ARCHIVAL_PIT_CERTIFIABLE"

EXPECTED_TARGETS = tuple(
    f"{ccy}.{layer}"
    for ccy in ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
    for layer in ("inflation", "labour")
)
EXPECTED_SET = set(EXPECTED_TARGETS)


def ym(value: str) -> str:
    if not isinstance(value, str) or len(value) < 7 or value[4] != "-":
        raise ValueError(f"invalid coverage/as-of value: {value!r}")
    out = value[:7]
    year, month = out.split("-")
    if len(year) != 4 or not year.isdigit() or not month.isdigit() or not 1 <= int(month) <= 12:
        raise ValueError(f"invalid YYYY-MM value: {value!r}")
    return out


def load_receipts() -> tuple[dict[str, dict[str, Any]], list[str]]:
    receipts: dict[str, dict[str, Any]] = {}
    files: list[str] = []
    for path in sorted(MACRO_DIR.glob("*_strict_pit_receipt_v1_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        target = data.get("target")
        if target not in EXPECTED_SET:
            raise RuntimeError(f"unknown strict-PIT receipt target {target!r}: {path.name}")
        if target in receipts:
            raise RuntimeError(f"duplicate strict-PIT receipt target {target}: {path.name}")
        if data.get("verdict") != VERDICT:
            raise RuntimeError(f"non-certifiable receipt present for {target}: {path.name}")
        coverage = data.get("coverage")
        if not isinstance(coverage, dict) or "start" not in coverage or "end" not in coverage:
            raise RuntimeError(f"missing coverage in receipt for {target}: {path.name}")
        start, end = ym(coverage["start"]), ym(coverage["end"])
        if start > end:
            raise RuntimeError(f"inverted coverage for {target}: {start}>{end}")
        data["_coverage_start"] = start
        data["_coverage_end"] = end
        data["_receipt_file"] = str(path.relative_to(ROOT))
        receipts[target] = data
        files.append(str(path.relative_to(ROOT)))
    return receipts, files


def build(as_of: str | None) -> dict[str, Any]:
    receipts, files = load_receipts()
    point = ym(as_of) if as_of else None
    rows: dict[str, dict[str, Any]] = {}
    certified = 0
    eligible = 0

    for target in EXPECTED_TARGETS:
        receipt = receipts.get(target)
        if receipt is None:
            rows[target] = {
                "certification": "WITHHELD",
                "backtest_eligible": False,
                "reason": "NO_CANONICAL_STRICT_FULL_WINDOW_PIT_RECEIPT",
            }
            continue

        certified += 1
        start = receipt["_coverage_start"]
        end = receipt["_coverage_end"]
        in_window = point is None or start <= point <= end
        if in_window:
            eligible += 1
            reason = "STRICT_PIT_RECEIPT_AND_DATE_IN_CERTIFIED_WINDOW" if point else "STRICT_PIT_RECEIPT_PRESENT"
        else:
            reason = "AS_OF_OUTSIDE_CERTIFIED_WINDOW"
        rows[target] = {
            "certification": "CERTIFIED",
            "backtest_eligible": bool(in_window),
            "reason": reason,
            "coverage": {"start": start, "end": end},
            "receipt": receipt["_receipt_file"],
        }

    return {
        "schema": "GMFQ_MACRO_WALKFORWARD_ELIGIBILITY_GATE_V1",
        "status": "PASS",
        "policy": {
            "fail_closed": True,
            "required_verdict": VERDICT,
            "runtime_history_fallback_allowed": False,
            "future_revision_fallback_allowed": False,
            "missing_receipt_action": "WITHHOLD",
            "date_outside_certified_coverage_action": "WITHHOLD",
        },
        "as_of": point,
        "expected_targets": len(EXPECTED_TARGETS),
        "certified_targets": certified,
        "eligible_targets": eligible,
        "withheld_targets": len(EXPECTED_TARGETS) - eligible,
        "receipt_files_scanned": files,
        "targets": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", help="Backtest information month YYYY-MM")
    parser.add_argument("--expect-certified-count", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = build(args.as_of)
    if args.expect_certified_count is not None and result["certified_targets"] != args.expect_certified_count:
        raise RuntimeError(
            f"certified target count changed: {result['certified_targets']} != {args.expect_certified_count}"
        )

    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
