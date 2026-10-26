#!/usr/bin/env python3
"""Audit Beta + Forward launch evidence without modifying data or models."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BETA = ROOT / "validation/beta/RATE_BETA_OBSERVATIONAL_CONTRACT_V1_2026-10-15.json"
SCHEMA = ROOT / "validation/forward/CORE_FORWARD_DECISION_LOGGER_V1_SCHEMA.json"
DECISIONS = ROOT / "validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl"
OUTCOMES = ROOT / "validation/forward/outcomes/CORE_DECISION_OUTCOMES_V1.jsonl"

# Source: Il_beta_dalla_A_alla_Z.pdf, Chapter 23.3 (ten-step procedure),
# Chapter 23.4 (OOS hedge variance reduction). A study reference, not a
# claim that all its robust, high-frequency and implicit methods are mandated
# operational production features.
BETA_METHOD_AUDIT = (
    ("purpose_and_reference", "PARTIAL_52W_FX_VS_2Y_CONTRACT"),
    ("clean_pit_aligned_return_panel", "NOT_CERTIFIED"),
    ("frequency_sensitivity_check", "NOT_IMPLEMENTED"),
    ("ols_robust_se_hac", "PARTIAL_OLS_ONLY"),
    ("robust_estimator_outlier_comparison", "NOT_IMPLEMENTED"),
    ("dimson_lead_lag_check", "NOT_IMPLEMENTED"),
    ("rolling_ewma_kalman_stability", "PARTIAL_ROLLING_52W_ONLY"),
    ("shrinkage_comparison_if_required", "NOT_IMPLEMENTED"),
    ("two_asset_regression_direction_check", "NOT_EVALUATED_FOR_FX_2Y"),
    ("strict_oos_hedge_variance_reduction", "NOT_CERTIFIED"),
)


def _read_lines(path):
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(s) for s in lines if s.strip()]


def _valid_utc(value):
    if not isinstance(value, str):
        return False
    try:
        x = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return x.tzinfo is not None and x.utcoffset() is not None
    except (ValueError, TypeError):
        return False


def _canonical_hash(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")) + "\n"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def inspect(beta, schema, decisions, outcomes):
    if beta.get("schema") != "GMFQ_RATE_BETA_OBSERVATIONAL_CONTRACT_V1":
        raise ValueError("unrecognized beta specification")
    if schema.get("schema") != "GMFQ_CORE_FORWARD_DECISION_LOGGER_V1":
        raise ValueError("unrecognized forward contract")
    if not isinstance(decisions, list) or not isinstance(outcomes, list):
        raise ValueError("expected JSONL row arrays")

    reasons = []
    beta_governance = beta.get("governance", {})
    beta_observational = (
        beta.get("status") == "RESEARCH_NOT_VALIDATED" and
        beta.get("model", {}).get("window_observations") == 52 and
        beta_governance.get("backtest_enabled") is False and
        beta_governance.get("promotion_enabled") is False
    )
    if not beta_observational:
        reasons.append("BETA_GOVERNANCE_REQUIRES_INDEPENDENT_REVIEW")
    reasons.append("BETA_NO_CERTIFIED_PIT_52W_FX_2Y_PANEL")
    reasons.append("BETA_NO_COMPLETED_OOS_HEDGE_VARIANCE_BENCHMARK")
    reasons.append("BETA_B1_B2_CANONICAL_RULES_NOT_MATERIALIZED")

    required = set(schema.get("required_snapshot_fields", ()))
    allowed_horizons = set(schema.get("outcome_horizons", ()))
    bad_hash = bad_time = contract_mismatches = 0
    duplicates = 0
    ids, batches, cutoffs = set(), set(), set()
    for item in decisions:
        if not isinstance(item, dict):
            raise ValueError("malformed historical decision")
        sid = item.get("snapshot_id")
        if sid in ids or not isinstance(sid, str) or len(sid) != 64:
            duplicates += 1
        ids.add(sid)
        cutoffs.add(item.get("decision_cutoff"))
        batches.add(item.get("run_id"))
        if item.get("snapshot_sha256") != _canonical_hash(
            {key: val for key, val in item.items() if key != "snapshot_sha256"}
        ):
            bad_hash += 1
        if not _valid_utc(item.get("decision_cutoff")):
            bad_time += 1
        if required - set(item):
            contract_mismatches += 1

    outcome_pairs, duplicate_outcomes, invalid_outcomes = set(), 0, 0
    for item in outcomes:
        if not isinstance(item, dict):
            raise ValueError("malformed historical outcome")
        key = (item.get("snapshot_id"), item.get("horizon"))
        if key in outcome_pairs:
            duplicate_outcomes += 1
        outcome_pairs.add(key)
        if (key[0] not in ids or key[1] not in allowed_horizons or
                not _valid_utc(item.get("available_at")) or
                item.get("outcome_sha256") != _canonical_hash(
                    {k: v for k, v in item.items() if k != "outcome_sha256"})):
            invalid_outcomes += 1

    if not decisions:
        reasons.append("FORWARD_NO_DECISION_SNAPSHOTS")
    if len(batches) < 2 or len(cutoffs) < 2:
        reasons.append("FORWARD_NO_REPEATED_PIT_CAPTURE")
    if any("smoke" in str(x).lower() for x in batches) and len(batches) == 1:
        reasons.append("FORWARD_SMOKE_ONLY_NO_LIVE_OBSERVATION_SEQUENCE")
    if not outcomes:
        reasons.append("FORWARD_NO_REALIZED_OUTCOMES")
    if contract_mismatches:
        reasons.append("FORWARD_SNAPSHOT_FIELDS_MISMATCH_CANONICAL_CONTRACT")
    if bad_hash or bad_time or duplicates or invalid_outcomes or duplicate_outcomes:
        reasons.append("FORWARD_ARCHIVE_INTEGRITY_EXCEPTION")
    # No independent price source audit or transaction-cost calibration exists
    # in this receipt. Data presence by itself never proves trading performance.
    reasons.append("FORWARD_NO_VERIFIED_PRICE_COST_PROVENANCE_AND_OOS_EVALUATION")
    return {
        "schema": "GMFQ_BETA_FORWARD_LAUNCH_TRUTH_GATE_V1",
        "state": "NOT_READY_FOR_FINAL_LAUNCH_SIGNOFF",
        "beta": {
            "method": "ROLLING_52W_FX_RETURN_VS_DELTA_REL_2Y_OLS",
            "observational_contract_present": beta_observational,
            "strategy_beta_validated": False,
            "pdf_23_3_ten_step_audit": [
                {"step": name, "state": state} for name, state in BETA_METHOD_AUDIT
            ],
            "pdf_23_4_oos_hedge_variance_reduction_validated": False,
            "b1_b2_ready": False,
        },
        "forward": {
            "decision_rows": len(decisions),
            "unique_cutoff_instants": len(cutoffs),
            "distinct_run_ids": len(batches),
            "run_ids": sorted(str(x) for x in batches),
            "outcome_rows": len(outcomes),
            "supported_outcome_horizons": sorted(allowed_horizons),
            "decision_snapshot_hash_mismatches": bad_hash,
            "decision_snapshot_clock_invalid": bad_time,
            "decision_snapshot_missing_contract_fields": contract_mismatches,
            "duplicate_snapshot_ids": duplicates,
            "duplicate_outcome_horizons": duplicate_outcomes,
            "invalid_outcomes": invalid_outcomes,
            "forward_sequence_verified": False,
            "performance_verified_oos": False,
        },
        "blockers": reasons,
        "core_score_modified": False,
        "beta_promoted": False,
        "forward_performance_promoted": False,
        "no_trades_or_simulated_returns_generated": True,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, help="Read-only QA receipt under /tmp")
    args = ap.parse_args()
    if args.out and not args.out.resolve().is_relative_to(Path("/tmp")):
        ap.error("QA output must stay under /tmp")
    receipt = inspect(json.loads(BETA.read_text()),
                      json.loads(SCHEMA.read_text()),
                      _read_lines(DECISIONS), _read_lines(OUTCOMES))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
