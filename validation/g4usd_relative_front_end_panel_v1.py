#!/usr/bin/env python3
"""Untuned G4-vs-USD OOS panel test for relative front-end repricing.

Currencies: EUR, JPY, CAD, AUD versus USD.
Primary hypothesis: monthly change in the local-minus-USD 2Y yield differential.
Benchmarks: static 2Y differential and full relative repricing (2Y/10Y/curve).
All currencies use the same fixed expanding ridge specification. Diagnostic only.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from bisect import bisect_right
from datetime import date
from pathlib import Path

SCHEMA = "GMFQ_G4USD_RELATIVE_FRONT_END_PANEL_V1"
ALPHA = 10.0
MIN_TRAIN = 36
CCYS = ("EUR", "JPY", "CAD", "AUD")
MODELS = {
    "PRIMARY_REL_2Y_REPRICE": ["d_diff_2y"],
    "STATIC_REL_2Y": ["diff_2y"],
    "FULL_REL_REPRICE": ["d_diff_2y", "d_diff_10y", "d_diff_curve_bp"],
}
SURVIVAL = {
    "minimum_panel_sharpe": 0.50,
    "minimum_positive_currency_sharpes": 3,
    "minimum_pooled_directional_accuracy": 0.52,
    "must_beat_static_2y_panel_sharpe": True,
}
BLOCKS = [
    ("2021-04_to_2022-12", "2021-04-10", "2022-12-10"),
    ("2023_to_2024", "2023-01-10", "2024-12-10"),
    ("2025_to_2026-07", "2025-01-10", "2026-07-10"),
]


def mean(x):
    return sum(x) / len(x)


def stdev(x):
    if len(x) < 2:
        return 0.0
    m = mean(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))


def corr(a, b):
    if len(a) < 3:
        return None
    ma, mb = mean(a), mean(b)
    da = sum((x - ma) ** 2 for x in a)
    db = sum((x - mb) ** 2 for x in b)
    if da <= 0 or db <= 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(da * db)


def sharpe(r):
    s = stdev(r)
    return None if s <= 1e-12 else mean(r) / s * math.sqrt(12)


def mdd(r):
    w = p = 1.0
    d = 0.0
    for x in r:
        w *= math.exp(x)
        p = max(p, w)
        d = min(d, w / p - 1.0)
    return d


def solve(a, b):
    n = len(b)
    z = [a[i][:] + [b[i]] for i in range(n)]
    for c in range(n):
        q = max(range(c, n), key=lambda r: abs(z[r][c]))
        z[c], z[q] = z[q], z[c]
        if abs(z[c][c]) < 1e-12:
            raise RuntimeError("singular")
        k = z[c][c]
        z[c] = [v / k for v in z[c]]
        for r in range(n):
            if r == c:
                continue
            k = z[r][c]
            if k:
                z[r] = [z[r][j] - k * z[c][j] for j in range(n + 1)]
    return [z[i][-1] for i in range(n)]


def fit(x, y):
    p = len(x[0])
    mu = [mean([r[j] for r in x]) for j in range(p)]
    sd = [stdev([r[j] for r in x]) or 1.0 for j in range(p)]
    z = [[1.0] + [(r[j] - mu[j]) / sd[j] for j in range(p)] for r in x]
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
    return solve(xtx, xty), mu, sd


def predict(beta, mu, sd, x):
    return beta[0] + sum(beta[j + 1] * (x[j] - mu[j]) / sd[j] for j in range(len(x)))


def load_rates(path: Path):
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({
                "obs": r["observation_date"],
                "eligible": r["first_eligible_decision_date"],
                "y2": float(r["yield_2y"]),
                "y10": float(r["yield_10y"]),
            })
    rows.sort(key=lambda r: (r["eligible"], r["obs"]))
    return rows


def select_rate(rows, dp):
    eligible = [r for r in rows if r["eligible"] <= dp]
    if not eligible:
        raise RuntimeError(f"no eligible rate row for {dp}")
    r = eligible[-1]
    if not (r["obs"] < dp and r["eligible"] <= dp):
        raise RuntimeError(f"temporal violation at {dp}: {r}")
    return r


def load_ecb(path: Path):
    out = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        fs = rd.fieldnames or []
        dk = next(k for k in ["TIME_PERIOD", "TIME PERIOD", "Date", "DATE"] if k in fs)
        vk = next(k for k in ["OBS_VALUE", "OBS VALUE", "Value", "VALUE"] if k in fs)
        for r in rd:
            ds = (r.get(dk) or "")[:10]
            vs = (r.get(vk) or "").strip()
            try:
                date.fromisoformat(ds)
                v = float(vs)
            except Exception:
                continue
            if v > 0:
                out[ds] = v
    return out


def first_common_after(dp, *series):
    common = sorted(set.intersection(*(set(s.keys()) for s in series)))
    i = bisect_right(common, dp)
    if i >= len(common):
        raise RuntimeError(f"missing common fixing after {dp}")
    return common[i]


def month_grid():
    out = []
    y, m = 2018, 3
    while (y, m) <= (2026, 8):
        out.append(f"{y:04d}-{m:02d}-10")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def metrics(preds):
    if not preds:
        return None
    actual = [r["actual"] for r in preds]
    pred = [r["prediction"] for r in preds]
    strat = [r["strategy"] for r in preds]
    hit = sum(1 for p, a in zip(pred, actual) if (p > 0 and a > 0) or (p < 0 and a < 0)) / len(preds)
    return {
        "observations": len(preds),
        "directional_accuracy": hit,
        "prediction_return_correlation": corr(pred, actual),
        "strategy_total_return": math.exp(sum(strat)) - 1.0,
        "strategy_annualized_sharpe": sharpe(strat),
        "strategy_max_drawdown": mdd(strat),
        "mean_monthly_strategy_log_return": mean(strat),
    }


def run_model(labelled, features):
    preds = []
    for t in range(MIN_TRAIN, len(labelled)):
        tr = labelled[:t]
        beta, mu, sd = fit([[r[f] for f in features] for r in tr], [r["ret"] for r in tr])
        pr = predict(beta, mu, sd, [labelled[t][f] for f in features])
        actual = labelled[t]["ret"]
        sign = 1 if pr > 0 else -1 if pr < 0 else 0
        preds.append({
            "decision_point": labelled[t]["dp"],
            "prediction": pr,
            "actual": actual,
            "strategy": sign * actual,
        })
    blocks = {}
    for name, lo, hi in BLOCKS:
        blocks[name] = metrics([r for r in preds if lo <= r["decision_point"] <= hi])
    return {"features": features, "overall": metrics(preds), "time_blocks": blocks, "predictions": preds}


def build_currency(ccy, local_rates, usd_rates, usd_per_eur, local_per_eur):
    rows = []
    for dp in month_grid():
        lr = select_rate(local_rates, dp)
        ur = select_rate(usd_rates, dp)
        if ccy == "EUR":
            fd = first_common_after(dp, usd_per_eur)
            px = usd_per_eur[fd]
        else:
            fd = first_common_after(dp, usd_per_eur, local_per_eur)
            px = usd_per_eur[fd] / local_per_eur[fd]  # USD per local currency: positive return = local FX strength.
        lc = (lr["y10"] - lr["y2"]) * 100.0
        uc = (ur["y10"] - ur["y2"]) * 100.0
        rows.append({
            "dp": dp,
            "fixing_date": fd,
            "price": px,
            "local_obs": lr["obs"],
            "usd_obs": ur["obs"],
            "diff_2y": lr["y2"] - ur["y2"],
            "diff_10y": lr["y10"] - ur["y10"],
            "diff_curve_bp": lc - uc,
        })
    repriced = []
    for i in range(1, len(rows)):
        r = dict(rows[i])
        p = rows[i - 1]
        r["d_diff_2y"] = r["diff_2y"] - p["diff_2y"]
        r["d_diff_10y"] = r["diff_10y"] - p["diff_10y"]
        r["d_diff_curve_bp"] = r["diff_curve_bp"] - p["diff_curve_bp"]
        repriced.append(r)
    labelled = []
    for i in range(len(repriced) - 1):
        r = dict(repriced[i])
        r["ret"] = math.log(repriced[i + 1]["price"] / r["price"])
        labelled.append(r)
    models = {name: run_model(labelled, feats) for name, feats in MODELS.items()}
    return {
        "scope": {
            "snapshot_count": len(rows),
            "repricing_rows": len(repriced),
            "labelled_months": len(labelled),
            "oos_predictions_per_model": len(models["PRIMARY_REL_2Y_REPRICE"]["predictions"]),
        },
        "models": models,
    }


def panel_metrics(currency_results, model_name):
    by_date = {}
    pooled = []
    positive = 0
    per_currency = {}
    for ccy, result in currency_results.items():
        model = result["models"][model_name]
        ov = model["overall"]
        per_currency[ccy] = ov
        if ov["strategy_annualized_sharpe"] is not None and ov["strategy_annualized_sharpe"] > 0:
            positive += 1
        for p in model["predictions"]:
            pooled.append(p)
            by_date.setdefault(p["decision_point"], []).append(p["strategy"])
    monthly = [{"decision_point": d, "strategy": mean(v)} for d, v in sorted(by_date.items())]
    monthly_ret = [r["strategy"] for r in monthly]
    pooled_hit = sum(1 for r in pooled if (r["prediction"] > 0 and r["actual"] > 0) or (r["prediction"] < 0 and r["actual"] < 0)) / len(pooled)
    return {
        "currencies": len(currency_results),
        "pooled_observations": len(pooled),
        "pooled_directional_accuracy": pooled_hit,
        "positive_currency_sharpes": positive,
        "equal_weight_monthly_total_return": math.exp(sum(monthly_ret)) - 1.0,
        "equal_weight_monthly_annualized_sharpe": sharpe(monthly_ret),
        "equal_weight_monthly_max_drawdown": mdd(monthly_ret),
        "per_currency": per_currency,
    }


def main():
    ap = argparse.ArgumentParser()
    for c in ("eur", "jpy", "cad", "aud", "usd"):
        ap.add_argument(f"--{c}-rates", type=Path, required=True)
    ap.add_argument("--usd-ecb", type=Path, required=True)
    ap.add_argument("--jpy-ecb", type=Path, required=True)
    ap.add_argument("--cad-ecb", type=Path, required=True)
    ap.add_argument("--aud-ecb", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()

    rates = {c.upper(): load_rates(getattr(a, f"{c}_rates")) for c in ("eur", "jpy", "cad", "aud", "usd")}
    usd_fx = load_ecb(a.usd_ecb)
    local_fx = {
        "EUR": None,
        "JPY": load_ecb(a.jpy_ecb),
        "CAD": load_ecb(a.cad_ecb),
        "AUD": load_ecb(a.aud_ecb),
    }
    currency_results = {
        ccy: build_currency(ccy, rates[ccy], rates["USD"], usd_fx, local_fx[ccy]) for ccy in CCYS
    }
    panel = {name: panel_metrics(currency_results, name) for name in MODELS}
    primary = panel["PRIMARY_REL_2Y_REPRICE"]
    static = panel["STATIC_REL_2Y"]
    survived = (
        primary["equal_weight_monthly_annualized_sharpe"] is not None
        and primary["equal_weight_monthly_annualized_sharpe"] >= SURVIVAL["minimum_panel_sharpe"]
        and primary["positive_currency_sharpes"] >= SURVIVAL["minimum_positive_currency_sharpes"]
        and primary["pooled_directional_accuracy"] >= SURVIVAL["minimum_pooled_directional_accuracy"]
        and primary["equal_weight_monthly_annualized_sharpe"] > static["equal_weight_monthly_annualized_sharpe"]
    )
    out = {
        "schema": SCHEMA,
        "status": "DIAGNOSTIC_COMPLETE",
        "hypothesis": "Monthly local-minus-USD 2Y repricing predicts next-month local-currency strength versus USD across EUR/JPY/CAD/AUD.",
        "method": {
            "primary_model": "PRIMARY_REL_2Y_REPRICE",
            "models": MODELS,
            "ridge_alpha_fixed": ALPHA,
            "minimum_training_months": MIN_TRAIN,
            "same_rule_all_currencies": True,
            "hyperparameter_tuning": False,
            "currency_specific_tuning": False,
            "rates_source": "certified temporal-PIT 2Y/10Y rowsets",
            "fx_source": "ECB official reference rates; transformed to USD per local currency so positive return always means local FX strength",
        },
        "survival_rule_predeclared": SURVIVAL,
        "currency_results": currency_results,
        "panel_results": panel,
        "edge_survival": {
            "primary_survived": survived,
            "verdict": "SURVIVES_PREDECLARED_GATE" if survived else "FAILS_PREDECLARED_GATE",
            "primary_minus_static_panel_sharpe": primary["equal_weight_monthly_annualized_sharpe"] - static["equal_weight_monthly_annualized_sharpe"],
        },
        "policy": {
            "diagnostic_only": True,
            "production_signal_authorized": False,
            "parameter_changes_from_results_authorized": False,
        },
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"edge_survival": out["edge_survival"], "panel_results": panel}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
