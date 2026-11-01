#!/usr/bin/env python3
"""Read-only source/revision audit of NON-OIS monetary curve estimates.

Estimate reliability != OIS accuracy. USD/EUR/CHF use the dated same-contract
futures research archive; NZD uses the already-pinned monthly Bank Bill-minus-OCR
calibration and 3 untouched central-fit holdout observations. Missing independent
same-tenor OIS benchmarks cause MAE and direction hit-rate to be NULL.
Never re-label a futures level as an official OIS quote or a source-day PIT trade.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation/cb_pricing/history/OIS_SAME_CONTRACT_QUOTES_V1.jsonl"
NZD = ROOT / "validation/cb_pricing/NZD_BB_CASH_RESEARCH_CALIBRATION_V1_2026-10-21.json"
SCHEMA = "GMFQ_ESTIMATED_OIS_RELIABILITY_RESEARCH_V1"
CCYS = ("USD", "EUR", "CHF")
TENORS = ("3m", "6m", "12m")
SPECS = {"USD": ("CBOT:", "ZQ"), "EUR": ("EUREX:", "FST3"),
         "CHF": ("ICEEUR:", "SA3")}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("OIS_ESTIMATE_RELIABILITY_REJECTED: " + message)


def iso_day(value: str) -> date:
    require(isinstance(value, str), "date must be string")
    d = date.fromisoformat(value)
    require(d.isoformat() == value, "non-ISO economic observation date")
    return d


def check_archive(data: list[dict]) -> list[dict]:
    require(isinstance(data, list) and len(data) >= 1, "no dated futures observations")
    seen = set()
    out = []
    for i, r in enumerate(data):
        require(isinstance(r, dict), f"row {i} must be object")
        c, h = r.get("currency"), r.get("observed_under_horizon")
        require(c in CCYS and h in TENORS, f"row {i} invalid currency/horizon")
        stem, root = SPECS[c]
        contract = r.get("contract")
        require(isinstance(contract, str) and contract.startswith(root)
                and len(contract) == len(root) + 5
                and contract[-4:].isdigit()
                and contract[len(root)] in "FGHJKMNQUVXZ", f"row {i} contract")
        require(r.get("symbol") == stem + contract, f"row {i} instrument mismatch")
        t = iso_day(r["observation_date"])
        expiry = iso_day(r["expiration"])
        require(expiry > t, f"row {i} expired future")
        seen_at = r.get("first_seen_at_utc")
        require(isinstance(seen_at, str) and seen_at.endswith("Z"), "no first-seen time")
        first_seen = datetime.fromisoformat(seen_at.replace("Z", "+00:00"))
        require(first_seen.date() >= t, "first-seen predates observed futures bar")
        price, rate = r.get("futures_price"), r.get("implied_rate")
        require(all(type(v) in (float, int) and math.isfinite(v) for v in (price, rate)),
                "nonfinite quote")
        require(-5 <= rate <= 25 and abs(100 - price - rate) <= 0.0002,
                f"row {i} futures quote identity")
        require(r.get("schema") == "GMFQ_OIS_SAME_CONTRACT_QUOTE_V1"
                and r.get("source_timestamp_evidence") ==
                    "SSR_DAILY_BAR_DATA_UPDATE_TIME"
                and r.get("source_method") ==
                    "TRADINGVIEW_DATED_FUTURES_SSR_V2"
                and r.get("official_ois_quote") is False
                and r.get("policy_delta_eligible") is False
                and r.get("backtest_eligible_as_official") is False,
                f"row {i} unapproved official promotion or provenance")
        key = (c, contract, t.isoformat())
        require(key not in seen, f"duplicate dated contract {key}")
        seen.add(key)
        out.append({**r, "_date": t, "_first_seen": first_seen})
    return out


def futures_evidence(rows: list[dict], ccy: str) -> dict:
    selected = [r for r in rows if r["currency"] == ccy]
    require(selected, ccy + ": no valid quotes")
    by_contract = defaultdict(list)
    for r in selected:
        by_contract[r["contract"]].append(r)
    changes, excluded_gap, excluded_horizon_remap = [], 0, 0
    for contract, contract_rows in sorted(by_contract.items()):
        s = sorted(contract_rows, key=lambda x: x["_date"])
        horizons = {x["observed_under_horizon"] for x in s}
        if len(horizons) > 1:
            # The verified Nov-2026 SARON methodological correction switched
            # from final-settlement tenor labels to accrual-start tenor
            # labels. Do not compare prices *as 3M/6M/12M changes* across this
            # boundary even for an identical listed contract. All unexpected
            # mapping changes still fail closed (USD/EUR, tampered CHF, etc).
            from validation.cb_pricing.collect_cb_pricing_estimated_live_v1 import saron_window
            start, expiry = saron_window(contract) if ccy == "CHF" else (None, None)
            pivot = next(i for i,x in enumerate(s)
                         if x["observed_under_horizon"] != s[0]["observed_under_horizon"])
            before, after = s[:pivot], s[pivot:]
            require(ccy == "CHF" and contract.startswith("SA3") and
                    len(horizons) == 2 and before and after and
                    len({x["observed_under_horizon"] for x in before}) == 1 and
                    len({x["observed_under_horizon"] for x in after}) == 1 and
                    all(x["_first_seen"].date() < date(2026,11,1) for x in before) and
                    all(x["_first_seen"].date() >= date(2026,11,1) for x in after) and
                    all(x["expiration"] == expiry.isoformat() for x in s) and
                    all(start > x["_date"] for x in after) and
                    all(abs((start - x["_first_seen"].date()).days -
                         {"3m":90,"6m":180,"12m":365}[x["observed_under_horizon"]]) <= 50
                        for x in after),
                    ccy + ": contract changed horizon label; no roll comparison")
        for old, new in zip(s, s[1:]):
            if old["observed_under_horizon"] != new["observed_under_horizon"]:
                excluded_horizon_remap += 1
                continue
            gap = (new["_date"] - old["_date"]).days
            if not 1 <= gap <= 7:
                excluded_gap += 1
                continue
            delta_bp = (new["implied_rate"] - old["implied_rate"]) * 100
            changes.append({"contract": contract, "tenor": new["observed_under_horizon"],
                "from": old["observation_date"], "to": new["observation_date"],
                "first_seen_complete_at_utc": max(old["_first_seen"], new["_first_seen"]).isoformat(),
                "change_bp": round(delta_bp, 4)})
    by_tenor = {}
    for t in TENORS:
        ss = [r for r in selected if r["observed_under_horizon"] == t]
        ms = [m["change_bp"] for m in changes if m["tenor"] == t]
        by_tenor[t] = {
            "quote_count": len(ss),
            "distinct_quoted_dates": len({r["observation_date"] for r in ss}),
            "distinct_contracts": len({r["contract"] for r in ss}),
            "same_contract_valid_move_count": len(ms),
            "observed_positive_moves": sum(x > 0 for x in ms),
            "observed_negative_moves": sum(x < 0 for x in ms),
            "observed_flat_moves": sum(x == 0 for x in ms),
            "median_abs_same_contract_move_bp": round(median(map(abs, ms)), 3) if ms else None,
            "reference_ois_level_MAE_bp": None,
            "reference_ois_level_bias_bp": None,
            "reference_ois_direction_hit_rate": None,
        }
    return {
        "currency": ccy, "input_kind": "VERIFIED_DATED_FUTURES_PROXY_NOT_OIS",
        "quote_count": len(selected), "contract_count": len(by_contract),
        "first_observation": min(r["observation_date"] for r in selected),
        "last_observation": max(r["observation_date"] for r in selected),
        "first_seen_lag_days_min": min((r["_first_seen"].date() - r["_date"]).days for r in selected),
        "first_seen_lag_days_max": max((r["_first_seen"].date() - r["_date"]).days for r in selected),
        "same_contract_valid_move_count": len(changes),
        "same_contract_excluded_gap_count": excluded_gap,
        "same_contract_excluded_horizon_remap_count": excluded_horizon_remap,
        "same_contract_changes": changes,
        "horizons": by_tenor,
        "same_contract_moves_are_NOT_predicted_OIS_direction": True,
        "independent_OIS_benchmark_available": False,
        "level_error_MAE_bp": None,
        "level_error_bias_bp": None,
        "direction_accuracy_percent": None,
        "reliability_grade_for_OIS_accuracy": "NOT_VALIDATED_NO_INDEPENDENT_OIS_REFERENCE",
        "futures_data_identity_audited": True,
        "historical_first_release_PIT_certified": False,
        "historical_futures_bar_first_seen_is_NOT_trade_timestamp": True,
        "minimum_OIS_level_or_direction_accuracy_demonstrated": False,
    }


def new_zealand_evidence(cal: dict) -> dict:
    require(cal.get("schema") ==
            "GMFQ_NZD_BB_VS_CASH_EMPIRICAL_CALIBRATION_RESEARCH_V1"
            and cal["method"]["source_span_handpicked_not_full_history"] is True
            and cal["method"]["all_contract_horizons_same_basis_assumption"] is True
            and cal["provenance"]["historical_pit_certified"] is False
            and cal["provenance"]["not_a_direct_ois_observation"] is True,
            "NZD basis provenance / methodology changed")
    ref = cal["reference_plateau"]["rows"]
    recent = cal["recent_plateau"]["rows"]
    holdout = cal["holdout_2026_q3"]["rows"]
    require(len(ref) == 13 and len(recent) == 6 and len(holdout) == 3,
            "NZD pinned calibration sample sizes changed")
    require([r["month"] for r in holdout] == ["2026-07", "2026-08", "2026-09"],
            "NZD central point contaminated by holdout selection")
    def basis(r):
        v = (r["bank_bill_90d_pct"] - r["ocr_pct"]) * 100
        require(type(v) in (int, float) and math.isfinite(v) and 0 < v < 100,
                "NZD basis invalid")
        return v
    left = median(basis(r) for r in ref)
    right = median(basis(r) for r in recent)
    fitted = round(.3 * left + .7 * right)
    require(fitted == 24 and cal["method"]["weighted_reference_median"] == .3
            and cal["method"]["weighted_recent_median"] == .7,
            "NZD central fit must be frozen independently of holdout")
    actual = [round(basis(r), 8) for r in holdout]
    residual = [round(fitted - v, 8) for v in actual]
    mae = mean(abs(e) for e in residual)
    entries = [
        {"month": r["month"], "observed_bill_minus_OCR_basis_bp": round(v, 5),
         "frozen_fit_basis_bp": fitted, "fit_minus_observed_basis_bp": round(e, 5)}
        for r, v, e in zip(holdout, actual, residual)
    ]
    assert math.isclose(mae, cal["holdout_2026_q3"]["mae_bp"], abs_tol=1e-6)
    return {
        "currency": "NZD",
        "input_kind": "NZD_BB_FUTURES_MINUS_HISTORIC_CASH_CARRY_SCENARIO",
        "calibration_months": 19, "held_out_months": 3,
        "frozen_basis_point_estimate_bp": fitted,
        "monthly_bill_minus_OCR_holdout_MAE_bp": round(mae, 3),
        "monthly_bill_minus_OCR_holdout_bias_bp": round(mean(residual), 3),
        "monthly_bill_minus_OCR_holdout_max_abs_error_bp": round(max(map(abs, residual)), 3),
        "holdout_months": entries,
        "sample_is_short_and_regime_selected": True,
        "expanded_10_to_50bp_band_selected_after_holdout": True,
        "expanded_band_is_NOT_an_out_of_sample_confidence_interval": True,
        "cash_bill_minus_OCR_is_NOT_the_traded_BB_minus_OIS_basis": True,
        "all_futures_expiry_horizons_same_carry_assumption_UNTESTED": True,
        "independent_OIS_benchmark_available": False,
        "level_error_MAE_bp": None,
        "level_error_bias_bp": None,
        "direction_accuracy_percent": None,
        "reliability_grade_for_OIS_accuracy": "NOT_VALIDATED_NO_INDEPENDENT_OIS_REFERENCE",
        "historical_first_release_PIT_certified": False,
        "direction_signal_from_monthly_basis_allowed": False,
    }


def build(archive_text: str, calibration: dict) -> dict:
    raw = [json.loads(x) for x in archive_text.splitlines() if x.strip()]
    rows = check_archive(raw)
    ccy = {c: futures_evidence(rows, c) for c in CCYS}
    ccy["NZD"] = new_zealand_evidence(calibration)
    require(len(ccy) == 4 and sum(ccy[c]["quote_count"] for c in CCYS) == len(rows),
            "archive integrity/coverage")
    output = {
        "schema": SCHEMA, "status": "RESEARCH_INPUT_AUDIT_ONLY_OIS_ACCURACY_NOT_VALIDATED",
        "quotes_observed": len(rows),
        "futures_currencies": list(CCYS),
        "futures_observation_date_first": min(r["observation_date"] for r in rows),
        "futures_observation_date_last": max(r["observation_date"] for r in rows),
        "total_matched_same_contract_changes": sum(ccy[c]["same_contract_valid_move_count"]
                                                   for c in CCYS),
        "currencies": ccy,
        "independent_synchronized_OIS_reference_count": 0,
        "currencies_with_verified_OIS_accuracy": 0,
        "can_assign_empirical_OIS_prediction_confidence": False,
        "level_MAE_vs_OIS": None,
        "directional_hit_rate_vs_OIS": None,
        "data_provenance_audit_is_NOT_model_validation": True,
        "an_OIS_proxy_is_not_an_OIS_quote": True,
        "future_reference_needed": [
            "independent_same_currency_same_horizon_OIS_quotes_with_original_publication_timestamps",
            "historical_basis_ois_minus_futures_or_bill_measured_in_matching_instruments",
            "walk_forward_holdout_across_distinct_repricing_regimes_and_source_revisions",
        ],
        "eligible_to_publish_official_OIS": False,
        "eligible_to_reprice_CB_or_28_pairs": False,
        "eligible_for_H1_or_Forward": False,
        "writes_live_data": False,
    }
    return output


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("/tmp/ois-estimate-reliability.json"))
    args = ap.parse_args()
    require(args.out.resolve().is_relative_to(Path("/tmp")),
            "read-only research output limited to /tmp")
    a = SOURCE.read_text(encoding="utf-8")
    b = json.loads(NZD.read_text(encoding="utf-8"))
    o = build(a, b)
    o["source_sha256"] = hashlib.sha256(a.encode()).hexdigest()
    o["nzd_calibration_sha256"] = hashlib.sha256(NZD.read_bytes()).hexdigest()
    o["receipt_sha256"] = hashlib.sha256(
        json.dumps(o, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(o, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": o["status"], "quotes": o["quotes_observed"],
        "same_contract_changes": o["total_matched_same_contract_changes"],
        "OIS_accuracy_validated": o["currencies_with_verified_OIS_accuracy"],
        "NZD_cash_basis_holdout_MAE_bp":
            o["currencies"]["NZD"]["monthly_bill_minus_OCR_holdout_MAE_bp"],
        "output": str(args.out)}, sort_keys=True))


if __name__ == "__main__":
    main()
