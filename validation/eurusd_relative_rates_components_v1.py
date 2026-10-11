#!/usr/bin/env python3
"""Decompose EURUSD relative-rate levels into front-end, long-end, and curve components.

Fixed ex-ante comparison on the same strict-PIT EUR Macro + certified EUR/USD Rates
information set and the same monthly EURUSD labels used by the prior relative-rates
diagnostic. No tuning, no threshold search, no production authorization.

Note: curve_diff_bp is algebraically derived from long_end_spread-front_end_spread,
so FULL_RELATIVE_LEVELS contains redundant rate information by construction. This
diagnostic identifies which component actually carries the useful information.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import eurusd_relative_rates_diagnostic_v1 as rr

SCHEMA = "GMFQ_EURUSD_RELATIVE_RATES_COMPONENTS_DIAGNOSTIC_V1"
MODELS = {
    "MACRO_ONLY": ["inflation", "unemployment"],
    "MACRO_PLUS_FRONT_END_SPREAD": ["inflation", "unemployment", "front_end_spread"],
    "MACRO_PLUS_LONG_END_SPREAD": ["inflation", "unemployment", "long_end_spread"],
    "MACRO_PLUS_CURVE_DIFF": ["inflation", "unemployment", "curve_diff_bp"],
    "MACRO_PLUS_FRONT_AND_LONG": ["inflation", "unemployment", "front_end_spread", "long_end_spread"],
    "FULL_RELATIVE_LEVELS_REDUNDANT": ["inflation", "unemployment", "front_end_spread", "long_end_spread", "curve_diff_bp"],
}


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
        preds.append({"decision_point": labelled[t]["decision_point"], "prediction": pr, "actual": actual, "strategy": sig * actual})
    return preds


def build(inf, lab, eur, usd, dates, prices) -> dict[str, Any]:
    rows = rr.build_rows(inf, lab, eur, usd, dates, prices)
    labelled = rr.label_rows(rows)
    models: dict[str, Any] = {}
    for name, features in MODELS.items():
        preds = run_model(labelled, features)
        blocks = {}
        for label, lo, hi in rr.BLOCKS:
            blocks[label] = rr.metrics([p for p in preds if lo <= p["decision_point"] <= hi])
        models[name] = {"features": features, "overall": rr.metrics(preds), "time_blocks": blocks}

    key = "2025_to_2026-07"
    macro = models["MACRO_ONLY"]["time_blocks"][key]
    comparison = {}
    for name in MODELS:
        if name == "MACRO_ONLY":
            continue
        m = models[name]["time_blocks"][key]
        comparison[name] = {
            "hit_rate_minus_macro_only": m["directional_accuracy"] - macro["directional_accuracy"],
            "sharpe_minus_macro_only": m["strategy_annualized_sharpe"] - macro["strategy_annualized_sharpe"],
            "total_return_minus_macro_only": m["strategy_total_return"] - macro["strategy_total_return"],
        }

    return {
        "schema": SCHEMA,
        "status": "DIAGNOSTIC_COMPLETE",
        "scope": {
            "instrument": "EURUSD",
            "snapshot_count": len(rows),
            "labelled_months": len(labelled),
            "oos_predictions_per_model": models["MACRO_ONLY"]["overall"]["observations"],
            "usd_macro_leg_present": False,
            "cross_market_rate_basis_identical": False,
            "cross_market_basis_caveat": "EUR=ECB AAA Svensson spot curve; USD=U.S. Treasury par curve",
        },
        "method": {
            "models_predeclared": MODELS,
            "ridge_alpha_fixed": rr.ALPHA,
            "minimum_training_months": rr.MIN_TRAIN,
            "hyperparameter_tuning": False,
            "test_set_model_selection": False,
            "same_day_rate_use_allowed": False,
            "curve_identity": "curve_diff_bp = 100 * (long_end_spread - front_end_spread)",
        },
        "models": models,
        "comparison_2025_to_2026_07_vs_macro_only": comparison,
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
    print(json.dumps({"status": result["status"], "comparison": result["comparison_2025_to_2026_07_vs_macro_only"], "models": result["models"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
