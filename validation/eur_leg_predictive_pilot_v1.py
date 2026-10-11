#!/usr/bin/env python3
"""EUR-side Macro+Rates predictive diagnostic against future EUR/USD returns.

This is intentionally NOT the final relative EURUSD model: it has only the EUR
leg because the USD Macro leg is not yet fully strict-PIT certified. The test is
therefore a diagnostic of whether the certified EUR information set contains
out-of-sample predictive information for EURUSD.

Design is fixed ex ante:
- monthly decision points from certified snapshots;
- official ECB EUR/USD reference-rate history;
- price label starts at the first ECB fixing STRICTLY AFTER a decision date;
- one-month forward log return to the first fixing strictly after next decision;
- five fixed features: inflation, unemployment, 2Y, 10Y, 10Y-2Y curve;
- expanding-window ridge regression, fixed alpha=10, minimum 36 labelled months;
- training-only standardization at every step; no hyperparameter tuning;
- no position sizing, transaction-cost optimisation, or production trading use.
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

SCHEMA = "GMFQ_EUR_LEG_PREDICTIVE_PILOT_V1"
FEATURES = ["inflation", "unemployment", "yield_2y", "yield_10y", "curve_bp"]
RIDGE_ALPHA = 10.0
MIN_TRAIN = 36


def read_json(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def load_snapshots(directory: Path) -> list[dict[str, Any]]:
    rows = []
    for p in sorted(directory.glob("*-snapshot.json")):
        s = read_json(p)
        if s.get("schema") != "GMFQ_WALKFORWARD_INPUT_SNAPSHOT_V1" or s.get("status") != "SNAPSHOT_MATERIALIZED":
            raise RuntimeError(f"invalid snapshot {p}")
        if s.get("currency") != "EUR":
            raise RuntimeError(f"non-EUR snapshot {p}")
        pol = s.get("policy") or {}
        if pol.get("future_information_allowed") is not False or pol.get("backtest_execution_authorized") is not False:
            raise RuntimeError(f"unsafe snapshot policy {p}")
        macro = s["layers"]["Macro"]["rows"]
        rates = s["layers"]["Rates"]["row"]
        inf = macro["EUR.inflation"]
        lab = macro["EUR.labour"]
        dp = s["decision_point"]
        if not (inf["release_date"] < dp and lab["release_date"] < dp and rates["observation_date"] < dp):
            raise RuntimeError(f"temporal violation in {p}")
        rows.append({
            "decision_point": dp,
            "snapshot_sha256": s["snapshot_sha256"],
            "inflation": float(inf["value"]),
            "unemployment": float(lab["value"]),
            "yield_2y": float(rates["yield_2y"]),
            "yield_10y": float(rates["yield_10y"]),
            "curve_bp": float(rates["curve_bp"]),
        })
    if len(rows) < MIN_TRAIN + 2:
        raise RuntimeError("insufficient snapshots")
    dps = [r["decision_point"] for r in rows]
    if dps != sorted(dps) or len(set(dps)) != len(dps):
        raise RuntimeError("snapshot chronology invalid")
    return rows


def load_ecb_prices(path: Path) -> tuple[list[str], dict[str, float]]:
    prices: dict[str, float] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        fields = rd.fieldnames or []
        date_key = next((k for k in ["TIME_PERIOD", "TIME PERIOD", "Date", "DATE"] if k in fields), None)
        value_key = next((k for k in ["OBS_VALUE", "OBS VALUE", "Value", "VALUE"] if k in fields), None)
        if not date_key or not value_key:
            raise RuntimeError(f"ECB CSV columns not recognised: {fields}")
        for row in rd:
            d = (row.get(date_key) or "").strip()[:10]
            v = (row.get(value_key) or "").strip()
            if not d or not v:
                continue
            try:
                date.fromisoformat(d)
                x = float(v)
            except Exception:
                continue
            if x > 0:
                prices[d] = x
    dates = sorted(prices)
    if len(dates) < 1000:
        raise RuntimeError(f"too few ECB FX observations: {len(dates)}")
    return dates, prices


def first_fixing_strictly_after(dp: str, dates: list[str], prices: dict[str, float]) -> tuple[str, float]:
    i = bisect_right(dates, dp)
    if i >= len(dates):
        raise RuntimeError(f"no ECB fixing after {dp}")
    d = dates[i]
    return d, prices[d]


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def stdev(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x-m)**2 for x in xs) / (len(xs)-1))


def solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    aug = [a[i][:] + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            raise RuntimeError("singular ridge system")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        q = aug[col][col]
        aug[col] = [v/q for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            q = aug[r][col]
            if q:
                aug[r] = [aug[r][c] - q*aug[col][c] for c in range(n+1)]
    return [aug[i][-1] for i in range(n)]


def fit_ridge(x: list[list[float]], y: list[float], alpha: float) -> tuple[list[float], list[float], list[float]]:
    p = len(x[0])
    mus = [mean([r[j] for r in x]) for j in range(p)]
    sds = [stdev([r[j] for r in x]) for j in range(p)]
    sds = [s if s > 1e-12 else 1.0 for s in sds]
    z = [[1.0] + [(r[j]-mus[j])/sds[j] for j in range(p)] for r in x]
    k = p + 1
    xtx = [[0.0]*k for _ in range(k)]
    xty = [0.0]*k
    for row, target in zip(z, y):
        for i in range(k):
            xty[i] += row[i] * target
            for j in range(k):
                xtx[i][j] += row[i] * row[j]
    for i in range(1, k):
        xtx[i][i] += alpha
    beta = solve(xtx, xty)
    return beta, mus, sds


def predict(beta: list[float], mus: list[float], sds: list[float], x: list[float]) -> float:
    return beta[0] + sum(beta[j+1] * ((x[j]-mus[j])/sds[j]) for j in range(len(x)))


def corr(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3:
        return None
    ma, mb = mean(a), mean(b)
    da = sum((x-ma)**2 for x in a)
    db = sum((x-mb)**2 for x in b)
    if da <= 0 or db <= 0:
        return None
    return sum((x-ma)*(y-mb) for x,y in zip(a,b)) / math.sqrt(da*db)


def sharpe_monthly(r: list[float]) -> float | None:
    s = stdev(r)
    return None if s <= 1e-12 else mean(r)/s*math.sqrt(12.0)


def max_drawdown(r: list[float]) -> float:
    wealth = peak = 1.0
    mdd = 0.0
    for x in r:
        wealth *= math.exp(x)
        peak = max(peak, wealth)
        mdd = min(mdd, wealth/peak - 1.0)
    return mdd


def build(rows: list[dict[str, Any]], price_dates: list[str], prices: dict[str, float]) -> dict[str, Any]:
    # Attach conservative post-decision fixings.
    for r in rows:
        fd, px = first_fixing_strictly_after(r["decision_point"], price_dates, prices)
        r["label_start_fixing_date"] = fd
        r["label_start_price"] = px

    # Label i is return from first fixing after decision i to first fixing after decision i+1.
    labelled = []
    for i in range(len(rows)-1):
        r = dict(rows[i])
        p0 = rows[i]["label_start_price"]
        p1 = rows[i+1]["label_start_price"]
        r["label_end_decision_point"] = rows[i+1]["decision_point"]
        r["label_end_fixing_date"] = rows[i+1]["label_start_fixing_date"]
        r["forward_log_return"] = math.log(p1/p0)
        labelled.append(r)

    preds = []
    for t in range(MIN_TRAIN, len(labelled)):
        train = labelled[:t]
        xtr = [[r[f] for f in FEATURES] for r in train]
        ytr = [r["forward_log_return"] for r in train]
        beta, mus, sds = fit_ridge(xtr, ytr, RIDGE_ALPHA)
        xt = [labelled[t][f] for f in FEATURES]
        pr = predict(beta, mus, sds, xt)
        y = labelled[t]["forward_log_return"]
        sig = 1 if pr > 0 else (-1 if pr < 0 else 0)
        preds.append({
            "decision_point": labelled[t]["decision_point"],
            "label_start_fixing_date": labelled[t]["label_start_fixing_date"],
            "label_end_fixing_date": labelled[t]["label_end_fixing_date"],
            "prediction": pr,
            "actual_forward_log_return": y,
            "signal": sig,
            "strategy_log_return": sig*y,
            "train_observations": t,
        })

    if len(preds) < 24:
        raise RuntimeError("too few OOS predictions")
    y = [r["actual_forward_log_return"] for r in preds]
    p = [r["prediction"] for r in preds]
    sr = [r["strategy_log_return"] for r in preds]
    hit = sum(1 for a,b in zip(p,y) if (a > 0 and b > 0) or (a < 0 and b < 0)) / len(preds)
    long_total = math.exp(sum(y))-1.0
    strat_total = math.exp(sum(sr))-1.0
    return {
        "schema": SCHEMA,
        "status": "DIAGNOSTIC_BACKTEST_COMPLETE",
        "scope": {
            "instrument": "EURUSD",
            "information_set": "EUR leg only: strict-PIT EUR inflation + unemployment + EUR 2Y/10Y rates",
            "important_limitation": "USD Macro leg is absent; this is not the final relative FX model backtest.",
            "snapshot_count": len(rows),
            "labelled_months": len(labelled),
            "oos_predictions": len(preds),
            "first_oos_decision": preds[0]["decision_point"],
            "last_oos_decision": preds[-1]["decision_point"],
        },
        "method": {
            "features": FEATURES,
            "model": "expanding-window ridge regression",
            "ridge_alpha_fixed": RIDGE_ALPHA,
            "minimum_training_months": MIN_TRAIN,
            "hyperparameter_tuning": False,
            "standardization": "training window only at each OOS step",
            "return_horizon": "next monthly decision point",
            "price_source": "ECB official EUR/USD reference rate",
            "label_start_rule": "first ECB fixing strictly after decision date",
            "transaction_costs": "not applied; diagnostic only",
            "position_sizing": "unit sign only; diagnostic only",
        },
        "oos_metrics": {
            "directional_accuracy": hit,
            "prediction_return_correlation": corr(p,y),
            "strategy_total_return": strat_total,
            "strategy_annualized_sharpe": sharpe_monthly(sr),
            "strategy_max_drawdown": max_drawdown(sr),
            "mean_monthly_strategy_log_return": mean(sr),
            "long_eurusd_total_return_same_window": long_total,
            "long_eurusd_annualized_sharpe_same_window": sharpe_monthly(y),
        },
        "predictions": preds,
        "policy": {
            "diagnostic_backtest_executed": True,
            "production_backtest_authorized": False,
            "production_signal_authorized": False,
            "position_sizing_authorized": False,
            "model_selection_from_test_set_allowed": False,
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
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "scope": result["scope"], "oos_metrics": result["oos_metrics"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
