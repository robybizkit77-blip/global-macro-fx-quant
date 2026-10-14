#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import tempfile
from datetime import date
from pathlib import Path

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILWTICO&cosd=2016-01-01"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    date.fromisoformat(args.as_of)

    with tempfile.TemporaryDirectory() as td:
        csv_path = Path(td) / "DCOILWTICO.csv"
        cmd = [
            "curl", "--http1.1", "-fL", "--compressed", "--retry", "5", "--retry-all-errors",
            "--retry-delay", "3", "--connect-timeout", "20", "--max-time", "180",
            "-A", "Mozilla/5.0", f"{URL}&coed={args.as_of}", "-o", str(csv_path),
        ]
        subprocess.run(cmd, check=True)
        text = csv_path.read_text(encoding="utf-8-sig")

    rows = []
    for rr in csv.DictReader(io.StringIO(text)):
        ds = (rr.get("observation_date") or rr.get("DATE") or "").strip()
        vs = (rr.get("DCOILWTICO") or "").strip()
        if not ds or vs in ("", ".", "NA", "N/A"):
            continue
        try:
            date.fromisoformat(ds)
            value = float(vs)
        except Exception:
            continue
        if ds <= args.as_of:
            rows.append({"date": ds, "value": value})

    rows.sort(key=lambda x: x["date"])
    if len(rows) < 500:
        raise SystemExit(f"WTI official history too short: {len(rows)}")
    dates = [x["date"] for x in rows]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise SystemExit("WTI source dates are not strictly unique/monotonic")
    if dates[0] > "2016-01-31":
        raise SystemExit(f"WTI source history starts too late: {dates[0]}")

    candidate = {
        "schema": "GMFQ_RISK_WTI_CANDIDATE_V1",
        "status": "GREEN_OFFICIAL_SOURCE_CANDIDATE",
        "as_of": args.as_of,
        "source": {
            "publisher": "U.S. Energy Information Administration via FRED",
            "series_name": "Crude Oil Prices: West Texas Intermediate (WTI) - Cushing, Oklahoma",
            "series_id": "DCOILWTICO",
            "transport": "FRED canonical CSV mirror of EIA series",
            "frequency": "Daily",
        },
        "observation_count": len(rows),
        "first_date": rows[0]["date"],
        "last_date": rows[-1]["date"],
        "last_value": rows[-1]["value"],
        "observations": rows,
    }
    Path(args.out).write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt = {k: v for k, v in candidate.items() if k != "observations"}
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
