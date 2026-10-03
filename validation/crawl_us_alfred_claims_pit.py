#!/usr/bin/env python3
"""Reconstruct PIT first-release values for U.S. initial and continuing claims
from ALFRED vintage snapshots.

Targets:
- US_ICSA_history_value -> ICSA, seasonally adjusted initial claims
- US_CCSA_history_CCSA -> CCSA, seasonally adjusted continued claims

Method:
1. Query ALFRED graph CSV for weekday vintage dates in batches.
2. For every observation date, detect the first vintage in which a numeric value
   appears.
3. Record that value and vintage date as the first-release PIT observation.

No current revised history is used as a substitute for missing PIT observations.
"""
from __future__ import annotations

import csv
import io
import json
import time
from datetime import date, timedelta
from pathlib import Path

import requests

OUT = Path("validation/pit_batch/alfred/ALFRED_US_CLAIMS_PIT_BATCH_V1_2026-10-03.json")
BASE = "https://alfred.stlouisfed.org/graph/alfredgraph.csv"
START = date(2020, 8, 1)
END = date(2026, 10, 3)
BATCH = 12
HEADERS = {"User-Agent": "GMFQ-PIT-research/1.0"}
SERIES = {
    "ICSA": "US_ICSA_history_value",
    "CCSA": "US_CCSA_history_CCSA",
}


def weekday_vintages(start: date, end: date) -> list[str]:
    out = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def fetch_chunk(series: str, vintages: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    params = {
        "id": ",".join([series] * len(vintages)),
        "vintage_date": ",".join(vintages),
        "cosd": (START - timedelta(days=21)).isoformat(),
        "coed": END.isoformat(),
    }
    r = requests.get(BASE, params=params, headers=HEADERS, timeout=60)
    r.raise_for_status()
    reader = csv.DictReader(io.StringIO(r.text))
    rows = list(reader)
    fields = reader.fieldnames or []
    expected = [f"{series}_{v.replace('-', '')}" for v in vintages]
    actual = fields[1:]
    if actual != expected:
        raise RuntimeError(f"Unexpected ALFRED columns for {series}: {actual[:3]} ... expected {expected[:3]}")
    return fields, rows


def build_first_release(series: str, vintages: list[str]) -> tuple[list[dict], list[dict]]:
    first: dict[str, dict] = {}
    errors = []
    for i in range(0, len(vintages), BATCH):
        chunk = vintages[i:i+BATCH]
        try:
            fields, rows = fetch_chunk(series, chunk)
            date_field = fields[0]
            for row in rows:
                obs = row.get(date_field)
                if not obs or obs < START.isoformat() or obs > END.isoformat():
                    continue
                for vintage in chunk:
                    col = f"{series}_{vintage.replace('-', '')}"
                    raw = (row.get(col) or "").strip()
                    if not raw or raw == ".":
                        continue
                    try:
                        val = float(raw)
                    except ValueError:
                        continue
                    cur = first.get(obs)
                    if cur is None or vintage < cur["release_date"]:
                        first[obs] = {
                            "observation_date": obs,
                            "release_date": vintage,
                            "first_release_value": val,
                        }
        except Exception as exc:
            errors.append({"series": series, "vintages": chunk, "error": f"{type(exc).__name__}: {exc}"})
        time.sleep(0.05)
    rows = [first[k] for k in sorted(first)]
    return rows, errors


def main() -> None:
    vintages = weekday_vintages(START, END)
    payload = {
        "schema": "GMFQ_ALFRED_US_CLAIMS_PIT_BATCH_V1",
        "created_at": date.today().isoformat(),
        "provider": "Federal Reserve Bank of St. Louis ALFRED",
        "source_strategy": "ALFRED_VINTAGE_SNAPSHOTS_FIRST_APPEARANCE",
        "guardrail": "For each weekly observation, the earliest ALFRED vintage containing a numeric value is treated as the first public release. Current revised history is never substituted for missing PIT rows.",
        "vintage_scan": {"start": START.isoformat(), "end": END.isoformat(), "weekdays_scanned": len(vintages)},
        "series": {},
        "errors": [],
    }
    for fred_id, runtime_id in SERIES.items():
        rows, errors = build_first_release(fred_id, vintages)
        payload["series"][runtime_id] = {
            "fred_id": fred_id,
            "rows_found": len(rows),
            "rows": rows,
        }
        payload["errors"].extend(errors)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "weekdays_scanned": len(vintages),
        "ICSA_rows": payload["series"]["US_ICSA_history_value"]["rows_found"],
        "CCSA_rows": payload["series"]["US_CCSA_history_CCSA"]["rows_found"],
        "errors": len(payload["errors"]),
    }, indent=2))
    if payload["series"]["US_ICSA_history_value"]["rows_found"] == 0:
        raise SystemExit("No ICSA PIT rows recovered")
    if payload["series"]["US_CCSA_history_CCSA"]["rows_found"] == 0:
        raise SystemExit("No CCSA PIT rows recovered")


if __name__ == "__main__":
    main()
