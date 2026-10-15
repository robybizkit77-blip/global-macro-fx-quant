#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def sha256(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def run_json(cmd: list[str]):
    proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if proc.returncode:
        raise SystemExit(proc.stdout)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON from {cmd}: {exc}\n{proc.stdout}")


def run(cmd: list[str]):
    proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if proc.returncode:
        raise SystemExit(proc.stdout)
    return proc.stdout


def main():
    v2 = run_json([sys.executable, "validation/run_final_e2e_certification_gate_v2.py"])
    if v2.get("status") != "PASS" or v2.get("v1_freeze_ready") is not True:
        raise SystemExit(f"V2 gate drift: {v2}")

    registry = load_json("validation/finalization/V1_DATA_LAYER_REGISTRY_2026-10-15.json")
    if registry.get("engine_state") != "READY_WITH_DOCUMENTED_EXPECTED_GAPS":
        raise SystemExit("registry engine state drift")
    if registry["layers"]["official_runtime"].get("fail_closed") is not True:
        raise SystemExit("official runtime is not fail-closed")

    cb_contract = load_json("validation/cb_pricing/CB_PRICING_ESTIMATED_CONTRACT_V1_2026-10-15.json")
    if cb_contract.get("status") != "INFORMATIONAL_ONLY":
        raise SystemExit("CB estimated layer is not informational-only")
    if cb_contract.get("eligible_currencies") != ["USD", "EUR", "CHF", "NZD"]:
        raise SystemExit("CB estimated currency set drift")
    for key in ("core_score_effect", "bias_effect", "sizing_effect", "pair_engine_effect", "backtest_effect"):
        if cb_contract["governance"].get(key) != "NONE":
            raise SystemExit(f"CB estimated non-neutral effect: {key}")

    cb_before_obj = load_json("live_data/sections/CB_PRICING_ESTIMATED.json")
    ois_before = sha256("live_data/sections/OIS_DATA.json")
    native_cb_before = sha256("live_data/sections/NATIVE_CB_DATA.json")
    run([sys.executable, "validation/cb_pricing/build_cb_pricing_estimated_v1.py"])
    run([sys.executable, "validation/cb_pricing/test_cb_pricing_estimated_v1.py"])
    cb_after_obj = load_json("live_data/sections/CB_PRICING_ESTIMATED.json")
    if cb_before_obj != cb_after_obj:
        raise SystemExit("CB estimated committed snapshot is semantically out of alignment with its deterministic builder")
    if ois_before != sha256("live_data/sections/OIS_DATA.json") or native_cb_before != sha256("live_data/sections/NATIVE_CB_DATA.json"):
        raise SystemExit("CB estimated validation mutated official CB/OIS inputs")

    residual_contract = load_json("validation/estimated/RESIDUAL_GAPS_ESTIMATED_CONTRACT_V1_2026-10-15.json")
    residual = load_json("live_data/sections/ESTIMATED_RESIDUAL_GAPS.json")
    if residual_contract.get("status") != "INFORMATIONAL_ONLY" or residual.get("status") != "INFORMATIONAL_ONLY":
        raise SystemExit("residual proxy layer governance drift")
    run([sys.executable, "validation/estimated/test_residual_gaps_estimated_v1.py"])
    expected_status = {
        "JPY.reserve_balances": "ESTIMATED_ACTIVE",
        "CHF.credit": "ESTIMATED_ACTIVE",
        "CHF.sight_deposits": "ESTIMATED_ACTIVE",
        "BRENT.market_proxy": "MARKET_PROXY_READY_NO_LIVE_VALUE",
    }
    for lane, status in expected_status.items():
        if residual["lanes"][lane].get("status") != status:
            raise SystemExit(f"residual proxy lane drift: {lane}")
    if residual["lanes"]["BRENT.market_proxy"].get("value") is not None:
        raise SystemExit("Brent proxy emitted an unvalidated numeric value")

    gaps = load_json("validation/finalization/V1_DOCUMENTED_EXPECTED_GAPS_2026-10-15.json")
    if gaps.get("summary", {}).get("total_expected_gaps") != 7:
        raise SystemExit("official expected-gap count drift")
    if any(row.get("status") != "WITHHELD_DOCUMENTED_EXPECTED_GAP" for row in gaps.get("gaps", [])):
        raise SystemExit("an official expected gap was silently promoted")

    receipt = {
        "schema": "GMFQ_FINAL_E2E_CERTIFICATION_GATE_V3",
        "status": "PASS",
        "operational_state": "READY_WITH_DOCUMENTED_EXPECTED_GAPS",
        "v1_engine_freeze_ready": True,
        "official_runtime": {
            "status": "CERTIFIED_FAIL_CLOSED",
            "documented_expected_gaps": 7,
            "silent_proxy_promotion": False,
        },
        "estimated_layers": {
            "cb_pricing": {
                "status": "ALIGNED_INFORMATIONAL_ONLY",
                "refresh_mode": "DERIVED_DYNAMIC_FROM_NATIVE_CB_DATA",
                "currencies": ["USD", "EUR", "CHF", "NZD"],
                "deterministic_snapshot_aligned": True,
                "core_effect": "NONE",
            },
            "residual_gaps": {
                "status": "ALIGNED_INFORMATIONAL_ONLY",
                "refresh_mode": "SNAPSHOT_UNTIL_LIVE_COLLECTOR_EXISTS",
                "active_numeric_proxies": ["JPY.reserve_balances", "CHF.credit", "CHF.sight_deposits"],
                "brent_live_value": False,
                "core_effect": "NONE",
            },
        },
        "rate_beta": v2.get("rate_beta"),
        "forward_logger": v2.get("forward_logger"),
        "next_research_not_part_of_freeze": [
            "wire reproducible live collectors for residual proxy snapshots",
            "wire reproducible current Brent futures proxy",
            "extend historical PIT panel for RATE_BETA backtest/OOS",
            "accumulate forward outcomes over time"
        ],
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
