#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SERIES_PATH = ROOT / "live_data" / "sections" / "MACRO_SERIES.json"
HEATMAP_PATH = ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json"
API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
LABOUR_BLS_SERIES = "LNS14000000"
INFLATION_BLS_SERIES = "CUSR0000SA0"
AUTHORITY = "U.S. Bureau of Labor Statistics"
TRANSPORT = "BLS Public Data API v2"
SOURCE_URL = "https://www.bls.gov/developers/"

CANONICAL_CONTRACT = {
    "labour": {
        "macro_series_id": "US_UNRATE_history_value",
        "heatmap_series_id": "UNRATE",
    },
    "inflation": {
        "macro_series_id": "US_CPIAUCSL_history_value",
        "heatmap_series_id": "CPIAUCSL",
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def month_key(year: str, period: str) -> str:
    if len(period) != 3 or not period.startswith("M") or period == "M13":
        raise ValueError(f"not a monthly BLS period: {period!r}")
    month = int(period[1:])
    if not 1 <= month <= 12:
        raise ValueError(f"invalid BLS month: {period!r}")
    return f"{int(year):04d}-{month:02d}"


def parse_series(payload: dict[str, Any], series_id: str) -> list[tuple[str, float]]:
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError(f"BLS request failed: status={payload.get('status')!r} message={payload.get('message')!r}")
    rows = payload.get("Results", {}).get("series", [])
    hits = [x for x in rows if str(x.get("seriesID")) == series_id]
    if len(hits) != 1:
        raise ValueError(f"expected exactly one BLS series {series_id}, got {len(hits)}")
    obs: dict[str, float] = {}
    for row in hits[0].get("data", []):
        period = str(row.get("period", ""))
        if period == "M13":
            continue
        if not period.startswith("M"):
            continue
        date = month_key(str(row.get("year", "")), period)
        raw = str(row.get("value", "")).strip().replace(",", "")
        if not raw:
            continue
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError(f"non-finite BLS value for {series_id} {date}")
        if date in obs and abs(obs[date] - value) > 1e-12:
            raise ValueError(f"duplicate conflicting BLS value for {series_id} {date}")
        obs[date] = value
    if not obs:
        raise ValueError(f"no monthly observations for {series_id}")
    return sorted(obs.items())


def yoy_from_index(observations: list[tuple[str, float]]) -> list[tuple[str, float]]:
    by_date = dict(observations)
    out: list[tuple[str, float]] = []
    for date, value in observations:
        year, month = map(int, date.split("-"))
        prior = f"{year-1:04d}-{month:02d}"
        if prior not in by_date:
            continue
        base = by_date[prior]
        if base == 0:
            raise ValueError(f"zero CPI base for {date}")
        out.append((date, (value / base - 1.0) * 100.0))
    if not out:
        raise ValueError("insufficient CPI history to calculate YoY; need same month one year earlier")
    return out


def resolve_contract(dimension: str) -> tuple[str, str, str, str, str]:
    if dimension not in CANONICAL_CONTRACT:
        raise ValueError(f"unsupported USD macro dimension: {dimension}")
    heat = load_json(HEATMAP_PATH)
    series = load_json(SERIES_PATH)
    h = heat["currencies"]["USD"][dimension]
    expected = CANONICAL_CONTRACT[dimension]
    heat_series_id = str(h["series_id"])
    if heat_series_id != expected["heatmap_series_id"]:
        raise ValueError(
            f"USD {dimension} heatmap semantic id drift: expected={expected['heatmap_series_id']!r} actual={heat_series_id!r}"
        )
    macro_series_id = expected["macro_series_id"]
    hits = [r for r in series["USD"] if str(r.get("id")) == macro_series_id]
    if len(hits) != 1:
        raise ValueError(
            f"USD {dimension} canonical MACRO_SERIES id drift: expected exactly one {macro_series_id!r}, got {len(hits)}"
        )
    return (
        macro_series_id,
        heat_series_id,
        str(h.get("source", "FRED/BLS")),
        str(h.get("frequency", "M")),
        str(h.get("transformation", "level" if dimension == "labour" else "yoy_pct_from_index")),
    )


def fetch_payload(start_year: int, end_year: int) -> dict[str, Any]:
    body = json.dumps({
        "seriesid": [LABOUR_BLS_SERIES, INFLATION_BLS_SERIES],
        "startyear": str(start_year),
        "endyear": str(end_year),
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "global-macro-fx-quant/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def build(payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    labour = parse_series(payload, LABOUR_BLS_SERIES)
    cpi_index = parse_series(payload, INFLATION_BLS_SERIES)
    cpi_yoy = yoy_from_index(cpi_index)
    if len(labour) < 2:
        raise ValueError("need at least two unemployment observations")

    latest_lab, prior_lab = labour[-1], labour[-2]
    latest_inf = cpi_yoy[-1]
    prior_inf = cpi_yoy[-2] if len(cpi_yoy) >= 2 else None

    lab_macro_id, lab_heat_id, lab_source, lab_freq, lab_transform = resolve_contract("labour")
    inf_macro_id, inf_heat_id, inf_source, inf_freq, inf_transform = resolve_contract("inflation")

    candidates = {
        "labour": {
            "currency": "USD",
            "dimension": "labour",
            "macro_series_id": lab_macro_id,
            "observation_date": latest_lab[0],
            "value": latest_lab[1],
            "source": lab_source,
            "source_url": SOURCE_URL,
            "series_id": lab_heat_id,
            "frequency": lab_freq,
            "transformation": lab_transform,
            "unit": "%",
        },
        "inflation": {
            "currency": "USD",
            "dimension": "inflation",
            "macro_series_id": inf_macro_id,
            "observation_date": latest_inf[0],
            "value": latest_inf[1],
            "source": inf_source,
            "source_url": SOURCE_URL,
            "series_id": inf_heat_id,
            "frequency": inf_freq,
            "transformation": inf_transform,
            "unit": "% YoY",
        },
    }
    audit = {
        "authority": AUTHORITY,
        "transport": TRANSPORT,
        "api_url": API_URL,
        "bls_series": {"labour": LABOUR_BLS_SERIES, "inflation_index": INFLATION_BLS_SERIES},
        "canonical_contract": CANONICAL_CONTRACT,
        "labour": {
            "latest_period": latest_lab[0], "latest_value": latest_lab[1],
            "prior_period": prior_lab[0], "prior_value": prior_lab[1],
        },
        "inflation": {
            "latest_period": latest_inf[0], "latest_value": latest_inf[1],
            "prior_period": prior_inf[0] if prior_inf else None,
            "prior_value": prior_inf[1] if prior_inf else None,
            "calculation": "100 * (CUSR0000SA0_t / CUSR0000SA0_t-12 - 1)",
        },
        "candidate_only": True,
        "live_data_written": False,
        "historical_pit_certified": False,
    }
    return candidates, audit


def main() -> int:
    ap = argparse.ArgumentParser(description="Build USD labour and inflation macro candidates from the official BLS API")
    ap.add_argument("--fixture", type=Path, help="Read deterministic BLS API JSON fixture instead of network")
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--start-year", type=int)
    ap.add_argument("--end-year", type=int)
    args = ap.parse_args()

    if args.fixture:
        payload = load_json(args.fixture)
        mode = "fixture"
    else:
        from datetime import datetime, timezone
        end_year = args.end_year or datetime.now(timezone.utc).year
        start_year = args.start_year or (end_year - 2)
        if end_year - start_year > 9:
            raise SystemExit("unregistered BLS live fetch is intentionally limited to a <=10-year span")
        payload = fetch_payload(start_year, end_year)
        mode = "live"

    candidates, audit = build(payload)
    audit["mode"] = mode
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for dimension, candidate in candidates.items():
        (args.output_dir / f"{dimension}-candidate.json").write_text(
            json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    (args.output_dir / "source-audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "PASS", "mode": mode, "candidates": candidates, "audit": audit}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
