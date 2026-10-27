#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def run_json(cmd: list[str]):
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode:
        raise SystemExit(proc.stdout)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON from {cmd}: {exc}\n{proc.stdout}")


def main():
    base_gate = run_json([sys.executable, "validation/run_daily_data_orchestrator_final_gate_v1.py"])
    if base_gate.get("operational_state") != "READY_WITH_DOCUMENTED_EXPECTED_GAPS":
        raise SystemExit(f"base final gate drift: {base_gate}")

    gaps = load_json("validation/finalization/V1_DOCUMENTED_EXPECTED_GAPS_2026-10-15.json")
    if gaps.get("classification") != "DOCUMENTED_EXPECTED_GAPS":
        raise SystemExit(f"gap classification drift: {gaps}")
    if gaps.get("summary") != {"total_expected_gaps": 7, "liquidity": 3, "cb_pricing": 4}:
        raise SystemExit(f"gap summary drift: {gaps.get('summary')}")
    expected_gap_ids = [
        "CHF.liquidity",
        "CHF.credit",
        "JPY.liquidity",
        "USD.cb_pricing",
        "EUR.cb_pricing",
        "CHF.cb_pricing",
        "NZD.cb_pricing",
    ]
    if [row.get("id") for row in gaps.get("gaps", [])] != expected_gap_ids:
        raise SystemExit("documented expected gap identity drift")
    if any(row.get("status") != "WITHHELD_DOCUMENTED_EXPECTED_GAP" for row in gaps["gaps"]):
        raise SystemExit("documented expected gap status drift")
    if gaps.get("blocks_v1_freeze") is not False:
        raise SystemExit("documented expected gaps unexpectedly block V1 freeze")

    beta = load_json("validation/beta/RATE_BETA_OBSERVATIONAL_CONTRACT_V1_2026-10-15.json")
    if beta.get("scope") != "OBSERVATIONAL_ONLY" or beta.get("status") != "RESEARCH_NOT_VALIDATED":
        raise SystemExit("RATE_BETA governance drift")
    model = beta.get("model", {})
    if model.get("window_observations") != 52:
        raise SystemExit("RATE_BETA window drift")
    if model.get("formula") != "fx_return ~ alpha + beta * delta_relative_2y_differential":
        raise SystemExit("RATE_BETA formula drift")
    governance = beta.get("governance", {})
    for key in ("core_score_effect", "bias_effect", "sizing_effect", "forward_logger_effect", "runtime_effect", "payload_effect", "dashboard_publication_effect"):
        if governance.get(key) != "NONE":
            raise SystemExit(f"RATE_BETA non-neutral effect: {key}={governance.get(key)}")
    if governance.get("backtest_enabled") is not False or governance.get("promotion_enabled") is not False:
        raise SystemExit("RATE_BETA backtest/promotion unexpectedly enabled")

    subprocess.run(
        [sys.executable, "validation/beta/test_rate_beta_observational_v1.py"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    forward_receipt = load_json("validation/forward/receipts/2026-10-14__real-main-smoke-20261014__V1.json")
    if forward_receipt.get("status") != "PASS":
        raise SystemExit("forward logger receipt not PASS")
    if forward_receipt.get("observational_only") is not True:
        raise SystemExit("forward logger is not observational-only")
    if forward_receipt.get("no_forward_outcomes_in_snapshot") is not True:
        raise SystemExit("forward snapshots contain forward outcomes")
    result = forward_receipt.get("result", {})
    if result.get("total_candidates") != 28:
        raise SystemExit("forward logger pair count drift")

    # Forward decisions are a legitimately growing append-only journal:
    # each new accepted prospective cutoff adds exactly 28 G8 crosses.
    # Never freeze the whole archive to the October 14 smoke batch size.
    from validation.forward.check_append_only_snapshots_gate_v1 import inspect as inspect_forward
    snapshot_path = ROOT / "validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl"
    snapshot_rows = [json.loads(line) for line in snapshot_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    forward_archive = inspect_forward(snapshot_rows)
    if forward_archive["status"] != "PASS_RESEARCH_OBSERVATIONAL_ARCHIVE_NOT_FORWARD_VALIDATION":
        raise SystemExit("forward journal audit not accepted")
    if forward_archive["run_ids"][0] != "real-main-smoke-20261014":
        raise SystemExit("first Forward smoke capture lineage changed")

    receipt = {
        "schema": "GMFQ_FINAL_E2E_CERTIFICATION_GATE_V2",
        "status": "PASS",
        "operational_state": "READY_WITH_DOCUMENTED_EXPECTED_GAPS",
        "v1_freeze_ready": True,
        "core_runtime_mutated": False,
        "base_gate": {
            "status": base_gate.get("status"),
            "operational_state": base_gate.get("operational_state"),
            "exact_blockers": base_gate.get("exact_blockers"),
        },
        "documented_expected_gaps": {
            "count": 7,
            "ids": expected_gap_ids,
            "fail_closed": True,
            "block_v1_freeze": False,
        },
        "rate_beta": {
            "status": "RESEARCH_NOT_VALIDATED",
            "scope": "OBSERVATIONAL_ONLY",
            "window_observations": 52,
            "backtest_enabled": False,
            "promotion_enabled": False,
            "core_effect": "NONE",
        },
        "forward_logger": {
            "status": "PASS",
            "observational_only": True,
            "snapshot_count": forward_archive["snapshot_rows"],
            "complete_28_pair_batches": forward_archive["complete_28_pair_batches"],
            "first_smoke_28_pair_batch_preserved": True,
            "legacy_missing_PIT_fields_not_promoted": True,
            "forward_launch_certified": False,
            "no_forward_outcomes_in_snapshot": forward_archive["no_forward_returns_embedded"],
        },
        "publication_policy": {
            "data_final_gate_publishable": base_gate.get("publishable"),
            "data_final_gate_publication_state": base_gate.get("publication_state"),
            "dashboard_can_exist_with_expected_gaps": True,
        },
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
