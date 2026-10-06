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
DEFAULT_BLS_SERIES_ID = "LNS14000000"
DEFAULT_API_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data"
SOURCE = "U.S. Bureau of Labor Statistics"
SOURCE_URL = "https://data.bls.gov/timeseries/LNS14000000"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_month(year: str, period: str) -> str:
    if not (period.startswith("M") and len(period) == 3):
        raise ValueError(f"not a monthly BLS period: {period!r}")
    month = int(period[1:])
    if month < 1 or month > 12:
        raise ValueError(f"BLS period outside M01..M12: {period!r}")
    # Canonical MACRO_SERIES uses month-start ISO dates.
    return f"{int(year):04d}-{month:02d}-01"


def extract_observations(payload: dict[str, Any], expected_series_id: str = DEFAULT_BLS_SERIES_ID) -> list[tuple[str, float, list[dict[str, Any]]]]:
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
    obs: dict[str, tuple[float, list[dict[str, Any]]]] = {}
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
        footnotes = row.get("footnotes", []) or []
        if date in obs and abs(obs[date][0] - value) > 1e-12:
            raise ValueError(f"ambiguous BLS observations for {date}")
        obs[date] = (value, footnotes)
    if len(obs) < 2:
        raise ValueError("need at least two monthly BLS unemployment observations")
    return [(date, obs[date][0], obs[date][1]) for date in sorted(obs)]


def resolve_ids() -> tuple[str, str, str, str]:
    series = load_json(SERIES_PATH)
    heat = load_json(HEATMAP_PATH)
    h = heat["currencies"]["USD"]["labour"]
    heat_series_id = str(h["series_id"])
    rows = series["USD"]
    by_id = {str(r.get("id")): r for r in rows if isinstance(r, dict) and r.get("id") is not None}

    candidate_ids = (
        heat_series_id,
        f"US_{heat_series_id}_history_value",
        f"US_{heat_series_id}_history_{heat_series_id}",
        f"USD_{heat_series_id}_history_value",
        f"USD_{heat_series_id}_history_{heat_series_id}",
    )
    convention_hits = [cid for cid in candidate_ids if cid in by_id]
    if len(convention_hits) == 1:
        macro_series_id = convention_hits[0]
    elif len(convention_hits) > 1:
        raise ValueError(f"ambiguous USD unemployment canonical IDs: {convention_hits}")
    else:
        hits = []
        for r in rows:
            text = " ".join(str(r.get(k, "")) for k in ("id", "name", "title", "indicator", "label")).lower()
            if "unemp" in text or "disoccup" in text:
                hits.append(r)
        if len(hits) != 1:
            raise ValueError(
                f"cannot resolve unique USD unemployment MACRO_SERIES row; "
                f"heatmap series_id={heat_series_id!r}; convention_hits={convention_hits}; semantic_hits={len(hits)}"
            )
        macro_series_id = str(hits[0]["id"])

    return macro_series_id, heat_series_id, str(h.get("frequency", "M")), str(h.get("transformation", "level"))


def fetch_payload(series_id: str = DEFAULT_BLS_SERIES_ID) -> dict[str, Any]:
    url = f"{DEFAULT_API_URL}/{series_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "global-macro-fx-quant/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if not isinstance(payload, dict):
        raise ValueError("BLS response root is not an object")
    return payload


def build_candidate(payload: dict[str, Any], upstream_series_id: str = DEFAULT_BLS_SERIES_ID) -> tuple[dict[str, Any], dict[str, Any]]:
    observations = extract_observations(payload, upstream_series_id)
    latest = observations[-1]
    previous = observations[-2]
    macro_series_id, heat_series_id, frequency, transformation = resolve_ids()
    candidate = {
        "currency": "USD",
        "dimension": "labour",
        "macro_series_id": macro_series_id,
        "observation_date": latest[0],
        "value": latest[1],
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "series_id": heat_series_id,
        "frequency": frequency,
        "transformation": transformation,
        "unit": "%",
    }
    audit = {
        "upstream_series_id": upstream_series_id,
        "api_url": f"{DEFAULT_API_URL}/{upstream_series_id}",
        "latest_period": latest[0],
        "latest_value": latest[1],
        "prior_period": previous[0],
        "prior_value": previous[1],
        "delta": round(latest[1] - previous[1], 10),
        "latest_footnotes": latest[2],
        "candidate_only": True,
        "live_data_written": False,
    }
    return candidate, audit


def main() -> int:
    ap = argparse.ArgumentParser(description="Build canonical USD unemployment candidate from official BLS data")
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
