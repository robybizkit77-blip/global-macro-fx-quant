#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

WINDOW = 52
RESEARCH_STATE = "RESEARCH_NOT_VALIDATED"
B1_STATUS = "NOT_EVALUATED_CANONICAL_SPEC_NOT_MATERIALIZED"
B2_STATUS = "NOT_EVALUATED_CANONICAL_SPEC_NOT_MATERIALIZED"
REGIME_STATUS = "NOT_CLASSIFIED_NO_CANONICAL_THRESHOLD_MATERIALIZED"
REQUIRED = ("week_end", "pair", "fx_return", "delta_rel_2y")


def _iso_date(value):
    parsed = dt.date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError(f"non-canonical ISO date: {value}")
    return parsed


def _finite_float(value, field):
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"non-finite {field}: {value}")
    return out


def load_panel(path):
    grouped = defaultdict(list)
    seen = set()
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or any(c not in reader.fieldnames for c in REQUIRED):
            raise ValueError(f"required columns: {','.join(REQUIRED)}")
        for row in reader:
            week = _iso_date(row["week_end"])
            pair = row["pair"].strip().upper()
            if not pair:
                raise ValueError("empty pair")
            key = (pair, week)
            if key in seen:
                raise ValueError(f"duplicate pair/week_end: {pair} {week}")
            seen.add(key)
            grouped[pair].append(
                (week, _finite_float(row["fx_return"], "fx_return"), _finite_float(row["delta_rel_2y"], "delta_rel_2y"))
            )
    for pair in grouped:
        grouped[pair].sort(key=lambda x: x[0])
    return grouped


def ols_beta(window):
    xs = [r[2] for r in window]
    ys = [r[1] for r in window]
    xbar = sum(xs) / len(xs)
    ybar = sum(ys) / len(ys)
    denom = sum((x - xbar) ** 2 for x in xs)
    if denom == 0:
        return None
    return sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / denom


def compute_pair(pair, rows):
    n = len(rows)
    base = {
        "pair": pair,
        "observations": n,
        "latest_week_end": rows[-1][0].isoformat() if rows else None,
        "window_observations": WINDOW,
        "beta_current": None,
        "beta_previous": None,
        "beta_change": None,
        "sample_depth": n,
        "status": "INSUFFICIENT_HISTORY" if n < WINDOW else "READY_OBSERVATIONAL",
        "research_state": RESEARCH_STATE,
        "b1_status": B1_STATUS,
        "b2_status": B2_STATUS,
        "regime_status": REGIME_STATUS,
    }
    if n < WINDOW:
        return base
    current = ols_beta(rows[-WINDOW:])
    if current is None:
        base["status"] = "BETA_UNDEFINED_ZERO_VARIANCE"
        return base
    base["beta_current"] = current
    if n >= WINDOW + 1:
        previous = ols_beta(rows[-WINDOW - 1:-1])
        base["beta_previous"] = previous
        if previous is not None:
            base["beta_change"] = current - previous
    return base


def compute(panel):
    return {
        "schema": "GMFQ_RATE_BETA_OBSERVATIONAL_OUTPUT_V1",
        "window_observations": WINDOW,
        "research_state": RESEARCH_STATE,
        "pairs": [compute_pair(pair, rows) for pair, rows in sorted(panel.items())],
    }


def main():
    parser = argparse.ArgumentParser(description="Observational 52W RATE_BETA plumbing. No B1/B2 evaluation.")
    parser.add_argument("input_csv")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = compute(load_panel(args.input_csv))
    encoded = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
