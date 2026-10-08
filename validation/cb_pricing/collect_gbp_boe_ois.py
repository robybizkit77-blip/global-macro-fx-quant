#!/usr/bin/env python3
"""Read-only collector for official Bank of England sterling OIS curve packages.

Supports both the historical archive package and the separate daily "Latest yield
curve data" package. The economic series and parser are identical: exact 3M,
6M and 12M columns from the BoE short-end SONIA/OIS forward curve, no
interpolation. It never writes live_data or payload.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import tempfile
import zipfile

import pandas as pd

SHEET = "1. fwds, short end"
WORKBOOK_PATTERNS = (
    (re.compile(r"OIS daily data_2025 to present\.xlsx$", re.I), "ARCHIVE_HISTORY", "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/oisddata.zip"),
    (re.compile(r"OIS daily data current month\.xlsx$", re.I), "LATEST_DAILY", "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/latest-yield-curve-data.zip"),
)
TENORS = {"3m": 3, "6m": 6, "12m": 12}


def find_workbook(zf: zipfile.ZipFile):
    matches = []
    for name in zf.namelist():
        for pattern, package_kind, package_url in WORKBOOK_PATTERNS:
            if pattern.search(name):
                matches.append((name, package_kind, package_url))
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one supported BoE OIS workbook, found {matches}")
    return matches[0]


def num(v):
    if pd.isna(v) or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lower().replace(",", ".")
    m = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*(?:m|month|months|y|year|years)?", s)
    if m:
        return float(m.group(1))
    try:
        return float(s)
    except ValueError:
        return None


def detect_tenor_columns(df: pd.DataFrame):
    month_targets = {3: 3.0, 6: 6.0, 12: 12.0}
    frac_targets = {3: 0.25, 6: 0.5, 12: 1.0}
    candidates = []
    for r_idx in range(min(30, len(df))):
        row = df.iloc[r_idx].tolist()
        for priority, targets, method in ((0, month_targets, "months"), (1, frac_targets, "year_fractions")):
            mapping = {}
            for c_idx, v in enumerate(row):
                n = num(v)
                if n is None:
                    continue
                for month, target in targets.items():
                    if abs(n - target) <= 1e-8:
                        mapping[month] = c_idx
            if all(m in mapping for m in (3, 6, 12)):
                candidates.append((priority, r_idx, mapping, method))
    if not candidates:
        preview = []
        for i in range(min(15, len(df))):
            vals = [str(v) for v in df.iloc[i].tolist() if not pd.isna(v)]
            if vals:
                preview.append({"row": i, "values": vals[:18]})
        raise SystemExit("Could not detect exact 3M/6M/12M header columns; preview=" + json.dumps(preview))
    candidates.sort(key=lambda x: (x[0], x[1]))
    _, row_idx, mapping, method = candidates[0]
    return row_idx, mapping, method


def cell_date(v):
    if pd.isna(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.date()
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return None


def extract(zip_path: pathlib.Path, requested_as_of: str | None):
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(zip_path) as zf:
            workbook_name, package_kind, package_url = find_workbook(zf)
            zf.extract(workbook_name, td)
            workbook_path = pathlib.Path(td) / workbook_name

        xls = pd.ExcelFile(workbook_path)
        if SHEET not in xls.sheet_names:
            raise SystemExit(f"Missing required sheet: {SHEET}")
        df = pd.read_excel(workbook_path, sheet_name=SHEET, header=None)
        header_row, month_cols, header_method = detect_tenor_columns(df)

        observations = []
        for r_idx in range(header_row + 1, len(df)):
            row = df.iloc[r_idx].tolist()
            obs_date = None
            for v in row:
                d = cell_date(v)
                if d is not None:
                    obs_date = d
                    break
            if obs_date is None:
                continue
            vals = {}
            for key, month in TENORS.items():
                v = row[month_cols[month]]
                if pd.isna(v) or not isinstance(v, (int, float)):
                    vals = {}
                    break
                vals[key] = float(v)
            if vals:
                observations.append({"date": obs_date, **vals})

        if not observations:
            raise SystemExit("No complete dated 3M/6M/12M observations found")
        observations.sort(key=lambda x: x["date"])

        if requested_as_of:
            target = dt.date.fromisoformat(requested_as_of)
            matches = [i for i, x in enumerate(observations) if x["date"] == target]
            if not matches:
                raise SystemExit(f"Requested as-of {target} not present in official package")
            idx = matches[-1]
        else:
            idx = len(observations) - 1

        if idx < 5:
            raise SystemExit("Insufficient prior official sessions for T-1/T-5")
        cur, prev, week = observations[idx], observations[idx - 1], observations[idx - 5]

        def clean(x):
            return {"date": x["date"].isoformat(), "3m": x["3m"], "6m": x["6m"], "12m": x["12m"]}

        current, t1, t5 = clean(cur), clean(prev), clean(week)
        change_1d = {k: round((current[k] - t1[k]) * 100.0, 4) for k in TENORS}
        change_1w = {k: round((current[k] - t5[k]) * 100.0, 4) for k in TENORS}

        return {
            "schema": "GMFQ_CB_PRICING_SOURCE_SNAPSHOT_V1",
            "currency": "GBP",
            "status": "SOURCE_SNAPSHOT_ONLY",
            "source": "Bank of England · estimated sterling OIS yield curves · daily OIS archive",
            "source_url": "https://www.bankofengland.co.uk/statistics/yield-curves",
            "official_archive": package_url,
            "package_kind": package_kind,
            "workbook": workbook_name,
            "sheet": SHEET,
            "instrument": "UK instantaneous OIS forward curve based on SONIA",
            "quotation": "annualised continuously-compounded forward rate, percent",
            "horizon_mapping": "exact 3M / 6M / 12M columns; no interpolation",
            "header_detection": header_method,
            "as_of": current["date"],
            "observations": {"current": current, "t_minus_1": t1, "t_minus_5": t5},
            "change_1d_bp": change_1d,
            "change_1w_bp": change_1w,
            "validation": {
                "official_source": True,
                "exact_tenor_columns": True,
                "no_interpolation": True,
                "homogeneous_sessions": True,
                "runtime_mutated": False,
                "payload_mutated": False
            }
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=pathlib.Path)
    ap.add_argument("--as-of", help="YYYY-MM-DD; omit for latest complete official observation")
    ap.add_argument("--output", type=pathlib.Path)
    args = ap.parse_args()
    result = extract(args.zip, args.as_of)
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
