#!/usr/bin/env python3
"""Read-only feasibility audit for a canonical G8 FX historical price matrix.

Source: ECB euro foreign exchange reference-rate historical daily CSV.
No repository or live_data writes are performed by this script.
"""

from __future__ import annotations

import argparse
import csv
import io
import itertools
import json
import math
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

SOURCE_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"
G8 = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"]
ECB_COLUMNS = [c for c in G8 if c != "EUR"]
START_DATE = date(2016, 1, 1)


def fetch_zip(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "GMFQ-PIT-price-matrix-audit/1.0",
            "Accept": "application/zip,application/octet-stream,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        status = getattr(r, "status", 200)
    if status != 200:
        raise RuntimeError(f"ECB download HTTP {status}")
    return raw


def load_rows(raw_zip: bytes):
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as zf:
        names = zf.namelist()
        csv_names = [n for n in names if n.lower().endswith(".csv")]
        if not csv_names:
            raise RuntimeError(f"No CSV in ECB ZIP: {names}")
        with zf.open(csv_names[0]) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8-sig", newline="")
            reader = csv.DictReader(text)
            fieldnames = [x.strip() for x in (reader.fieldnames or [])]
            missing_cols = [c for c in ["Date", *ECB_COLUMNS] if c not in fieldnames]
            if missing_cols:
                raise RuntimeError(f"Missing expected ECB columns: {missing_cols}; got {fieldnames}")
            out = []
            for row in reader:
                d = date.fromisoformat(row["Date"].strip())
                if d < START_DATE:
                    continue
                rates = {"EUR": 1.0}
                complete = True
                for c in ECB_COLUMNS:
                    raw = (row.get(c) or "").strip()
                    if not raw:
                        complete = False
                        break
                    try:
                        v = float(raw)
                    except ValueError:
                        complete = False
                        break
                    if not (math.isfinite(v) and v > 0):
                        complete = False
                        break
                    rates[c] = v
                out.append((d, complete, rates))
    return out, csv_names[0]


def cross(a: str, b: str, rates: dict[str, float]) -> float:
    # ECB rates are currency units per EUR. Therefore units of B per A = q_B / q_A.
    return rates[b] / rates[a]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    raw = fetch_zip(SOURCE_URL)
    rows, csv_name = load_rows(raw)
    if not rows:
        raise SystemExit("No rows in requested audit window")

    complete_rows = [(d, r) for d, ok, r in rows if ok]
    incomplete_dates = [d.isoformat() for d, ok, _ in rows if not ok]
    pairs = [f"{a}{b}" for a, b in itertools.combinations(G8, 2)]

    finite_cross_rows = 0
    reciprocal_max_abs_error = 0.0
    latest_sample = None
    for d, rates in complete_rows:
        vals = []
        for a, b in itertools.combinations(G8, 2):
            ab = cross(a, b, rates)
            ba = cross(b, a, rates)
            reciprocal_max_abs_error = max(reciprocal_max_abs_error, abs(ab * ba - 1.0))
            vals.append(ab)
        if len(vals) == 28 and all(math.isfinite(v) and v > 0 for v in vals):
            finite_cross_rows += 1
        latest_sample = {
            "date": d.isoformat(),
            "eur_base_rates": {c: rates[c] for c in G8},
            "sample_crosses": {
                "EURUSD": cross("EUR", "USD", rates),
                "USDJPY": cross("USD", "JPY", rates),
                "GBPUSD": cross("GBP", "USD", rates),
                "AUDNZD": cross("AUD", "NZD", rates),
                "CADCHF": cross("CAD", "CHF", rates),
            },
        }

    first_date = rows[0][0] if rows else None
    last_date = rows[-1][0] if rows else None
    # ECB CSV is normally newest-first, so use min/max rather than file order.
    all_dates = [d for d, _, _ in rows]
    min_date, max_date = min(all_dates), max(all_dates)

    checks = {
        "source_download_nonempty": len(raw) > 100_000,
        "all_7_non_eur_g8_columns_present": True,
        "window_starts_by_2016_01_04": min_date <= date(2016, 1, 4),
        "at_least_2500_complete_business_days": len(complete_rows) >= 2500,
        "all_complete_rows_generate_28_positive_crosses": finite_cross_rows == len(complete_rows),
        "reciprocal_identity_tolerance": reciprocal_max_abs_error < 1e-12,
        "latest_observation_recent": (date.today() - max_date).days <= 10,
    }
    passed = all(checks.values())

    out = {
        "schema": "GMFQ_FX_PRICE_MATRIX_ECB_FEASIBILITY_V1",
        "status": "PASS" if passed else "FAIL",
        "mode": "READ_ONLY_AUDIT",
        "source": "ECB euro foreign exchange reference rates - historical daily data",
        "source_url": SOURCE_URL,
        "source_zip_bytes": len(raw),
        "source_csv_member": csv_name,
        "method": "Use seven official ECB EUR-base G8 rates plus EUR=1.0; derive every bilateral A/B as q_B/q_A.",
        "g8_currencies": G8,
        "source_series_count": 7,
        "derived_pair_count": len(pairs),
        "derived_pairs": pairs,
        "audit_window": {
            "requested_start": START_DATE.isoformat(),
            "first_observation": min_date.isoformat(),
            "latest_observation": max_date.isoformat(),
            "rows_examined": len(rows),
            "complete_rows": len(complete_rows),
            "incomplete_rows": len(incomplete_dates),
            "incomplete_date_examples": incomplete_dates[:20],
        },
        "math_checks": {
            "finite_cross_rows": finite_cross_rows,
            "reciprocal_max_abs_error": reciprocal_max_abs_error,
        },
        "checks": checks,
        "latest_sample": latest_sample,
        "pit_note": "These are daily official reference rates with a known publication convention. They are suitable as a canonical daily close/reference-price history for forward-return measurement, subject to event-time alignment policy; they are not intraday executable prices.",
        "changes_live_data": False,
        "changes_engine_rules": False,
        "changes_oos_baseline": False,
    }

    Path(args.output).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
