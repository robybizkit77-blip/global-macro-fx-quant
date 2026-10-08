#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SERIES_PATH = ROOT / "live_data" / "sections" / "MACRO_SERIES.json"
HEATMAP_PATH = ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json"
API_BASE = "https://api.beta.ons.gov.uk/v1/data"
SOURCE = "Office for National Statistics"

CONFIG: dict[str, dict[str, Any]] = {
    "inflation": {
        "series_id": "D7G7",
        "dataset": "MM23",
        "uri": "/economy/inflationandpriceindices/timeseries/d7g7/mm23",
        "source_url": "https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23",
        "expected_heatmap_series_id": "D7G7",
        "expected_transformation": "reported_yoy_rate",
        "unit": "% YoY",
        "macro_series_id": "UK_CPI_HEADLINE_YOY_history_value",
    },
    "labour": {
        "series_id": "MGSX",
        "dataset": "LMS",
        "uri": "/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms",
        "source_url": "https://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms",
        "expected_heatmap_series_id": "MGSX",
        "expected_transformation": "level",
        "unit": "%",
        "macro_series_id": "UK_UNEMP_RATE_history_value",
    },
}

MONTHS = {
    "JAN": 1, "JANUARY": 1,
    "FEB": 2, "FEBRUARY": 2,
    "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4,
    "MAY": 5,
    "JUN": 6, "JUNE": 6,
    "JUL": 7, "JULY": 7,
    "AUG": 8, "AUGUST": 8,
    "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10,
    "NOV": 11, "NOVEMBER": 11,
    "DEC": 12, "DECEMBER": 12,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_month(row: dict[str, Any]) -> str:
    date = str(row.get("date", "")).strip()
    year = str(row.get("year", "")).strip()
    month = str(row.get("month", "")).strip().upper()
    if date:
        parts = date.replace("-", " ").split()
        if len(parts) >= 2 and parts[0].isdigit():
            y = int(parts[0])
            m = MONTHS.get(parts[1].upper())
            if m:
                return f"{y:04d}-{m:02d}"
    if year.isdigit() and month in MONTHS:
        return f"{int(year):04d}-{MONTHS[month]:02d}"
    raise ValueError(f"cannot parse ONS monthly period from row: {row}")


def extract_months(payload: dict[str, Any]) -> list[tuple[str, float]]:
    months = payload.get("months")
    if not isinstance(months, list):
        raise ValueError("ONS payload does not contain months list")
    out: dict[str, float] = {}
    for row in months:
        if not isinstance(row, dict):
            continue
        raw = row.get("value")
        if raw in (None, "", "..", "-"):
            continue
        date = parse_month(row)
        value = float(str(raw).replace(",", ""))
        if date in out and abs(out[date] - value) > 1e-12:
            raise ValueError(f"conflicting ONS values for {date}")
        out[date] = value
    if len(out) < 2:
        raise ValueError(f"need at least two ONS monthly observations; got {len(out)}")
    return [(date, out[date]) for date in sorted(out)]


def resolve_heatmap_contract(dimension: str) -> tuple[str, str, str]:
    heat = load_json(HEATMAP_PATH)
    row = heat["currencies"]["GBP"][dimension]
    cfg = CONFIG[dimension]
    series_id = str(row.get("series_id"))
    frequency = str(row.get("frequency"))
    transformation = str(row.get("transformation"))
    if series_id != cfg["expected_heatmap_series_id"]:
        raise ValueError(f"GBP {dimension} heatmap series ID changed: {series_id!r}")
    if frequency != "M":
        raise ValueError(f"GBP {dimension} frequency changed: {frequency!r}")
    if transformation != cfg["expected_transformation"]:
        raise ValueError(f"GBP {dimension} transformation changed: {transformation!r}")
    return series_id, frequency, transformation


def resolve_macro_series_id(dimension: str) -> str:
    series = load_json(SERIES_PATH)
    rows = series["GBP"]
    expected = str(CONFIG[dimension]["macro_series_id"])
    hits = [r for r in rows if isinstance(r, dict) and str(r.get("id")) == expected]
    if len(hits) != 1:
        raise ValueError(
            f"GBP {dimension} canonical MACRO_SERIES contract drift: "
            f"expected exactly one {expected!r}, got {len(hits)}"
        )
    return expected


def build_api_url(dimension: str) -> str:
    uri = CONFIG[dimension]["uri"]
    return f"{API_BASE}?{urllib.parse.urlencode({'uri': uri})}"


def fetch_payload(dimension: str) -> dict[str, Any]:
    req = urllib.request.Request(build_api_url(dimension), headers={"User-Agent": "global-macro-fx-quant/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if not isinstance(payload, dict):
        raise ValueError("ONS response root is not an object")
    return payload


def build_candidate(dimension: str, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = CONFIG[dimension]
    observations = extract_months(payload)
    latest_period, latest_value = observations[-1]
    prior_period, prior_value = observations[-2]
    heat_series_id, frequency, transformation = resolve_heatmap_contract(dimension)
    macro_series_id = resolve_macro_series_id(dimension)
    candidate = {
        "currency": "GBP",
        "dimension": dimension,
        "macro_series_id": macro_series_id,
        "observation_date": latest_period,
        "value": latest_value,
        "source": SOURCE,
        "source_url": cfg["source_url"],
        "series_id": heat_series_id,
        "frequency": frequency,
        "transformation": transformation,
        "unit": cfg["unit"],
    }
    audit = {
        "upstream_series_id": cfg["series_id"],
        "dataset": cfg["dataset"],
        "ons_uri": cfg["uri"],
        "api_url": build_api_url(dimension),
        "canonical_macro_series_id": macro_series_id,
        "latest_period": latest_period,
        "latest_value": latest_value,
        "prior_period": prior_period,
        "prior_value": prior_value,
        "delta": latest_value - prior_value,
        "candidate_only": True,
        "live_data_written": False,
    }
    return candidate, audit


def main() -> int:
    ap = argparse.ArgumentParser(description="Build GBP core macro candidate from official ONS published time-series API")
    ap.add_argument("--dimension", choices=sorted(CONFIG), required=True)
    ap.add_argument("--fixture", type=Path, help="Read deterministic ONS JSON fixture instead of network")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--audit-output", type=Path)
    args = ap.parse_args()
    if args.fixture:
        payload = load_json(args.fixture)
        mode = "fixture"
    else:
        payload = fetch_payload(args.dimension)
        mode = "live"
    candidate, audit = build_candidate(args.dimension, payload)
    audit["mode"] = mode
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.audit_output:
        args.audit_output.parent.mkdir(parents=True, exist_ok=True)
        args.audit_output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "candidate": candidate, "audit": audit}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
