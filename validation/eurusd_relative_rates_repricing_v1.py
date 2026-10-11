#!/usr/bin/env python3
"""Diagnostic: EURUSD relative-rate LEVELS versus month-to-month REPRICING.

Fixed ex-ante design:
- reuse the exact strict-PIT EUR Macro histories, frozen EUR/USD Rates histories,
  decision grid, and ECB EURUSD labels from eurusd_relative_rates_diagnostic_v1;
- convert relative rate features into changes versus the immediately prior
  monthly decision point;
- compare relative LEVELS, repricing-only, Macro+repricing, and Macro+levels+repricing;
- expanding-window ridge, alpha=10, minimum 36 labelled months;
- no tuning, no test-set model selection, no production authorization.

Economic interpretation: FX may react more to changes in relative monetary/market
pricing than to the absolute level of either curve. This script tests that claim
without changing the downstream target or optimization scheme.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import eurusd_relative_rates_diagnostic_v1 as rr

SCHEMA = "GMFQ_EURUSD_RELATIVE_RATES_REPRICING_DIAGNOSTIC_V1"
MODELS = {
    "MACRO_PLUS_RELATIVE_LEVELS_BASELINE": [
        "inflation", "unemployment", "front_end_spread", "long_end_spread", "curve_diff_bp"
    ],
    "RELATIVE_REPRICING_ONLY": [
        "d_front_end_spread", "d_long_end_spread", "d_curve_diff_bp"
    ],
    "MACRO_PLUS_RELATIVE_REPRICING": [
        "inflation", "unemployment", "d_front_end_spread", "d_long_end_spread", "d_curve_diff_bp"
    ],
    "MACRO_PLUS_LEVELS_AND_REPRICING": [
        "inflation", "unemployment",
        "front_end_spread", "long_end_spread", "curve_diff_bp",
        "d_front_end_spread", "d_long_end_spread", "d_curve_diff_bp",
    ],
}


def add_repricing(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(1, len(rows)):
        prev = rows[i - 1]
        cur = dict(rows[i])
        cur["d_front_end_spread"] = cur["front_end_spread"] - prev["front_end_spread"]
        cur["d_long_end_spread"] = cur["long_end_spread"] - prev["long_end_spread"]
        cur["d_curve_diff_bp"] = cur["curve_diff_bp"] - prev["curve_diff_bp"]
        cur["prior_decision_point"] = prev["decision_point"]
        out.append(cur)
    if len(out) != len(rows) - 1:
        raise RuntimeError("repricing transform changed row count unexpectedly")
    return out


def run_model(labelled: list[dict[str, Any]], features: list[str]) -> list[dict[str, Any]]:
    preds: list[dict[str, Any]] = []
    for t in range(rr.MIN_TRAIN, len(labelled)):
        train = labelled[:t]
        xtr = [[r[f] for f in features] for r in train]
        ytr = [r["forward_log_return"] for r in train]
        beta, mus, sds = rr.fit_ridge(xtr, ytr)
        x = [labelled[t][f] for f in features]
        pr = rr.predict(beta, mus, sds, x)
        actual = labelled[t]["forward_log_return"]
        sig = 1 if pr > 0 else (-1 if pr < 0 else 0)
        preds.append({
            "decision_point": labelled[t]["decision_point"],
            "prediction": pr,
            "actual": actual,
            "strategy": sig * actual,
        })
    return preds


def build(
    inf: list[dict[str, Any]],
    lab: list[dict[str, Any]],
    eur: list[dict[str, Any]],
    usd: list[dict[str, Any]],
    dates: list[str],
    prices: dict[str, float],
) -> dict[str, Any]:
    base_rows = rr.build_rows(inf, lab, eur, usd, dates, prices)
    rows = add_repricing(base_rows)
    labelled = rr.label_rows(rows)

    models: dict[str, Any] = {}
    for name, features in MODELS.items():
        preds = run_model(labelled, features)
        blocks = {}
        for label, lo, hi in rr.BLOCKS:
            blocks[label] = rr.metrics([p for p in preds if lo <= p["decision_point"] <= hi])
        models[name] = {
            "features": features,
            "overall": rr.metrics(preds),
            "time_blocks": blocks,
        }

    key = "2025_to_2026-07"
    baseline = models["MACRO_PLUS_RELATIVE_LEVELS_BASELINE"]["time_blocks"][key]
    repricing = models["MACRO_PLUS_RELATIVE_REPRICING"]["time_blocks"][key]
    combined = models["MACRO_PLUS_LEVELS_AND_REPRICING"]["time_blocks"][key]

    return {
        "schema": SCHEMA,
        "status": "DIAGNOSTIC_COMPLETE",
        "scope": {
            "instrument": "EURUSD",
            "base_monthly_rows": len(base_rows),
            "repricing_rows": len(rows),
            "labelled_months": len(labelled),
            "oos_predictions_per_model": models["MACRO_PLUS_RELATIVE_LEVELS_BASELINE"]["overall"]["observations"],
            "information_set": "strict-PIT EUR Macro plus certified temporally eligible EUR and USD rates",
            "usd_macro_leg_present": False,
            "cross_market_rate_basis_identical": False,
            "cross_market_basis_caveat": "EUR=ECB AAA Svensson spot curve; USD=U.S. Treasury par curve",
        },
        "method": {
            "models_predeclared": MODELS,
            "repricing_definition": "current monthly decision-point relative spread minus immediately prior monthly decision-point relative spread",
            "ridge_alpha_fixed": rr.ALPHA,
            "minimum_training_months": rr.MIN_TRAIN,
            "hyperparameter_tuning": False,
            "test_set_model_selection": False,
            "same_day_rate_use_allowed": False,
            "label_start_rule": "first ECB EURUSD fixing strictly after decision date",
        },
        "models": models,
        "comparison_2025_to_2026_07": {
            "macro_repricing_minus_macro_levels_hit_rate": repricing["directional_accuracy"] - baseline["directional_accuracy"],
            "macro_repricing_minus_macro_levels_sharpe": repricing["strategy_annualized_sharpe"] - baseline["strategy_annualized_sharpe"],
            "macro_repricing_minus_macro_levels_total_return": repricing["strategy_total_return"] - baseline["strategy_total_return"],
            "combined_minus_macro_levels_sharpe": combined["strategy_annualized_sharpe"] - baseline["strategy_annualized_sharpe"],
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
        "comparison": result["comparison_2025_to_2026_07"],
        "models": result["models"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
