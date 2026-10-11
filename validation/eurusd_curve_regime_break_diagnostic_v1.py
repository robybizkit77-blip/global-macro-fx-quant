#!/usr/bin/env python3
"""Trace the EUR 10Y-2Y curve regime break in the EURUSD predictive pilot.

This is a diagnostic, not a regime-switching trading rule. It deliberately avoids
choosing a date threshold or a fitted gating rule from the test set.

Fixed design:
- same strict-PIT EUR Macro inputs, certified EUR/USD Rates histories, monthly grid,
  and ECB EURUSD labels used by the existing diagnostic stack;
- compare Macro-only with Macro+EUR-curve under the same expanding ridge
  (alpha=10, minimum 36 labelled months);
- capture the standardized curve coefficient and the curve model's marginal
  prediction/strategy contribution at every OOS decision point;
- summarize only predeclared fixed blocks plus a fixed 24-month trailing raw
  curve/forward-return correlation available at each OOS point;
- no tuning, no threshold search, no production authorization.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import eurusd_relative_rates_diagnostic_v1 as rr

SCHEMA = "GMFQ_EURUSD_CURVE_REGIME_BREAK_DIAGNOSTIC_V1"
ROLLING_WINDOW = 24
MACRO_FEATURES = ["inflation", "unemployment"]
CURVE_FEATURES = ["inflation", "unemployment", "eur_curve_bp"]


def corr(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3:
        return None
    ma, mb = rr.mean(a), rr.mean(b)
    da = sum((x - ma) ** 2 for x in a)
    db = sum((x - mb) ** 2 for x in b)
    if da <= 0 or db <= 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(da * db)


def fit_predict(train: list[dict[str, Any]], row: dict[str, Any], features: list[str]):
    xtr = [[r[f] for f in features] for r in train]
    ytr = [r["forward_log_return"] for r in train]
    beta, mus, sds = rr.fit_ridge(xtr, ytr)
    x = [row[f] for f in features]
    pred = rr.predict(beta, mus, sds, x)
    return pred, beta


def block_summary(path: list[dict[str, Any]]) -> dict[str, Any]:
    if not path:
        return {"observations": 0}
    diverged = [r for r in path if r["signal_diverged"]]
    marginal = [r["curve_marginal_strategy_log_return"] for r in path]
    negative = [r for r in path if r["curve_marginal_strategy_log_return"] < 0]
    betas = [r["curve_standardized_coefficient"] for r in path]
    raw_curve = [r["eur_curve_bp"] for r in path]
    actual = [r["actual_forward_log_return"] for r in path]
    return {
        "observations": len(path),
        "signal_divergence_count": len(diverged),
        "signal_divergence_share": len(diverged) / len(path),
        "negative_marginal_months": len(negative),
        "curve_marginal_total_log_return": sum(marginal),
        "curve_marginal_total_simple_return_equivalent": math.exp(sum(marginal)) - 1.0,
        "mean_curve_standardized_coefficient": rr.mean(betas),
        "min_curve_standardized_coefficient": min(betas),
        "max_curve_standardized_coefficient": max(betas),
        "curve_coefficient_positive_share": sum(v > 0 for v in betas) / len(betas),
        "raw_curve_forward_return_correlation": corr(raw_curve, actual),
        "first_signal_divergence": diverged[0]["decision_point"] if diverged else None,
        "first_negative_marginal_month": negative[0]["decision_point"] if negative else None,
    }


def build(inf, lab, eur, usd, dates, prices) -> dict[str, Any]:
    rows = rr.build_rows(inf, lab, eur, usd, dates, prices)
    labelled = rr.label_rows(rows)
    path: list[dict[str, Any]] = []

    for t in range(rr.MIN_TRAIN, len(labelled)):
        train = labelled[:t]
        row = labelled[t]
        macro_pred, macro_beta = fit_predict(train, row, MACRO_FEATURES)
        curve_pred, curve_beta = fit_predict(train, row, CURVE_FEATURES)
        actual = row["forward_log_return"]
        macro_sig = 1 if macro_pred > 0 else (-1 if macro_pred < 0 else 0)
        curve_sig = 1 if curve_pred > 0 else (-1 if curve_pred < 0 else 0)
        macro_strategy = macro_sig * actual
        curve_strategy = curve_sig * actual

        trailing = train[-ROLLING_WINDOW:]
        trailing_corr = corr(
            [r["eur_curve_bp"] for r in trailing],
            [r["forward_log_return"] for r in trailing],
        ) if len(trailing) == ROLLING_WINDOW else None

        path.append({
            "decision_point": row["decision_point"],
            "eur_curve_bp": row["eur_curve_bp"],
            "actual_forward_log_return": actual,
            "macro_prediction": macro_pred,
            "curve_model_prediction": curve_pred,
            "curve_prediction_delta_vs_macro": curve_pred - macro_pred,
            "macro_signal": macro_sig,
            "curve_signal": curve_sig,
            "signal_diverged": macro_sig != curve_sig,
            "macro_strategy_log_return": macro_strategy,
            "curve_strategy_log_return": curve_strategy,
            "curve_marginal_strategy_log_return": curve_strategy - macro_strategy,
            "curve_standardized_coefficient": curve_beta[-1],
            "macro_inflation_standardized_coefficient": macro_beta[1],
            "macro_unemployment_standardized_coefficient": macro_beta[2],
            "trailing_24m_raw_curve_forward_return_correlation_training_only": trailing_corr,
            "train_observations": t,
        })

    blocks: dict[str, Any] = {}
    for label, lo, hi in rr.BLOCKS:
        blocks[label] = block_summary([r for r in path if lo <= r["decision_point"] <= hi])

    p2025 = [r for r in path if "2025-01-01" <= r["decision_point"] <= "2026-07-31"]
    damage_months = [
        {
            "decision_point": r["decision_point"],
            "eur_curve_bp": r["eur_curve_bp"],
            "curve_standardized_coefficient": r["curve_standardized_coefficient"],
            "macro_signal": r["macro_signal"],
            "curve_signal": r["curve_signal"],
            "actual_forward_log_return": r["actual_forward_log_return"],
            "curve_marginal_strategy_log_return": r["curve_marginal_strategy_log_return"],
            "trailing_24m_raw_curve_forward_return_correlation_training_only": r["trailing_24m_raw_curve_forward_return_correlation_training_only"],
        }
        for r in p2025 if r["curve_marginal_strategy_log_return"] < 0
    ]

    signal_flip_months = [
        {
            "decision_point": r["decision_point"],
            "eur_curve_bp": r["eur_curve_bp"],
            "curve_standardized_coefficient": r["curve_standardized_coefficient"],
            "macro_signal": r["macro_signal"],
            "curve_signal": r["curve_signal"],
            "actual_forward_log_return": r["actual_forward_log_return"],
            "curve_marginal_strategy_log_return": r["curve_marginal_strategy_log_return"],
        }
        for r in p2025 if r["signal_diverged"]
    ]

    return {
        "schema": SCHEMA,
        "status": "DIAGNOSTIC_COMPLETE",
        "scope": {
            "instrument": "EURUSD",
            "snapshot_count": len(rows),
            "labelled_months": len(labelled),
            "oos_path_points": len(path),
            "first_oos_decision": path[0]["decision_point"],
            "last_oos_decision": path[-1]["decision_point"],
            "information_set": "strict-PIT EUR Macro + certified temporally eligible EUR rates; USD Macro absent",
        },
        "method": {
            "macro_features": MACRO_FEATURES,
            "curve_model_features": CURVE_FEATURES,
            "ridge_alpha_fixed": rr.ALPHA,
            "minimum_training_months": rr.MIN_TRAIN,
            "rolling_correlation_window_fixed_months": ROLLING_WINDOW,
            "rolling_correlation_uses_training_only": True,
            "hyperparameter_tuning": False,
            "threshold_search": False,
            "regime_switch_rule_fitted": False,
            "test_set_model_selection": False,
        },
        "fixed_block_summary": blocks,
        "2025_to_2026_07_signal_flip_months": signal_flip_months,
        "2025_to_2026_07_damage_months": damage_months,
        "path": path,
        "diagnostic_readout": {
            "curve_feature_regime_instability_observed": True,
            "date_based_curve_disable_rule_authorized": False,
            "observable_regime_gate_identified": False,
            "next_question": "Can an independently observable PIT market/macro regime variable explain when EUR curve slope stops representing currency-supportive policy/growth information?",
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
    ap.add_argument("--inflation", type=Path, required=True)
    ap.add_argument("--labour", type=Path, required=True)
    ap.add_argument("--eur-rates", type=Path, required=True)
    ap.add_argument("--usd-rates", type=Path, required=True)
    ap.add_argument("--ecb", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    inf = rr.load_macro(args.inflation, "headline_hicp_yoy_pct")
    lab = rr.load_macro(args.labour, "unemployment_rate_pct")
    eur = rr.load_rates(args.eur_rates)
    usd = rr.load_rates(args.usd_rates)
    dates, prices = rr.load_prices(args.ecb)
    result = build(inf, lab, eur, usd, dates, prices)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "blocks": result["fixed_block_summary"],
        "signal_flips_2025": result["2025_to_2026_07_signal_flip_months"],
        "damage_months_2025": result["2025_to_2026_07_damage_months"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
