#!/usr/bin/env python3
"""Read-only collector for official Bank of England sterling OIS curve packages.

Historical requests use the BoE archive. Latest requests combine the separate
BoE "Latest yield curve data" current-month package with the BoE historical
archive as same-series backfill, so T-1/T-5 remain exact across month boundaries.
The current observation must always originate from the latest package.
No interpolation is used and this collector never writes live_data or payload.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import tempfile
import urllib.request
import zipfile

import pandas as pd

SHEET = "1. fwds, short end"
LATEST_URL = "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/latest-yield-curve-data.zip"
ARCHIVE_URL = "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/oisddata.zip"
WORKBOOK_PATTERNS = (
    (re.compile(r"OIS daily data_2025 to present\.xlsx$", re.I), "ARCHIVE_HISTORY", ARCHIVE_URL),
    (re.compile(r"OIS daily data current month\.xlsx$", re.I), "LATEST_DAILY", LATEST_URL),
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


def inspect_package(zip_path: pathlib.Path):
    with zipfile.ZipFile(zip_path) as zf:
        return find_workbook(zf)


def download(url: str, destination: pathlib.Path):
    req = urllib.request.Request(url, headers={"User-Agent": "GLOBAL-MACRO-FX-QUANT daily observation"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r, destination.open("wb") as f:
            f.write(r.read())
    except Exception as exc:
        raise SystemExit(f"Official BoE package download failed for {url}: {exc}")
    inspect_package(destination)


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


def load_package(zip_path: pathlib.Path):
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(zip_path) as zf:
            workbook_name, pkg_kind, pkg_url = find_workbook(zf)
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
            obs_date = next((cell_date(v) for v in row if cell_date(v) is not None), None)
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
            raise SystemExit(f"No complete dated 3M/6M/12M observations found in {workbook_name}")
        observations.sort(key=lambda x: x["date"])
        return {
            "package_kind": pkg_kind,
            "package_url": pkg_url,
            "workbook": workbook_name,
            "header_detection": header_method,
            "observations": observations,
        }


def clean(x):
    return {"date": x["date"].isoformat(), "3m": x["3m"], "6m": x["6m"], "12m": x["12m"]}


def make_snapshot(current, prev, week, latest_meta, archive_meta=None):
    current, t1, t5 = clean(current), clean(prev), clean(week)
    change_1d = {k: round((current[k] - t1[k]) * 100.0, 4) for k in TENORS}
    change_1w = {k: round((current[k] - t5[k]) * 100.0, 4) for k in TENORS}
    is_latest = latest_meta["package_kind"] == "LATEST_DAILY"
    package_kind = "LATEST_DAILY_WITH_ARCHIVE_BACKFILL" if is_latest and archive_meta else latest_meta["package_kind"]
    out = {
        "schema": "GMFQ_CB_PRICING_SOURCE_SNAPSHOT_V1",
        "currency": "GBP",
        "status": "SOURCE_SNAPSHOT_ONLY",
        "source": "Bank of England · estimated sterling OIS yield curves · daily OIS archive",
        "source_url": "https://www.bankofengland.co.uk/statistics/yield-curves",
        "official_archive": latest_meta["package_url"],
        "package_kind": package_kind,
        "workbook": latest_meta["workbook"],
        "sheet": SHEET,
        "instrument": "UK instantaneous OIS forward curve based on SONIA",
        "quotation": "annualised continuously-compounded forward rate, percent",
        "horizon_mapping": "exact 3M / 6M / 12M columns; no interpolation",
        "header_detection": latest_meta["header_detection"],
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
            "payload_mutated": False,
            "latest_current_from_official_daily_package": is_latest,
            "historical_backfill_same_official_series": bool(archive_meta),
        },
    }
    if archive_meta:
        out["history_backfill_url"] = archive_meta["package_url"]
        out["history_backfill_workbook"] = archive_meta["workbook"]
    return out


def historical_snapshot(supplied_zip: pathlib.Path, requested_as_of: str):
    meta = load_package(supplied_zip)
    target = dt.date.fromisoformat(requested_as_of)
    observations = meta["observations"]
    matches = [i for i, x in enumerate(observations) if x["date"] == target]
    if not matches:
        raise SystemExit(f"Requested as-of {target} not present in official package")
    idx = matches[-1]
    if idx < 5:
        raise SystemExit("Insufficient prior official sessions for T-1/T-5")
    return make_snapshot(observations[idx], observations[idx - 1], observations[idx - 5], meta)


def latest_snapshot(supplied_zip: pathlib.Path):
    supplied_meta = load_package(supplied_zip)
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        if supplied_meta["package_kind"] == "LATEST_DAILY":
            latest_meta = supplied_meta
            archive_path = td / "boe-archive.zip"
            download(ARCHIVE_URL, archive_path)
            archive_meta = load_package(archive_path)
        elif supplied_meta["package_kind"] == "ARCHIVE_HISTORY":
            archive_meta = supplied_meta
            latest_path = td / "boe-latest.zip"
            download(LATEST_URL, latest_path)
            latest_meta = load_package(latest_path)
        else:
            raise SystemExit(f"Unsupported supplied BoE package kind {supplied_meta['package_kind']}")

        if latest_meta["package_kind"] != "LATEST_DAILY":
            raise SystemExit("Latest GBP collection did not resolve to official BoE LATEST_DAILY package")
        if archive_meta["package_kind"] != "ARCHIVE_HISTORY":
            raise SystemExit("GBP history backfill did not resolve to official BoE ARCHIVE_HISTORY package")

        latest_dates = {x["date"] for x in latest_meta["observations"]}
        if not latest_dates:
            raise SystemExit("BoE latest package contains no complete observations")
        current_date = max(latest_dates)

        merged = {x["date"]: x for x in archive_meta["observations"]}
        # Prefer the daily Latest package on overlapping dates.
        merged.update({x["date"]: x for x in latest_meta["observations"]})
        observations = [merged[d] for d in sorted(merged)]
        matches = [i for i, x in enumerate(observations) if x["date"] == current_date]
        if len(matches) != 1:
            raise SystemExit("Could not locate unique latest current date in merged BoE series")
        idx = matches[0]
        if idx < 5:
            raise SystemExit("Insufficient official same-series history after archive backfill")
        current, prev, week = observations[idx], observations[idx - 1], observations[idx - 5]
        if current["date"] not in latest_dates:
            raise SystemExit("Current GBP observation did not originate from BoE Latest package")
        return make_snapshot(current, prev, week, latest_meta, archive_meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=pathlib.Path)
    ap.add_argument("--as-of", help="YYYY-MM-DD; omit for latest complete official observation")
    ap.add_argument("--output", type=pathlib.Path)
    args = ap.parse_args()

    result = historical_snapshot(args.zip, args.as_of) if args.as_of else latest_snapshot(args.zip)
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
