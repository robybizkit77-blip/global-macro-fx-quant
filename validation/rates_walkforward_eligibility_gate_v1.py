#!/usr/bin/env python3
"""Fail-closed eligibility gate for Rates walk-forward/backtest use.

Only currencies with one canonical official Temporal-PIT 2Y/10Y evidence file are
admitted. Missing currencies are WITHHELD. The gate preserves each source's own
temporal release rule and never permits same-day use when the evidence forbids it.

This module decides whether a Rates layer is eligible for a decision date. It does
not select a market observation. A downstream loader must still select only a row
whose evidence-specific temporal eligibility rule is satisfied at the decision
point.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALIDATION_DIR = ROOT / "validation"
EVIDENCE_CLASS = "TEMPORAL_PIT_OFFICIAL_MARKET_HISTORY"
EXPECTED_CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
EXPECTED_TARGETS = {f"{ccy}.rates_2y_10y" for ccy in EXPECTED_CURRENCIES}


def iso_day(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"invalid date {value!r}")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid ISO date {value!r}") from exc
    return parsed.isoformat()


def evidence_ref(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        # Test harnesses may stage exact evidence copies outside the repository.
        # Production discovery still scans VALIDATION_DIR under ROOT.
        return path.name


def coverage_bounds(coverage: Any) -> tuple[str | None, int | None, str]:
    if not isinstance(coverage, dict):
        raise RuntimeError("coverage must be an object")
    end = iso_day(coverage.get("end_date"))
    if "start_date" in coverage:
        start = iso_day(coverage["start_date"])
        if start > end:
            raise RuntimeError(f"inverted coverage {start}>{end}")
        return start, None, end
    if "start_year" in coverage:
        year = coverage["start_year"]
        if not isinstance(year, int) or not 1900 <= year <= 2200:
            raise RuntimeError(f"invalid start_year {year!r}")
        if year > int(end[:4]):
            raise RuntimeError(f"start_year {year} after coverage end {end}")
        return None, year, end
    raise RuntimeError("coverage lacks start_date/start_year")


def validate_evidence(path: Path, data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    target = data.get("target")
    if target not in EXPECTED_TARGETS:
        raise RuntimeError(f"unknown Rates target {target!r}: {path.name}")
    if data.get("status") != "PASS":
        raise RuntimeError(f"non-PASS Rates evidence present for {target}: {path.name}")
    if data.get("evidence_class") != EVIDENCE_CLASS:
        raise RuntimeError(f"unexpected evidence class for {target}: {path.name}")

    contract = data.get("series_contract")
    if not isinstance(contract, dict):
        raise RuntimeError(f"missing series_contract for {target}")
    if contract.get("tenors") != ["2Y", "10Y"]:
        raise RuntimeError(f"unexpected tenor contract for {target}")
    if contract.get("same_observation_date_required") is not True:
        raise RuntimeError(f"same-observation-date invariant missing for {target}")
    if contract.get("same_source_family_required") is not True:
        raise RuntimeError(f"same-source-family invariant missing for {target}")

    temporal = data.get("temporal_contract")
    if not isinstance(temporal, dict):
        raise RuntimeError(f"missing temporal_contract for {target}")
    if temporal.get("same_day_use_allowed") is not False:
        raise RuntimeError(f"same-day use not explicitly forbidden for {target}")
    eligibility_rule = temporal.get("eligibility")
    if not isinstance(eligibility_rule, str) or not eligibility_rule.strip():
        raise RuntimeError(f"missing temporal eligibility rule for {target}")

    invariants = data.get("invariants")
    if not isinstance(invariants, dict):
        raise RuntimeError(f"missing invariants for {target}")
    required_true = (
        "official_source_only",
        "same_basis_2y_10y",
        "same_day_lookahead_prevented",
        "two_materializations_semantically_identical",
    )
    for key in required_true:
        if invariants.get(key) is not True:
            raise RuntimeError(f"required invariant {key}=true missing for {target}")
    if invariants.get("secondary_source_fallback_used") is not False:
        raise RuntimeError(f"secondary-source fallback detected for {target}")

    start_date, start_year, end_date = coverage_bounds(data.get("coverage"))
    return target, {
        "authority": data.get("authority"),
        "coverage_start_date": start_date,
        "coverage_start_year": start_year,
        "coverage_end_date": end_date,
        "temporal_eligibility_rule": eligibility_rule,
        "same_day_use_allowed": False,
        "evidence": evidence_ref(path),
        "semantic_rowset_sha256": data.get("semantic_rowset_sha256"),
    }


def load_evidence() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in sorted(VALIDATION_DIR.glob("*_RATES_TEMPORAL_PIT_EVIDENCE_V1_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        target, normalized = validate_evidence(path, data)
        if target in rows:
            raise RuntimeError(f"duplicate canonical Rates evidence for {target}: {path.name}")
        rows[target] = normalized
    return rows


def date_in_certified_window(point: str, evidence: dict[str, Any]) -> tuple[bool, str]:
    end = evidence["coverage_end_date"]
    if point > end:
        return False, "DECISION_DATE_AFTER_CERTIFIED_COVERAGE"

    start_date = evidence["coverage_start_date"]
    if start_date is not None:
        # Strictly later than the first observation date because same-day use is forbidden.
        if point <= start_date:
            return False, "NO_PRIOR_TEMPORALLY_ELIGIBLE_RATE_OBSERVATION"
        return True, "DATE_INSIDE_CERTIFIED_WINDOW__ROW_MUST_PASS_SOURCE_TEMPORAL_RULE"

    start_year = evidence["coverage_start_year"]
    # If only a start year is proven, fail closed for that whole boundary year.
    if int(point[:4]) <= start_year:
        return False, "COVERAGE_START_ONLY_PROVEN_AT_YEAR_RESOLUTION"
    return True, "DATE_INSIDE_CERTIFIED_WINDOW__ROW_MUST_PASS_SOURCE_TEMPORAL_RULE"


def build(decision_date: str | None) -> dict[str, Any]:
    evidence = load_evidence()
    point = iso_day(decision_date) if decision_date else None
    targets: dict[str, dict[str, Any]] = {}
    certified = 0
    eligible = 0

    for ccy in EXPECTED_CURRENCIES:
        target = f"{ccy}.rates_2y_10y"
        item = evidence.get(target)
        if item is None:
            targets[target] = {
                "certification": "WITHHELD",
                "backtest_eligible": False,
                "reason": "NO_CANONICAL_TEMPORAL_PIT_RATES_EVIDENCE",
            }
            continue

        certified += 1
        is_eligible = True
        reason = "CANONICAL_TEMPORAL_PIT_RATES_EVIDENCE_PRESENT"
        if point is not None:
            is_eligible, reason = date_in_certified_window(point, item)
        if is_eligible:
            eligible += 1

        targets[target] = {
            "certification": "CERTIFIED",
            "backtest_eligible": is_eligible,
            "reason": reason,
            "coverage": {
                "start_date": item["coverage_start_date"],
                "start_year": item["coverage_start_year"],
                "end_date": item["coverage_end_date"],
            },
            "authority": item["authority"],
            "evidence": item["evidence"],
            "temporal_eligibility_rule": item["temporal_eligibility_rule"],
            "same_day_use_allowed": False,
            "semantic_rowset_sha256": item["semantic_rowset_sha256"],
        }

    return {
        "schema": "GMFQ_RATES_WALKFORWARD_ELIGIBILITY_GATE_V1",
        "status": "PASS",
        "decision_date": point,
        "policy": {
            "fail_closed": True,
            "required_evidence_class": EVIDENCE_CLASS,
            "official_source_only": True,
            "same_basis_2y_10y_required": True,
            "same_source_family_required": True,
            "secondary_source_fallback_allowed": False,
            "same_day_use_allowed": False,
            "missing_evidence_action": "WITHHOLD",
            "date_outside_certified_coverage_action": "WITHHOLD",
            "downstream_row_selection_requirement": "SELECT_ONLY_OBSERVATIONS_SATISFYING_THE_EVIDENCE_SPECIFIC_TEMPORAL_ELIGIBILITY_RULE_AT_THE_DECISION_POINT",
        },
        "expected_targets": len(EXPECTED_CURRENCIES),
        "certified_targets": certified,
        "eligible_targets": eligible,
        "withheld_targets": len(EXPECTED_CURRENCIES) - eligible,
        "targets": targets,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-date", help="Backtest decision date YYYY-MM-DD")
    parser.add_argument("--expect-certified-count", type=int)
    parser.add_argument("--expect-eligible-count", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = build(args.decision_date)
    if args.expect_certified_count is not None and result["certified_targets"] != args.expect_certified_count:
        raise RuntimeError(
            f"certified target count changed: {result['certified_targets']} != {args.expect_certified_count}"
        )
    if args.expect_eligible_count is not None and result["eligible_targets"] != args.expect_eligible_count:
        raise RuntimeError(
            f"eligible target count changed: {result['eligible_targets']} != {args.expect_eligible_count}"
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
