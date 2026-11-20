#!/usr/bin/env python3
"""Maintain observed SNB 10Y inputs for a separate CHF 2Y change estimate."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

from check_snb_same_basis_candidate_v1 import KEYS, SOURCE, parse_candidate

SCHEMA = "GMFQ_CHF_2Y_FROM_SNB_10Y_ESTIMATE_V1"
TRAIN_START = "2022-01-01"
SPLIT = "2026-01-01"
SNB_10Y_SOURCE = "https://www.snb.ch/en/the-snb/mandates-goals/statistics/statistics-pub/current_interest_exchange_rates"
SPOT_PATH = "live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json"
OUTPUT = Path("site/fx-quant-v2/chf-2y-estimate-research.json")


def weekdays(start: date, end: date) -> int:
    weeks, tail = divmod((end - start).days, 7)
    return weeks * 5 + sum((start.weekday() + i) % 7 < 5 for i in range(tail))


def calibrate(raw: bytes, anchor: dict, asof: date) -> dict:
    source = json.loads(raw)
    basis = parse_candidate(source, certified_date=anchor["date"],
                            certified_2y=anchor["2Y"], certified_10y=anchor["10Y"])
    if basis["status"] not in ("REVIEWABLE_NEW_OFFICIAL_PAIR", "CURRENT_CANONICAL_DATE_RECONCILED"):
        raise ValueError("SNB 2Y/10Y historical basis fails")
    by_key = {s["metadata"]["key"]: {row["date"]: row["value"] for row in s["values"]}
              for s in source["timeseries"]}
    two, ten = by_key[KEYS["2Y"]], by_key[KEYS["10Y"]]
    dates = sorted(set(two) & set(ten))
    # The first observed date follows 1 January by the first working day.
    if not dates or dates[-1] > asof.isoformat() or dates[0] > "2022-01-05":
        raise ValueError("incomplete or future calibration data")
    dates = [date.fromisoformat(d) for d in dates if d >= TRAIN_START]
    train, test = {}, {}
    for i, start in enumerate(dates):
        for end in dates[i + 1:i + 11]:
            window = weekdays(start, end)
            if not 5 <= window <= 9:
                continue
            a, b = start.isoformat(), end.isoformat()
            obs = (a, b, (ten[b] - ten[a]) * 100, (two[b] - two[a]) * 100)
            if b < SPLIT:
                train.setdefault(window, []).append(obs)
            elif a >= SPLIT:
                held = test.setdefault(window, [])
                if not held or a >= held[-1][1]:
                    held.append(obs)
    horizons = {}
    for n in range(5, 10):
        fit, hold = train.get(n, []), test.get(n, [])
        if len(fit) < 250 or len(hold) < 20:
            continue
        variance = sum(x * x for _, _, x, _ in fit)
        if not variance:
            continue
        beta = sum(x * y for _, _, x, y in fit) / variance
        errors = sorted(abs(y - beta * x) for _, _, x, y in hold)
        mae = sum(errors) / len(errors)
        flat = sum(abs(y) for _, _, _, y in hold) / len(hold)
        if not 0 < beta < 2 or not mae < flat:
            continue
        horizons[str(n)] = {
            "beta": round(beta, 6),
            "abs_error_p90_bp": round(errors[math.ceil(.90 * len(errors)) - 1], 3),
            "mae_bp": round(mae, 3), "flat_mae_bp": round(flat, 3),
            "train_count": len(fit), "holdout_count": len(hold),
        }
    if not horizons:
        raise ValueError("no validated CHF 2Y-change calibration")
    return {
        "model": "CHF_2Y_CHANGE_BETA_TIMES_SNB_10Y_CHANGE",
        "source_url": SOURCE, "source_sha256": hashlib.sha256(raw).hexdigest(),
        "train_before": SPLIT, "holdout_through": dates[-1].isoformat(),
        "holdout_nonoverlapping": True, "calibration_data_latest_vintage": True,
        "horizons": horizons,
    }


def spot_observation(doc: dict, asof: date) -> dict:
    d = date.fromisoformat(doc["as_of"])
    digest, value = doc["source_html_sha256"], doc["value_percent"]
    if not (doc["schema"] == "GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1"
            and doc["status"] == "OFFICIAL_PUBLISHED_10Y_INFORMATIONAL"
            and doc["source_url"] == SNB_10Y_SOURCE
            and doc["provenance"] == "SNB_PUBLIC_PAGE_DATED_EXACT_10Y"
            and doc["yield_type"] == "SWISS_CONFEDERATION_ZERO_COUPON_SPOT"
            and doc["currency"] == "CHF" and doc["tenor"] == "10Y"
            and doc["has_current_2y"] is False and doc["eligible_for_backtests"] is False
            and d.isoformat() == doc["as_of"] and d <= asof and d.weekday() < 5
            and type(value) in (int, float) and -3 <= value <= 18
            and re.fullmatch(r"[a-f0-9]{64}", digest)):
        raise ValueError("SNB 10Y close provenance, value or date failed")
    return {"date": d.isoformat(), "yield_percent": value, "source_sha256": digest}


def update(previous: dict, spots: list[dict], asof: date) -> dict:
    if previous["schema"] != SCHEMA or previous["research_only"] is not True:
        raise ValueError("invalid CHF estimate research receipt")
    merged = {row["date"]: row for row in previous["observations"]}
    for spot in spots:
        row = spot_observation(spot, asof)
        day = row["date"]
        if day in merged and merged[day]["yield_percent"] != row["yield_percent"]:
            raise ValueError("same-date SNB 10Y revision requires review")
        merged.setdefault(day, row)
    return {**previous, "observations": [merged[d] for d in sorted(merged)[-65:]]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--snb-history", type=Path, help="Official SNB 2J/10J response to seed calibration")
    parser.add_argument("--seed-from-git", action="store_true")
    args = parser.parse_args()
    asof = date.today()
    previous = json.loads(args.output.read_text()) if args.output.exists() else {
        "schema": SCHEMA, "research_only": True,
        "eligible_for_core": False, "eligible_for_backtests": False,
        "spot_source_url": SNB_10Y_SOURCE, "observations": [],
    }
    if args.snb_history:
        native = json.loads(Path("live_data/sections/NATIVE_RATES_DATA.json").read_text())
        previous["calibration"] = calibrate(args.snb_history.read_bytes(), native["CHF"], asof)
    if "calibration" not in previous:
        raise ValueError("calibration is required before publishing observations")
    spots = [json.loads(Path(SPOT_PATH).read_text())]
    if args.seed_from_git:
        commits = subprocess.check_output(
            ["git", "log", "-65", "--format=%H", "--", SPOT_PATH], text=True).split()
        spots.extend(json.loads(subprocess.check_output(["git", "show", sha + ":" + SPOT_PATH]))
                     for sha in commits)
    doc = update(previous, spots, asof)
    serialized = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if not args.output.exists() or args.output.read_text() != serialized:
        args.output.write_text(serialized, encoding="utf-8")
    print("CHF_2Y_ESTIMATE_INPUTS", json.dumps({
        "observations_10y": len(doc["observations"]),
        "latest_10y": doc["observations"][-1]["date"],
        "calibrated_horizons": list(doc["calibration"]["horizons"]),
    }))


if __name__ == "__main__":
    main()
