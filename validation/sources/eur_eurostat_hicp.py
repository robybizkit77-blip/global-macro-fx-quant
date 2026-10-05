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
DATASET = "prc_hicp_minr"
SOURCE = "Eurostat"
SOURCE_URL = "https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/default/table?lang=en"
API_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_minr"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def ordered_category_keys(category: dict[str, Any]) -> list[str]:
    idx = category.get("index", {})
    if isinstance(idx, dict):
        return [k for k, _ in sorted(idx.items(), key=lambda kv: int(kv[1]))]
    if isinstance(idx, list):
        return [str(x) for x in idx]
    raise ValueError("unsupported JSON-stat category.index structure")


def extract_observations(payload: dict[str, Any]) -> list[tuple[str, float]]:
    category = payload.get("dimension", {}).get("time", {}).get("category", {})
    periods = ordered_category_keys(category)
    raw = payload.get("value")
    if isinstance(raw, list):
        values = raw
    elif isinstance(raw, dict):
        values = [None] * len(periods)
        for k, v in raw.items():
            values[int(k)] = v
    else:
        raise ValueError("Eurostat response has no JSON-stat value array")
    if len(values) != len(periods):
        raise ValueError("Eurostat time/value length mismatch")
    out = [(period, float(value)) for period, value in zip(periods, values) if value is not None]
    if len(out) < 2:
        raise ValueError("need at least two HICP observations")
    return out


def resolve_ids() -> tuple[str, str, str, str]:
    series = load_json(SERIES_PATH)
    heat = load_json(HEATMAP_PATH)
    h = heat["currencies"]["EUR"]["inflation"]
    heat_series_id = str(h["series_id"])
    rows = series["EUR"]
    hits = [r for r in rows if heat_series_id.lower() in str(r.get("id", "")).lower()]
    if len(hits) != 1:
        hits = [r for r in rows if str(r.get("id")) == "EA_HICP_HEADLINE_YOY_history_value"]
    if len(hits) != 1:
        raise ValueError(f"cannot resolve unique EUR HICP history row; heatmap series_id={heat_series_id!r}")
    return str(hits[0]["id"]), heat_series_id, str(h.get("frequency", "M")), str(h.get("transformation", "reported_yoy_rate"))


def fetch_payload(geo: str = "EA21") -> dict[str, Any]:
    params = {
        "lang": "en",
        "freq": "M",
        "unit": "RCH_A",
        "coicop18": "TOTAL",
        "geo": geo,
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "global-macro-fx-quant/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "error" in payload:
        raise ValueError(f"Eurostat API error: {payload['error']}")
    return payload


def build_candidate(payload: dict[str, Any], geo: str) -> tuple[dict[str, Any], dict[str, Any]]:
    obs = extract_observations(payload)
    latest, previous = obs[-1], obs[-2]
    macro_series_id, heat_series_id, frequency, transformation = resolve_ids()
    candidate = {
        "currency": "EUR",
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
        "mode": "live",
        "dataset": DATASET,
        "geo": geo,
        "filters": {"freq": "M", "unit": "RCH_A", "coicop18": "TOTAL"},
        "latest_period": latest[0],
        "latest_value": latest[1],
        "prior_period": previous[0],
        "prior_value": previous[1],
        "delta": round(latest[1] - previous[1], 10),
        "candidate_only": True,
        "live_data_written": False,
    }
    return candidate, audit


def main() -> int:
    ap = argparse.ArgumentParser(description="Build canonical EUR headline HICP YoY candidate from Eurostat")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--audit-output", type=Path)
    ap.add_argument("--geo", default="EA21")
    args = ap.parse_args()
    candidate, audit = build_candidate(fetch_payload(args.geo), args.geo)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.audit_output:
        args.audit_output.parent.mkdir(parents=True, exist_ok=True)
        args.audit_output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "candidate": candidate, "audit": audit}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
