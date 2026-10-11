#!/usr/bin/env python3
"""Diagnostic test of absolute EUR rates versus EUR-USD relative rates for EURUSD.

Fixed ex-ante design:
- monthly decision points on the 10th, 2018-03 through 2026-08;
- strict first-release EUR inflation and labour histories;
- certified temporally eligible EUR and USD 2Y/10Y rate histories;
- ECB official EUR/USD reference-rate labels, starting strictly after each decision;
- expanding-window ridge regression, alpha=10, minimum 36 labelled months;
- no hyperparameter tuning, no test-set model selection, no production authorization.

Cross-market caveat: EUR yields are ECB AAA Svensson spot rates while USD yields are
U.S. Treasury par yields. Relative spreads are therefore diagnostic cross-market
features, not claims of identical curve methodology across currencies.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from bisect import bisect_right
from datetime import date
from pathlib import Path
from typing import Any

ALPHA = 10.0
MIN_TRAIN = 36
SCHEMA = "GMFQ_EURUSD_RELATIVE_RATES_DIAGNOSTIC_V1"
BLOCKS = [
    ("2021-03_to_2022-12", "2021-03-10", "2022-12-31"),
    ("2023_to_2024", "2023-01-01", "2024-12-31"),
    ("2025_to_2026-07", "2025-01-01", "2026-07-31"),
]
MODELS = {
    "EUR_ABSOLUTE_BASELINE": ["inflation", "unemployment", "eur_y2", "eur_y10", "eur_curve_bp"],
    "RELATIVE_RATES_ONLY": ["front_end_spread", "long_end_spread", "curve_diff_bp"],
    "EUR_MACRO_PLUS_RELATIVE_RATES": ["inflation", "unemployment", "front_end_spread", "long_end_spread", "curve_diff_bp"],
}


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def stdev(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def sharpe_monthly(xs: list[float]) -> float | None:
    s = stdev(xs)
    return None if s <= 1e-12 else mean(xs) / s * math.sqrt(12.0)


def corr(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3:
        return None
    ma, mb = mean(a), mean(b)
    da = sum((x - ma) ** 2 for x in a)
    db = sum((x - mb) ** 2 for x in b)
    if da <= 0 or db <= 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(da * db)


def max_drawdown(xs: list[float]) -> float:
    wealth = peak = 1.0
    worst = 0.0
    for r in xs:
        wealth *= math.exp(r)
        peak = max(peak, wealth)
        worst = min(worst, wealth / peak - 1.0)
    return worst


def solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    z = [a[i][:] + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(z[r][col]))
        if abs(z[pivot][col]) < 1e-12:
            raise RuntimeError("singular ridge system")
        z[col], z[pivot] = z[pivot], z[col]
        q = z[col][col]
        z[col] = [v / q for v in z[col]]
        for r in range(n):
            if r == col:
                continue
            q = z[r][col]
            if q:
                z[r] = [z[r][c] - q * z[col][c] for c in range(n + 1)]
    return [z[i][-1] for i in range(n)]


def fit_ridge(x: list[list[float]], y: list[float]) -> tuple[list[float], list[float], list[float]]:
    p = len(x[0])
    mus = [mean([r[j] for r in x]) for j in range(p)]
    sds = [stdev([r[j] for r in x]) for j in range(p)]
    sds = [s if s > 1e-12 else 1.0 for s in sds]
    z = [[1.0] + [(r[j] - mus[j]) / sds[j] for j in range(p)] for r in x]
    k = p + 1
    xtx = [[0.0] * k for _ in range(k)]
    xty = [0.0] * k
    for row, target in zip(z, y):
        for i in range(k):
            xty[i] += row[i] * target
            for j in range(k):
                xtx[i][j] += row[i] * row[j]
    for i in range(1, k):
        xtx[i][i] += ALPHA
    return solve(xtx, xty), mus, sds


def predict(beta: list[float], mus: list[float], sds: list[float], x: list[float]) -> float:
    return beta[0] + sum(beta[j + 1] * ((x[j] - mus[j]) / sds[j]) for j in range(len(x)))


def load_macro(path: Path, value_col: str) -> list[dict[str, Any]]:
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({"ref": r["reference_month"], "release": r["release_date"], "value": float(r[value_col])})
    if not rows:
        raise RuntimeError(f"empty macro history: {path}")
    return rows


def load_rates(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({
                "obs": r["observation_date"],
                "eligible": r["first_eligible_decision_date"],
                "y2": float(r["yield_2y"]),
                "y10": float(r["yield_10y"]),
            })
    if not rows:
        raise RuntimeError(f"empty rates history: {path}")
    return rows


def latest_macro(rows: list[dict[str, Any]], dp: str) -> dict[str, Any]:
    eligible = [r for r in rows if r["release"] < dp]
    if not eligible:
        raise RuntimeError(f"no prior macro row at {dp}")
    return max(eligible, key=lambda r: (r["release"], r["ref"]))


def latest_rates(rows: list[dict[str, Any]], dp: str) -> dict[str, Any]:
    eligible = [r for r in rows if r["eligible"] <= dp and r["obs"] < dp]
    if not eligible:
        raise RuntimeError(f"no temporally eligible rates row at {dp}")
    return max(eligible, key=lambda r: r["obs"])


def grid() -> list[str]:
    out = []
    y, m = 2018, 3
    while (y, m) <= (2026, 8):
        out.append(f"{y:04d}-{m:02d}-10")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def load_prices(path: Path) -> tuple[list[str], dict[str, float]]:
    prices: dict[str, float] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        fields = rd.fieldnames or []
        dk = next((k for k in ["TIME_PERIOD", "TIME PERIOD", "Date", "DATE"] if k in fields), None)
        vk = next((k for k in ["OBS_VALUE", "OBS VALUE", "Value", "VALUE"] if k in fields), None)
        if not dk or not vk:
            raise RuntimeError(f"ECB CSV columns not recognised: {fields}")
        for r in rd:
            ds = (r.get(dk) or "")[:10]
            vs = (r.get(vk) or "").strip()
            try:
                date.fromisoformat(ds)
                v = float(vs)
            except Exception:
                continue
            if v > 0:
                prices[ds] = v
    dates = sorted(prices)
    if len(dates) < 1000:
        raise RuntimeError(f"too few EURUSD observations: {len(dates)}")
    return dates, prices


def first_fixing_after(dp: str, dates: list[str], prices: dict[str, float]) -> tuple[str, float]:
    i = bisect_right(dates, dp)
    if i >= len(dates):
        raise RuntimeError(f"no EURUSD fixing after {dp}")
    d = dates[i]
    return d, prices[d]


def build_rows(inf: list[dict[str, Any]], lab: list[dict[str, Any]], eur: list[dict[str, Any]], usd: list[dict[str, Any]], dates: list[str], prices: dict[str, float]) -> list[dict[str, Any]]:
    rows = []
    for dp in grid():
        i = latest_macro(inf, dp)
        l = latest_macro(lab, dp)
        er = latest_rates(eur, dp)
        ur = latest_rates(usd, dp)
        eur_curve = (er["y10"] - er["y2"]) * 100.0
        usd_curve = (ur["y10"] - ur["y2"]) * 100.0
        fd, px = first_fixing_after(dp, dates, prices)
        rows.append({
            "decision_point": dp,
            "inflation": i["value"],
            "unemployment": l["value"],
            "eur_y2": er["y2"],
            "eur_y10": er["y10"],
            "eur_curve_bp": eur_curve,
            "usd_y2": ur["y2"],
            "usd_y10": ur["y10"],
            "usd_curve_bp": usd_curve,
            "front_end_spread": er["y2"] - ur["y2"],
            "long_end_spread": er["y10"] - ur["y10"],
            "curve_diff_bp": eur_curve - usd_curve,
            "eur_rate_observation": er["obs"],
            "usd_rate_observation": ur["obs"],
            "label_start_fixing_date": fd,
            "label_start_price": px,
        })
    if len(rows) != 102:
        raise RuntimeError(f"unexpected grid size: {len(rows)}")
    return rows


def label_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labelled = []
    for i in range(len(rows) - 1):
        r = dict(rows[i])
        r["label_end_fixing_date"] = rows[i + 1]["label_start_fixing_date"]
        r["forward_log_return"] = math.log(rows[i + 1]["label_start_price"] / rows[i]["label_start_price"])
        labelled.append(r)
    return labelled


def metrics(preds: list[dict[str, Any]]) -> dict[str, Any]:
    if not preds:
        return {"observations": 0}
    y = [r["actual"] for r in preds]
    p = [r["prediction"] for r in preds]
    sr = [r["strategy"] for r in preds]
    hits = sum(1 for a, b in zip(p, y) if a * b > 0)
    return {
        "observations": len(preds),
        "directional_accuracy": hits / len(preds),
        "prediction_return_correlation": corr(p, y),
        "strategy_total_return": math.exp(sum(sr)) - 1.0,
        "strategy_annualized_sharpe": sharpe_monthly(sr),
        "strategy_max_drawdown": max_drawdown(sr),
        "mean_monthly_strategy_log_return": mean(sr),
    }


def run_model(labelled: list[dict[str, Any]], features: list[str]) -> list[dict[str, Any]]:
    preds = []
    for t in range(MIN_TRAIN, len(labelled)):
        train = labelled[:t]
        xtr = [[r[f] for f in features] for r in train]
        ytr = [r["forward_log_return"] for r in train]
        beta, mus, sds = fit_ridge(xtr, ytr)
        x = [labelled[t][f] for f in features]
        pr = predict(beta, mus, sds, x)
        actual = labelled[t]["forward_log_return"]
        sig = 1 if pr > 0 else (-1 if pr < 0 else 0)
        preds.append({"decision_point": labelled[t]["decision_point"], "prediction": pr, "actual": actual, "strategy": sig * actual})
    return preds


def build(inf: list[dict[str, Any]], lab: list[dict[str, Any]], eur: list[dict[str, Any]], usd: list[dict[str, Any]], dates: list[str], prices: dict[str, float]) -> dict[str, Any]:
    rows = build_rows(inf, lab, eur, usd, dates, prices)
    labelled = label_rows(rows)
    models: dict[str, Any] = {}
    for name, features in MODELS.items():
        preds = run_model(labelled, features)
        blocks = {}
        for label, lo, hi in BLOCKS:
            blocks[label] = metrics([p for p in preds if lo <= p["decision_point"] <= hi])
        models[name] = {"features": features, "overall": metrics(preds), "time_blocks": blocks}
    b = models["EUR_ABSOLUTE_BASELINE"]["time_blocks"]["2025_to_2026-07"]
    r = models["RELATIVE_RATES_ONLY"]["time_blocks"]["2025_to_2026-07"]
    c = models["EUR_MACRO_PLUS_RELATIVE_RATES"]["time_blocks"]["2025_to_2026-07"]
    return {
        "schema": SCHEMA,
        "status": "DIAGNOSTIC_COMPLETE",
        "scope": {
            "instrument": "EURUSD",
            "snapshot_count": len(rows),
            "labelled_months": len(labelled),
            "oos_predictions_per_model": models["EUR_ABSOLUTE_BASELINE"]["overall"]["observations"],
            "information_set": "strict-PIT EUR Macro plus certified temporally eligible EUR and USD rates",
            "usd_macro_leg_present": False,
            "cross_market_rate_basis_identical": False,
            "cross_market_basis_caveat": "EUR=ECB AAA Svensson spot curve; USD=U.S. Treasury par curve",
        },
        "method": {
            "models_predeclared": MODELS,
            "ridge_alpha_fixed": ALPHA,
            "minimum_training_months": MIN_TRAIN,
            "hyperparameter_tuning": False,
            "test_set_model_selection": False,
            "same_day_rate_use_allowed": False,
            "label_start_rule": "first ECB EURUSD fixing strictly after decision date",
        },
        "models": models,
        "comparison_2025_to_2026_07": {
            "macro_plus_relative_minus_absolute_hit_rate": c["directional_accuracy"] - b["directional_accuracy"],
            "macro_plus_relative_minus_absolute_sharpe": c["strategy_annualized_sharpe"] - b["strategy_annualized_sharpe"],
            "macro_plus_relative_minus_absolute_total_return": c["strategy_total_return"] - b["strategy_total_return"],
            "relative_only_minus_absolute_sharpe": r["strategy_annualized_sharpe"] - b["strategy_annualized_sharpe"],
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
    result = build(
        load_macro(args.inflation, "headline_hicp_yoy_pct"),
        load_macro(args.labour, "unemployment_rate_pct"),
        load_rates(args.eur_rates),
        load_rates(args.usd_rates),
        *load_prices(args.ecb),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "comparison": result["comparison_2025_to_2026_07"], "models": result["models"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
