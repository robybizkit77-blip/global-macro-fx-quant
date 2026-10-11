#!/usr/bin/env python3
"""Fail-closed walk-forward eligibility gate for CB Pricing / Market Pricing.

Today the canonical repository contains a Temporal-PIT contract but no PASS
historical CB-pricing evidence files. Therefore all eight currencies are
WITHHELD. The gate is intentionally date-aware so future *partial* certified
coverage can become eligible only inside its exact certified interval, without
pretending that the same source/instrument existed earlier.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "validation"
CB_DIR = VALIDATION / "cb_pricing"
CONTRACT_PATH = VALIDATION / "CB_PRICING_TEMPORAL_PIT_CONTRACT_V1_2026-10-11.json"
EXPECTED_CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
EVIDENCE_SCHEMA = "GMFQ_CB_PRICING_TEMPORAL_PIT_EVIDENCE_V1"
LAYER = "Central Banks / Market Pricing"


def iso_day(value: str) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"invalid date {value!r}")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"invalid ISO date {value!r}") from exc


def load_contract() -> dict[str, Any]:
    d = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if d.get("schema") != "GMFQ_CB_PRICING_TEMPORAL_PIT_CONTRACT_V1":
        raise RuntimeError("unexpected CB Pricing temporal contract schema")
    scope = d.get("scope", {})
    if scope.get("layer") != LAYER:
        raise RuntimeError("CB Pricing temporal contract layer mismatch")
    if tuple(scope.get("currencies", [])) != EXPECTED_CURRENCIES:
        raise RuntimeError("CB Pricing temporal contract currency universe changed")
    rules = d.get("core_rules", {})
    required_true = (
        "official_or_directly_licensed_source_required",
        "homogeneous_basis_required",
        "same_instrument_family_required_for_current_and_references",
        "no_secondary_price_fallback",
        "no_lookahead",
        "fail_closed_on_missing_or_ambiguous_publication_time",
        "raw_source_hash_required",
        "semantic_replay_required",
    )
    for key in required_true:
        if rules.get(key) is not True:
            raise RuntimeError(f"required CB Pricing contract rule {key}=true missing")
    return d


def validate_evidence(path: Path, d: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if d.get("schema") != EVIDENCE_SCHEMA:
        raise RuntimeError(f"unexpected CB Pricing evidence schema: {path.name}")
    if d.get("status") != "PASS":
        raise RuntimeError(f"non-PASS evidence file present: {path.name}")
    if d.get("layer") != LAYER:
        raise RuntimeError(f"layer mismatch in {path.name}")
    ccy = d.get("currency")
    if ccy not in EXPECTED_CURRENCIES:
        raise RuntimeError(f"unknown CB Pricing currency {ccy!r}")

    coverage = d.get("coverage")
    if not isinstance(coverage, dict):
        raise RuntimeError(f"missing coverage for {ccy}")
    start = iso_day(coverage.get("start_date"))
    end = iso_day(coverage.get("end_date"))
    if start > end:
        raise RuntimeError(f"inverted CB Pricing coverage for {ccy}")

    temporal = d.get("temporal_contract")
    if not isinstance(temporal, dict):
        raise RuntimeError(f"missing temporal contract for {ccy}")
    same_day = temporal.get("same_day_use_allowed")
    if same_day not in (False, True):
        raise RuntimeError(f"same-day policy not explicit for {ccy}")
    if same_day is True:
        publication = temporal.get("verified_publication_timestamp_rule")
        if not isinstance(publication, str) or not publication.strip():
            raise RuntimeError(f"same-day CB Pricing use lacks verified publication timestamp rule for {ccy}")
    eligibility = temporal.get("eligibility")
    if not isinstance(eligibility, str) or not eligibility.strip():
        raise RuntimeError(f"missing CB Pricing temporal eligibility rule for {ccy}")

    source = d.get("source_contract")
    if not isinstance(source, dict):
        raise RuntimeError(f"missing source contract for {ccy}")
    required_source_true = (
        "official_or_directly_licensed",
        "homogeneous_basis",
        "same_instrument_family",
        "no_secondary_price_fallback",
        "deterministic_horizon_mapping",
    )
    for key in required_source_true:
        if source.get(key) is not True:
            raise RuntimeError(f"source invariant {key}=true missing for {ccy}")

    integrity = d.get("integrity")
    if not isinstance(integrity, dict):
        raise RuntimeError(f"missing integrity section for {ccy}")
    raw_hash = integrity.get("raw_source_sha256")
    semantic_hash = integrity.get("semantic_replay_sha256")
    if not isinstance(raw_hash, str) or len(raw_hash) != 64:
        raise RuntimeError(f"invalid raw source hash for {ccy}")
    if not isinstance(semantic_hash, str) or len(semantic_hash) != 64:
        raise RuntimeError(f"invalid semantic replay hash for {ccy}")
    if integrity.get("two_independent_materializations_equal") is not True:
        raise RuntimeError(f"independent CB Pricing materializations not proven equal for {ccy}")

    return ccy, {
        "coverage_start_date": start,
        "coverage_end_date": end,
        "same_day_use_allowed": same_day,
        "eligibility_rule": eligibility,
        "authority": d.get("authority"),
        "instrument": d.get("instrument"),
        "evidence": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name,
        "raw_source_sha256": raw_hash,
        "semantic_replay_sha256": semantic_hash,
    }


def load_evidence() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not CB_DIR.exists():
        return rows
    for path in sorted(CB_DIR.glob("*_TEMPORAL_PIT_EVIDENCE_V1*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        ccy, normalized = validate_evidence(path, d)
        if ccy in rows:
            raise RuntimeError(f"duplicate canonical CB Pricing evidence for {ccy}")
        rows[ccy] = normalized
    return rows


def in_window(point: str, evidence: dict[str, Any]) -> tuple[bool, str]:
    if point < evidence["coverage_start_date"]:
        return False, "DECISION_DATE_BEFORE_CERTIFIED_COVERAGE"
    if point > evidence["coverage_end_date"]:
        return False, "DECISION_DATE_AFTER_CERTIFIED_COVERAGE"
    return True, "DATE_INSIDE_CERTIFIED_COVERAGE__OBSERVATION_MUST_STILL_PASS_TEMPORAL_RULE"


def build(decision_date: str | None) -> dict[str, Any]:
    contract = load_contract()
    evidence = load_evidence()
    point = iso_day(decision_date) if decision_date else None
    targets: dict[str, Any] = {}
    eligible = 0

    for ccy in EXPECTED_CURRENCIES:
        item = evidence.get(ccy)
        if item is None:
            original = (contract.get("currently_withheld_sources", {}).get(ccy)
                        or contract.get("currently_certifiable_sources", {}).get(ccy)
                        or {})
            targets[ccy] = {
                "certification": "WITHHELD",
                "backtest_eligible": False,
                "reason": "NO_CANONICAL_PASS_TEMPORAL_PIT_EVIDENCE",
                "contract_status": original.get("status"),
                "authority": original.get("authority"),
                "instrument": original.get("instrument"),
                "contract_blocker": original.get("blocker"),
            }
            continue

        is_eligible = True
        reason = "CANONICAL_PASS_TEMPORAL_PIT_EVIDENCE_PRESENT"
        if point is not None:
            is_eligible, reason = in_window(point, item)
        if is_eligible:
            eligible += 1
        targets[ccy] = {
            "certification": "CERTIFIED_PARTIAL_OR_FULL_WINDOW",
            "backtest_eligible": is_eligible,
            "reason": reason,
            **item,
        }

    return {
        "schema": "GMFQ_CB_PRICING_WALKFORWARD_ELIGIBILITY_GATE_V1",
        "status": "PASS",
        "decision_date": point,
        "policy": {
            "fail_closed": True,
            "expected_evidence_schema": EVIDENCE_SCHEMA,
            "partial_certified_coverage_allowed": True,
            "date_outside_certified_coverage_action": "WITHHOLD",
            "missing_evidence_action": "WITHHOLD",
            "official_or_directly_licensed_source_required": True,
            "homogeneous_basis_required": True,
            "same_instrument_family_required": True,
            "no_secondary_price_fallback": True,
            "no_proxy_substitution_without_reclassification": True,
            "same_day_use_requires_verified_publication_timestamp": True,
            "downstream_observation_selection_requirement": "SOURCE_SPECIFIC_TEMPORAL_SELECTOR_REQUIRED",
        },
        "expected_currencies": 8,
        "certified_currencies": len(evidence),
        "eligible_currencies": eligible,
        "withheld_currencies": 8 - eligible,
        "targets": targets,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decision-date")
    ap.add_argument("--expect-certified-count", type=int)
    ap.add_argument("--expect-eligible-count", type=int)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    result = build(args.decision_date)
    if args.expect_certified_count is not None and result["certified_currencies"] != args.expect_certified_count:
        raise RuntimeError("CB Pricing certified currency count changed")
    if args.expect_eligible_count is not None and result["eligible_currencies"] != args.expect_eligible_count:
        raise RuntimeError("CB Pricing eligible currency count changed")
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
