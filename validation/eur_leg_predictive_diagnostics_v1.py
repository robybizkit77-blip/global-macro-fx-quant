#!/usr/bin/env python3
"""Decompose the EUR-leg predictive pilot without tuning the OOS test set.

Fixed diagnostics only:
- same 102 strict-PIT monthly snapshots and ECB EURUSD labels as pilot v1;
- same expanding-window ridge alpha=10 and 36-month minimum train;
- three pre-declared feature sets: FULL, MACRO_ONLY, RATES_ONLY;
- fixed time blocks for stability inspection;
- standardized coefficient sign / magnitude stability from the FULL model.

This is diagnostic evidence, not model selection and not production authorization.
"""
from __future__ import annotations

import argparse
import json
import math
from bisect import bisect_right
from pathlib import Path
from typing import Any

from eur_leg_predictive_pilot_v1 import (
    MIN_TRAIN,
    RIDGE_ALPHA,
    corr,
    fit_ridge,
    load_ecb_prices,
    load_snapshots,
    max_drawdown,
    mean,
    predict,
    sharpe_monthly,
)

SCHEMA = "GMFQ_EUR_LEG_PREDICTIVE_DIAGNOSTICS_V1"
FEATURE_SETS = {
    "FULL": ["inflation", "unemployment", "yield_2y", "yield_10y", "curve_bp"],
    "MACRO_ONLY": ["inflation", "unemployment"],
    "RATES_ONLY": ["yield_2y", "yield_10y", "curve_bp"],
}
BLOCKS = [
    ("2021-03-10", "2022-12-31", "2021-03_to_2022-12"),
    ("2023-01-01", "2024-12-31", "2023_to_2024"),
    ("2025-01-01", "2026-07-31", "2025_to_2026-07"),
]


def first_fixing_strictly_after(dp: str, dates: list[str], prices: dict[str, float]) -> tuple[str, float]:
    i = bisect_right(dates, dp)
    if i >= len(dates):
        raise RuntimeError(f"no ECB fixing after {dp}")
    d = dates[i]
    return d, prices[d]


def label_rows(rows: list[dict[str, Any]], dates: list[str], prices: dict[str, float]) -> list[dict[str, Any]]:
    work = [dict(r) for r in rows]
    for r in work:
        fd, px = first_fixing_strictly_after(r["decision_point"], dates, prices)
        r["label_start_fixing_date"] = fd
        r["label_start_price"] = px
    labelled = []
    for i in range(len(work) - 1):
        r = dict(work[i])
        r["label_end_fixing_date"] = work[i + 1]["label_start_fixing_date"]
        r["forward_log_return"] = math.log(work[i + 1]["label_start_price"] / work[i]["label_start_price"])
        labelled.append(r)
    return labelled


def metrics(preds: list[dict[str, Any]]) -> dict[str, Any]:
    if not preds:
        return {"observations": 0}
    y = [r["actual"] for r in preds]
    p = [r["prediction"] for r in preds]
    sr = [r["strategy"] for r in preds]
    hits = sum(1 for a, b in zip(p, y) if (a > 0 and b > 0) or (a < 0 and b < 0))
    return {
        "observations": len(preds),
        "directional_accuracy": hits / len(preds),
        "prediction_return_correlation": corr(p, y),
        "strategy_total_return": math.exp(sum(sr)) - 1.0,
        "strategy_annualized_sharpe": sharpe_monthly(sr),
        "strategy_max_drawdown": max_drawdown(sr),
        "mean_monthly_strategy_log_return": mean(sr),
    }


def run_feature_set(labelled: list[dict[str, Any]], features: list[str], capture_beta: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    preds: list[dict[str, Any]] = []
    betas: list[dict[str, Any]] = []
    for t in range(MIN_TRAIN, len(labelled)):
        train = labelled[:t]
        xtr = [[r[f] for f in features] for r in train]
        ytr = [r["forward_log_return"] for r in train]
        beta, mus, sds = fit_ridge(xtr, ytr, RIDGE_ALPHA)
        x = [labelled[t][f] for f in features]
        pr = predict(beta, mus, sds, x)
        actual = labelled[t]["forward_log_return"]
        sig = 1 if pr > 0 else (-1 if pr < 0 else 0)
        preds.append({
            "decision_point": labelled[t]["decision_point"],
            "prediction": pr,
            "actual": actual,
            "signal": sig,
            "strategy": sig * actual,
        })
        if capture_beta:
            betas.append({
                "decision_point": labelled[t]["decision_point"],
                "standardized_coefficients": {f: beta[j + 1] for j, f in enumerate(features)},
            })
    return preds, betas


def coefficient_summary(betas: list[dict[str, Any]], features: list[str]) -> dict[str, Any]:
    out = {}
    for f in features:
        vals = [b["standardized_coefficients"][f] for b in betas]
        pos = sum(v > 0 for v in vals)
        neg = sum(v < 0 for v in vals)
        out[f] = {
            "mean_standardized_coefficient": mean(vals),
            "mean_absolute_standardized_coefficient": mean([abs(v) for v in vals]),
            "positive_share": pos / len(vals),
            "negative_share": neg / len(vals),
            "sign_stability": max(pos, neg) / len(vals),
        }
    return out


def build(rows: list[dict[str, Any]], dates: list[str], prices: dict[str, float]) -> dict[str, Any]:
    labelled = label_rows(rows, dates, prices)
    models: dict[str, Any] = {}
    full_betas: list[dict[str, Any]] = []
    for name, features in FEATURE_SETS.items():
        preds, betas = run_feature_set(labelled, features, capture_beta=(name == "FULL"))
        if name == "FULL":
            full_betas = betas
        blocks = {}
        for lo, hi, label in BLOCKS:
            blocks[label] = metrics([p for p in preds if lo <= p["decision_point"] <= hi])
        models[name] = {
            "features": features,
            "overall": metrics(preds),
            "time_blocks": blocks,
        }
    full = models["FULL"]["overall"]
    macro = models["MACRO_ONLY"]["overall"]
    rates = models["RATES_ONLY"]["overall"]
    return {
        "schema": SCHEMA,
        "status": "DIAGNOSTIC_DECOMPOSITION_COMPLETE",
        "scope": {
            "snapshot_count": len(rows),
            "labelled_months": len(labelled),
            "oos_predictions_per_model": full["observations"],
            "instrument": "EURUSD",
            "information_set": "EUR leg only; USD Macro leg absent",
        },
        "method": {
            "feature_sets_predeclared": FEATURE_SETS,
            "ridge_alpha_fixed": RIDGE_ALPHA,
            "minimum_training_months": MIN_TRAIN,
            "hyperparameter_tuning": False,
            "test_set_model_selection": False,
            "time_blocks_fixed_before_results": True,
        },
        "models": models,
        "full_model_coefficient_stability": coefficient_summary(full_betas, FEATURE_SETS["FULL"]),
        "diagnostic_readout": {
            "full_minus_macro_sharpe": None if full["strategy_annualized_sharpe"] is None or macro["strategy_annualized_sharpe"] is None else full["strategy_annualized_sharpe"] - macro["strategy_annualized_sharpe"],
            "full_minus_rates_sharpe": None if full["strategy_annualized_sharpe"] is None or rates["strategy_annualized_sharpe"] is None else full["strategy_annualized_sharpe"] - rates["strategy_annualized_sharpe"],
            "best_single_block_full_sharpe": max(v["strategy_annualized_sharpe"] for v in models["FULL"]["time_blocks"].values() if v.get("strategy_annualized_sharpe") is not None),
            "worst_single_block_full_sharpe": min(v["strategy_annualized_sharpe"] for v in models["FULL"]["time_blocks"].values() if v.get("strategy_annualized_sharpe") is not None),
        },
        "policy": {
            "diagnostic_only": True,
            "production_backtest_authorized": False,
            "production_signal_authorized": False,
            "position_sizing_authorized": False,
            "parameter_changes_from_results_authorized": False,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshots", type=Path, required=True)
    ap.add_argument("--ecb-csv", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    rows = load_snapshots(args.snapshots)
    dates, prices = load_ecb_prices(args.ecb_csv)
    result = build(rows, dates, prices)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "models": result["models"], "coefficient_stability": result["full_model_coefficient_stability"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
