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


def certify_secondary_source_state(ccy: str, row: dict) -> str:
    """Validates graded secondary evidence without inventing clean OIS curves."""
    if ccy not in ("USD", "EUR", "CHF"):
        raise ValueError("unsupported secondary currency")
    if row.get("status") != "ESTIMATED_ACTIVE":
        raise ValueError(f"{ccy} estimated live layer not active")
    if row.get("method_id") != "TRADINGVIEW_DATED_FUTURES_SSR_V2":
        raise ValueError(f"{ccy} estimated method drift")
    if row.get("governance", {}).get("backtest_eligible_as_official_ois") is not False:
        raise ValueError(f"{ccy} secondary futures promoted to official backtest input")
    if row.get("governance", {}).get("core_score_effect") != "NONE" or (
        row.get("governance", {}).get("pair_engine_effect") != "NONE"):
        raise ValueError(f"{ccy} secondary sources silently entered Macro/Pair")
    mode = row.get("input_mode")
    if mode not in ("LIVE_SECONDARY_OVERLAY", "LIVE_SECONDARY_CONFLICT_INDICATIVE"):
        raise ValueError(f"{ccy} estimated input mode drift")
    disputed = mode == "LIVE_SECONDARY_CONFLICT_INDICATIVE"
    horizon_ids = set()
    if disputed:
        if (row.get("source_conflict_status") !=
                "UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT"
            or row.get("source_quality") != "SECONDARY_CONFLICTED_INDICATIVE_NOT_OIS"
            or row.get("direction_vs_policy") != "WITHHELD"
            or row.get("change_status") != "CONFLICTED_SECONDARY_NO_REPRICING"
            or row.get("change_1d_bp") is not None
            or row.get("change_1w_bp") is not None):
            raise ValueError(f"{ccy} conflicted source was promoted to repricing")
        keys = row.get("source_conflict_keys")
        if not isinstance(keys, list) or not keys or len(keys) > 3:
            raise ValueError(f"{ccy} missing verified conflict identity")
        import re
        for key in keys:
            h = key.get("horizon") if isinstance(key, dict) else None
            point = (row.get("horizons") or {}).get(h) or {}
            if (h not in ("3m", "6m", "12m") or h in horizon_ids
                or not isinstance(key.get("event_id"), str)
                or re.fullmatch(r"[0-9a-f]{64}", key["event_id"]) is None
                or key.get("contract") != point.get("contract")
                or key.get("observation_date") != point.get("quote_as_of")
                or point.get("quote_timestamp_verified") is not False
                or point.get("quote_timestamp_source") !=
                    "QUARANTINED_SAME_CONTRACT_SAME_DAY"):
                raise ValueError(f"{ccy}/{h} unverified quarantine source identity")
            horizon_ids.add(h)
    elif row.get("source_conflict_status") is not None or row.get("source_conflict_keys"):
        raise ValueError(f"{ccy} clean source has hidden unresolved conflicts")
    for horizon in ("3m", "6m", "12m"):
        point = (row.get("horizons") or {}).get(horizon) or {}
        if (type(point.get("rate")) not in (int, float)
            or "!" in str(point.get("contract") or "")
            or "!" in str(point.get("symbol") or "")):
            raise ValueError(f"{ccy} estimated {horizon} lacks a dated numeric futures quote")
        if disputed and point.get("policy_delta_bp") is not None:
            raise ValueError(f"{ccy}/{horizon} conflicted currency inferred CB policy")
        if disputed and horizon not in horizon_ids:
            if (point.get("quote_timestamp_verified") is not True or
                point.get("quote_timestamp_source") !=
                    "SSR_DAILY_BAR_DATA_UPDATE_TIME"):
                raise ValueError(f"{ccy}/{horizon} uncontested tenor unverified")
    return ("SOURCE_CONFLICT_ANNOTATED_NO_REPRICING"
            if disputed else "INDEPENDENTLY_TIMESTAMPED_SECONDARY_NOT_OIS")


def main():
    v2 = run_json([sys.executable, "validation/run_final_e2e_certification_gate_v2.py"])
    if v2.get("status") != "PASS" or v2.get("v1_freeze_ready") is not True:
        raise SystemExit(f"V2 gate drift: {v2}")

    registry = load_json("validation/finalization/V1_DATA_LAYER_REGISTRY_2026-10-15.json")
    if registry.get("engine_state") != "READY_WITH_DOCUMENTED_EXPECTED_GAPS":
        raise SystemExit("registry engine state drift")
    if registry["layers"]["official_runtime"].get("fail_closed") is not True:
        raise SystemExit("official runtime is not fail-closed")
    if registry["layers"]["cb_pricing_estimated"].get("refresh_mode") != "LIVE_OPERATIONAL_ESTIMATED_WITH_HOMOGENEOUS_REPRICING":
        raise SystemExit("CB estimated registry refresh mode drift")
    if registry["layers"]["residual_gap_proxies"].get("refresh_mode") != "ALL_RESIDUAL_PROXIES_LIVE_OR_AUTO_REFRESH":
        raise SystemExit("residual registry refresh mode drift")

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

    # Current operational estimated architecture: USD/EUR/CHF use live secondary
    # dated listed futures only; NZD preserves the native RBNZ OIS anchor and adds
    # an explicitly non-OIS ASX directional market-rates proxy.
    secondary_grades = {}
    for ccy in ("USD", "EUR", "CHF"):
        try:
            secondary_grades[ccy] = certify_secondary_source_state(
                ccy, cb_after_obj["currencies"][ccy])
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

    nzd = cb_after_obj["currencies"]["NZD"]
    if nzd.get("status") != "ESTIMATED_PARTIAL" or nzd.get("input_mode") != "NATIVE_CB_FALLBACK":
        raise SystemExit("NZD native OIS fallback state drift")
    if nzd.get("method_id") != "NATIVE_CB_ESTIMATED_V1":
        raise SystemExit("NZD native OIS method drift")
    if (nzd.get("horizons") or {}).get("3m", {}).get("rate") != 3.0:
        raise SystemExit("NZD native 3M OIS anchor drift")
    if (nzd.get("horizons") or {}).get("6m", {}).get("rate") is not None or (nzd.get("horizons") or {}).get("12m", {}).get("rate") is not None:
        raise SystemExit("NZD ASX proxy silently filled native OIS horizons")
    nzd_proxy = nzd.get("market_direction_proxy") or {}
    if nzd_proxy.get("status") != "LIVE_DIRECTIONAL_PROXY_READY":
        raise SystemExit("NZD ASX directional proxy not ready")
    if nzd_proxy.get("substitutes_for_ois_level") is not False or nzd_proxy.get("policy_delta_from_proxy_allowed") is not False:
        raise SystemExit("NZD ASX directional proxy governance drift")
    for horizon in ("3m", "6m", "12m"):
        if not isinstance((nzd_proxy.get("horizons") or {}).get(horizon, {}).get("implied_bank_bill_rate"), (int, float)):
            raise SystemExit(f"NZD ASX directional proxy missing {horizon}")

    # Resolved operational view must cover all G8 while keeping the quality split explicit.
    run([sys.executable, "validation/cb_pricing/build_ois_operational_view_v1.py"])
    run([sys.executable, "validation/cb_pricing/test_ois_operational_view_v1.py"])
    operational_ois = load_json("live_data/sections/OIS_OPERATIONAL_VIEW.json")
    summary = operational_ois.get("summary") or {}
    rows = operational_ois.get("currencies") or {}
    if set(rows) != {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"}:
        raise SystemExit("OIS operational G8 currency coverage drift")
    counts = {
        "green_official": sum(r.get("operational_status") == "GREEN_OFFICIAL" for r in rows.values()),
        "green_estimated": sum(r.get("operational_status") == "GREEN_ESTIMATED" for r in rows.values()),
        "operational_withheld": sum(r.get("operational_status") == "WITHHELD" for r in rows.values()),
    }
    green = counts["green_official"] + counts["green_estimated"]
    expected_status = "PARTIAL_WITHHELD" if counts["operational_withheld"] else "GREEN_8_OF_8"
    if (sum(counts.values()) != 8 or summary.get("g8_total") != 8
            or summary.get("operational_green") != green
            or any(summary.get(key) != value for key, value in counts.items())
            or operational_ois.get("status") != expected_status):
        raise SystemExit("OIS operational dynamic G8 status/summary drift")
    if operational_ois.get("official_runtime_untouched") is not True:
        raise SystemExit("OIS operational view no longer preserves official runtime")
    for ccy in ("AUD", "CAD", "GBP", "JPY"):
        if operational_ois["currencies"][ccy].get("operational_status") != "GREEN_OFFICIAL":
            raise SystemExit(f"{ccy} official operational OIS status drift")
    for ccy in ("USD", "EUR", "CHF"):
        row = operational_ois["currencies"][ccy]
        if row.get("backtest_eligible_as_official") is not False:
            raise SystemExit(f"{ccy} estimated operational OIS must never count as official")
        if row.get("operational_status") == "WITHHELD":
            if any(row.get("horizons", {}).get(h, {}).get("rate") is not None for h in ("3m", "6m", "12m")):
                raise SystemExit(f"{ccy} WITHHELD OIS cannot publish rates")
        elif row.get("operational_status") != "GREEN_ESTIMATED":
            raise SystemExit(f"{ccy} estimated operational OIS governance drift")
    nzd = operational_ois["currencies"]["NZD"]
    if nzd.get("operational_status") == "WITHHELD":
        if any((nzd.get("horizons") or {}).get(h, {}).get("rate") is not None for h in ("3m", "6m", "12m")):
            raise SystemExit("NZD withheld OIS has non-null level")
    elif nzd.get("operational_status") in ("GREEN_OFFICIAL", "GREEN_ESTIMATED"):
        if any((nzd.get("horizons") or {}).get(h, {}).get("rate") is None for h in ("3m", "6m", "12m")):
            raise SystemExit("NZD GREEN OIS has incomplete levels")
        if nzd.get("backtest_eligible_as_official") is not (nzd["operational_status"] == "GREEN_OFFICIAL"):
            raise SystemExit("NZD official-backtest eligibility drift")
    for ccy in ("USD", "EUR", "CHF"):
        row = operational_ois["currencies"][ccy]
        if row.get("method_id") != "TRADINGVIEW_DATED_FUTURES_SSR_V2":
            raise SystemExit(f"{ccy} operational OIS method drift")
        for horizon in ("3m", "6m", "12m"):
            point = (row.get("horizons") or {}).get(horizon) or {}
            if "!" in str(point.get("contract") or "") or "!" in str(point.get("symbol") or ""):
                raise SystemExit(f"{ccy} operational {horizon} uses forbidden continuous future")

    residual_contract = load_json("validation/estimated/RESIDUAL_GAPS_ESTIMATED_CONTRACT_V1_2026-10-15.json")
    residual = load_json("live_data/sections/ESTIMATED_RESIDUAL_GAPS.json")
    if residual_contract.get("status") != "INFORMATIONAL_ONLY" or residual.get("status") != "INFORMATIONAL_ONLY":
        raise SystemExit("residual proxy layer governance drift")
    run([sys.executable, "validation/estimated/test_residual_gaps_estimated_v1.py"])

    allowed_status = {
        "JPY.reserve_balances": {"ESTIMATED_ACTIVE", "ESTIMATED_ACTIVE_AUTO_REFRESH_OFFICIAL_PROXY"},
        "CHF.credit": {"ESTIMATED_ACTIVE", "ESTIMATED_ACTIVE_AUTO_REFRESH_OFFICIAL_PROXY"},
        "CHF.sight_deposits": {"ESTIMATED_ACTIVE", "ESTIMATED_ACTIVE_AUTO_REFRESH_OFFICIAL_PROXY"},
        "BRENT.market_proxy": {"MARKET_PROXY_ACTIVE_SECONDARY"},
    }
    for lane, statuses in allowed_status.items():
        if residual["lanes"][lane].get("status") not in statuses:
            raise SystemExit(f"residual proxy lane drift: {lane}")

    brent = residual["lanes"]["BRENT.market_proxy"]
    if not (isinstance(brent.get("value"), (int, float)) and brent["value"] > 0):
        raise SystemExit("Brent secondary proxy has no valid live numeric value")
    if brent.get("official_canonical_untouched") is not True or brent.get("vendor_symbol") != "BZ=F":
        raise SystemExit("Brent secondary proxy governance drift")

    for lane in ("CHF.credit", "CHF.sight_deposits"):
        row = residual["lanes"][lane]
        if row.get("status") == "ESTIMATED_ACTIVE_AUTO_REFRESH_OFFICIAL_PROXY":
            if row.get("official_canonical_untouched") is not True or "SNB official API" not in row.get("source", ""):
                raise SystemExit(f"CHF auto-refresh proxy governance drift: {lane}")

    jpy = residual["lanes"]["JPY.reserve_balances"]
    if jpy.get("status") == "ESTIMATED_ACTIVE_AUTO_REFRESH_OFFICIAL_PROXY":
        if jpy.get("official_canonical_untouched") is not True or "Bank of Japan official" not in jpy.get("source", ""):
            raise SystemExit("JPY reserve auto-refresh proxy governance drift")
        anchor = jpy.get("original_runtime_validation") or {}
        if anchor.get("period") != "2026-08" or anchor.get("absolute_difference") != 460.0:
            raise SystemExit("JPY reserve original runtime validation anchor drift")
        continuity = jpy.get("continuity_anchor") or {}
        if continuity.get("period") != "2026-09" or continuity.get("expected_official_value") != 3849859.0 or continuity.get("matched") is not True:
            raise SystemExit("JPY reserve September continuity anchor drift")

    gaps = load_json("validation/finalization/V1_DOCUMENTED_EXPECTED_GAPS_2026-10-15.json")
    if gaps.get("summary", {}).get("total_expected_gaps") != 7:
        raise SystemExit("official expected-gap count drift")
    if any(row.get("status") != "WITHHELD_DOCUMENTED_EXPECTED_GAP" for row in gaps.get("gaps", [])):
        raise SystemExit("an official expected gap was silently promoted")

    chf_auto = all(
        residual["lanes"][lane].get("status") == "ESTIMATED_ACTIVE_AUTO_REFRESH_OFFICIAL_PROXY"
        for lane in ("CHF.credit", "CHF.sight_deposits")
    )
    jpy_auto = jpy.get("status") == "ESTIMATED_ACTIVE_AUTO_REFRESH_OFFICIAL_PROXY"
    all_residual_live = chf_auto and jpy_auto and brent.get("status") == "MARKET_PROXY_ACTIVE_SECONDARY"
    if not all_residual_live:
        raise SystemExit("registry says all residual proxies live/auto-refresh but runtime does not")

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
                "refresh_mode": "LIVE_OPERATIONAL_ESTIMATED_WITH_HOMOGENEOUS_REPRICING",
                "currencies": ["USD", "EUR", "CHF", "NZD"],
                "live_secondary_overlay_currencies": ["USD", "EUR", "CHF"],
                "live_secondary_method": "TRADINGVIEW_DATED_FUTURES_SSR_V2",
                "continuous_futures_allowed": False,
                "native_ois_anchor_currencies": ["NZD"],
                "directional_market_proxy_currencies": ["NZD"],
                "deterministic_snapshot_aligned": True,
                "operational_coverage": operational_ois["status"],
                "official_green": counts["green_official"],
                "estimated_green": counts["green_estimated"],
                "operational_withheld": counts["operational_withheld"],
                "secondary_source_grades": secondary_grades,
                "unresolved_secondary_source_conflicts": [
                    ccy for ccy, grade in secondary_grades.items()
                    if grade == "SOURCE_CONFLICT_ANNOTATED_NO_REPRICING"
                ],
                "core_effect": "NONE",
            },
            "residual_gaps": {
                "status": "ALIGNED_INFORMATIONAL_ONLY",
                "refresh_mode": "ALL_RESIDUAL_PROXIES_LIVE_OR_AUTO_REFRESH",
                "active_numeric_proxies": ["JPY.reserve_balances", "CHF.credit", "CHF.sight_deposits", "BRENT.market_proxy"],
                "brent_live_value": True,
                "chf_official_proxy_auto_refresh": chf_auto,
                "jpy_reserve_refresh_mode": "AUTO_REFRESH_OFFICIAL_PROXY",
                "core_effect": "NONE",
            },
        },
        "rate_beta": v2.get("rate_beta"),
        "forward_logger": v2.get("forward_logger"),
        "next_research_not_part_of_freeze": [
            "extend historical PIT panel for RATE_BETA backtest/OOS",
            "accumulate forward outcomes over time"
        ],
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
