#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SERIES_PATH = ROOT / "live_data" / "sections" / "MACRO_SERIES.json"
HEATMAP_PATH = ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json"
DEFAULT_BLS_SERIES_ID = "CUSR0000SA0"
DEFAULT_API_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data"
SOURCE = "U.S. Bureau of Labor Statistics"
SOURCE_URL = "https://data.bls.gov/timeseries/CUSR0000SA0"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_month(year: str, period: str) -> str:
    if not (period.startswith("M") and len(period) == 3 and period[1:].isdigit()):
        raise ValueError(f"not a monthly BLS period: {period!r}")
    month = int(period[1:])
    if not 1 <= month <= 12:
        raise ValueError(f"BLS period outside M01..M12: {period!r}")
    return f"{int(year):04d}-{month:02d}-01"


def extract_index(payload: dict[str, Any], expected_series_id: str = DEFAULT_BLS_SERIES_ID) -> list[tuple[str, float]]:
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError(f"BLS API request failed: status={payload.get('status')} message={payload.get('message')}")
    series = payload.get("Results", {}).get("series", [])
    if not isinstance(series, list):
        raise ValueError("BLS Results.series is not a list")
    hits = [row for row in series if str(row.get("seriesID")) == expected_series_id]
    if len(hits) != 1:
        raise ValueError(f"expected exactly one BLS series {expected_series_id}; got {len(hits)}")
    data = hits[0].get("data", [])
    if not isinstance(data, list):
        raise ValueError("BLS series data is not a list")

    obs: dict[str, float] = {}
    for row in data:
        period = str(row.get("period", ""))
        if not (period.startswith("M") and len(period) == 3 and period[1:].isdigit()):
            continue
        month = int(period[1:])
        if not 1 <= month <= 12:
            continue
        raw = row.get("value")
        if raw in (None, "", "-", "***"):
            continue
        date = parse_month(str(row.get("year", "")), period)
        value = float(str(raw).replace(",", ""))
        if value <= 0:
            raise ValueError(f"non-positive CPI index for {date}: {value}")
        if date in obs and abs(obs[date] - value) > 1e-12:
            raise ValueError(f"ambiguous BLS CPI observations for {date}")
        obs[date] = value
    if len(obs) < 13:
        raise ValueError("need at least 13 monthly BLS CPI index observations for YoY transformation")
    return [(date, obs[date]) for date in sorted(obs)]


def to_yoy(index_obs: list[tuple[str, float]]) -> list[tuple[str, float, float, float]]:
    by_date = dict(index_obs)
    out: list[tuple[str, float, float, float]] = []
    for date, latest_index in index_obs:
        year = int(date[:4])
        month = int(date[5:7])
        prior_date = f"{year - 1:04d}-{month:02d}-01"
        prior_index = by_date.get(prior_date)
        if prior_index is None:
            continue
        yoy = (latest_index / prior_index - 1.0) * 100.0
        out.append((date, yoy, latest_index, prior_index))
    if not out:
        raise ValueError("could not form any 12-month CPI comparisons")
    return out


def resolve_ids() -> tuple[str, str, str, str]:
    series = load_json(SERIES_PATH)
    heat = load_json(HEATMAP_PATH)
    h = heat["currencies"]["USD"]["inflation"]
    heat_series_id = str(h["series_id"])
    rows = series["USD"]
    by_id = {str(r.get("id")): r for r in rows if isinstance(r, dict) and r.get("id") is not None}

    candidate_ids = (
        heat_series_id,
        f"US_{heat_series_id}_history_value",
        f"US_{heat_series_id}_history_{heat_series_id}",
        f"USD_{heat_series_id}_history_value",
        f"USD_{heat_series_id}_history_{heat_series_id}",
        "US_CPI_YoY_history_value",
    )
    hits = [cid for cid in candidate_ids if cid in by_id]
    if len(hits) == 1:
        macro_series_id = hits[0]
    elif len(hits) > 1:
        raise ValueError(f"ambiguous USD CPI canonical IDs: {hits}")
    else:
        semantic = []
        for row in rows:
            text = " ".join(str(row.get(k, "")) for k in ("id", "name", "title", "indicator", "label")).lower()
            if "cpi" in text and ("yoy" in text or "infl" in text):
                semantic.append(row)
        if len(semantic) != 1:
            raise ValueError(
                f"cannot resolve unique USD CPI MACRO_SERIES row; heatmap series_id={heat_series_id!r}; "
                f"convention_hits={hits}; semantic_hits={len(semantic)}"
            )
        macro_series_id = str(semantic[0]["id"])

    return macro_series_id, heat_series_id, str(h.get("frequency", "M")), str(h.get("transformation", ""))


def fetch_payload(series_id: str = DEFAULT_BLS_SERIES_ID) -> dict[str, Any]:
    url = f"{DEFAULT_API_URL}/{series_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "global-macro-fx-quant/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if not isinstance(payload, dict):
        raise ValueError("BLS response root is not an object")
    return payload


def build_candidate(payload: dict[str, Any], upstream_series_id: str = DEFAULT_BLS_SERIES_ID) -> tuple[dict[str, Any], dict[str, Any]]:
    index_obs = extract_index(payload, upstream_series_id)
    yoy_obs = to_yoy(index_obs)
    latest = yoy_obs[-1]
    previous = yoy_obs[-2] if len(yoy_obs) >= 2 else None
    macro_series_id, heat_series_id, frequency, transformation = resolve_ids()
    if transformation != "yoy_pct_from_index":
        raise ValueError(f"USD inflation heatmap transformation changed unexpectedly: {transformation!r}")

    candidate = {
        "currency": "USD",
        "dimension": "inflation",
        "macro_series_id": macro_series_id,
        "observation_date": latest[0],
        "value": latest[1],
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "series_id": heat_series_id,
        "frequency": frequency,
        "transformation": transformation,
        "unit": "% YoY",
    }
    audit = {
        "upstream_series_id": upstream_series_id,
        "api_url": f"{DEFAULT_API_URL}/{upstream_series_id}",
        "latest_period": latest[0],
        "latest_yoy": latest[1],
        "latest_index": latest[2],
        "year_ago_index": latest[3],
        "prior_yoy_period": previous[0] if previous else None,
        "prior_yoy": previous[1] if previous else None,
        "delta_yoy": round(latest[1] - previous[1], 10) if previous else None,
        "candidate_only": True,
        "live_data_written": False,
    }
    return candidate, audit


def main() -> int:
    ap = argparse.ArgumentParser(description="Build canonical USD CPI YoY candidate from official BLS CPI-U SA index")
    ap.add_argument("--fixture", type=Path, help="Read deterministic BLS JSON fixture instead of network")
    ap.add_argument("--output", type=Path, required=True, help="Candidate JSON output path")
    ap.add_argument("--audit-output", type=Path, help="Optional extraction audit JSON output")
    ap.add_argument("--series-id", default=DEFAULT_BLS_SERIES_ID)
    args = ap.parse_args()

    if args.fixture:
        payload = load_json(args.fixture)
        mode = "fixture"
    else:
        payload = fetch_payload(args.series_id)
        mode = "live"

    candidate, audit = build_candidate(payload, args.series_id)
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
