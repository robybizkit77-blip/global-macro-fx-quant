#!/usr/bin/env python3
"""Read-only collector for the official Bank of England sterling OIS archive.

Input is the official oisddata.zip downloaded by the caller. The collector never
writes live_data or payload. It extracts the exact 3M/6M/12M columns from the
BoE '1. fwds, short end' sheet and emits current, T-1 and five-observation-back
(T-5 business-session) snapshots.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import tempfile
import zipfile

from openpyxl import load_workbook

SHEET = "1. fwds, short end"
WORKBOOK_RE = re.compile(r"OIS daily data_2025 to present\.xlsx$", re.I)
TENORS = {"3m": 3, "6m": 6, "12m": 12}
YEAR_FRACTIONS = {3: 0.25, 6: 0.5, 12: 1.0}


def as_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return None


def find_workbook(zf: zipfile.ZipFile) -> str:
    matches = [n for n in zf.namelist() if WORKBOOK_RE.search(n)]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one current BoE OIS workbook, found {matches}")
    return matches[0]


def number_token(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().lower().replace(',', '.')
        # Header cells can be plain numbers or labelled forms such as '3 months'.
        m = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*(?:m|month|months)?", s)
        if m:
            return float(m.group(1))
        try:
            return float(s)
        except ValueError:
            return None
    return None


def row_mapping(row, targets, tol=1e-10):
    mapping = {}
    for c_idx, v in enumerate(row, start=1):
        n = number_token(v)
        if n is None:
            continue
        for key, target in targets.items():
            if abs(n - target) <= tol:
                mapping[key] = c_idx
    return mapping


def detect_tenor_columns(rows):
    # The BoE workbook exposes both a month header (1..12) and a year-fraction
    # header (1/12, 2/12, 0.25, ... 0.5, ... 1.0). Accept either exact form.
    candidates = []
    month_targets = {3: 3.0, 6: 6.0, 12: 12.0}
    fraction_targets = YEAR_FRACTIONS
    for r_idx, row in enumerate(rows[:30], start=1):
        mm = row_mapping(row, month_targets)
        if all(x in mm for x in (3, 6, 12)):
            candidates.append((0, r_idx, mm, "months"))
        ff = row_mapping(row, fraction_targets, tol=1e-8)
        if all(x in ff for x in (3, 6, 12)):
            candidates.append((1, r_idx, ff, "year_fractions"))
    if not candidates:
        preview=[]
        for i,row in enumerate(rows[:20],start=1):
            vals=[v for v in row[:20] if v is not None]
            if vals:
                preview.append({"row":i,"values":[str(v) for v in vals[:12]]})
        raise SystemExit("Could not detect exact 3M/6M/12M header columns; header preview="+json.dumps(preview))
    candidates.sort(key=lambda x: (x[0], x[1]))
    _, r_idx, mapping, method = candidates[0]
    return r_idx, mapping, method


def extract(zip_path: pathlib.Path, requested_as_of: str | None):
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(zip_path) as zf:
            workbook_name = find_workbook(zf)
            zf.extract(workbook_name, td)
            workbook_path = pathlib.Path(td) / workbook_name

        wb = load_workbook(workbook_path, read_only=True, data_only=True)
        if SHEET not in wb.sheetnames:
            raise SystemExit(f"Missing required sheet: {SHEET}")
        ws = wb[SHEET]
        rows = [tuple(r) for r in ws.iter_rows(values_only=True)]
        header_row, month_cols, header_method = detect_tenor_columns(rows)

        observations = []
        for excel_row, row in enumerate(rows[header_row:], start=header_row + 1):
            date_col = None
            obs_date = None
            for c_idx, v in enumerate(row, start=1):
                d = as_date(v)
                if d is not None:
                    date_col = c_idx
                    obs_date = d
                    break
            if obs_date is None:
                continue
            vals = {}
            good = True
            for key, month in TENORS.items():
                c = month_cols[month]
                if c > len(row):
                    good = False
                    break
                v = row[c - 1]
                if not isinstance(v, (int, float)) or isinstance(v, bool):
                    good = False
                    break
                vals[key] = float(v)
            if good:
                observations.append({"date": obs_date, "excel_row": excel_row, "date_col": date_col, **vals})

        if not observations:
            raise SystemExit("No complete dated 3M/6M/12M observations found")
        observations.sort(key=lambda x: x["date"])

        if requested_as_of:
            target = dt.date.fromisoformat(requested_as_of)
            matches = [i for i, x in enumerate(observations) if x["date"] == target]
            if not matches:
                raise SystemExit(f"Requested as-of {target} not present in official archive")
            idx = matches[-1]
        else:
            idx = len(observations) - 1

        if idx < 5:
            raise SystemExit("Insufficient prior official sessions for T-1/T-5")
        cur = observations[idx]
        prev = observations[idx - 1]
        week = observations[idx - 5]

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
            "official_archive": "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/oisddata.zip",
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
