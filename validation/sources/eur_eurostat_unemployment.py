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
DATASET = "une_rt_m"
SOURCE = "Eurostat"
SOURCE_URL = "https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table?lang=en"
API_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_m"


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
    if payload.get("class") not in ("dataset", None):
        raise ValueError(f"unexpected JSON-stat class: {payload.get('class')!r}")
    dims = payload.get("dimension", {})
    time_dim = dims.get("time", {})
    category = time_dim.get("category", {})
    periods = ordered_category_keys(category)
    raw_values = payload.get("value")
    if isinstance(raw_values, list):
        vals = raw_values
    elif isinstance(raw_values, dict):
        vals = [None] * len(periods)
        for k, v in raw_values.items():
            vals[int(k)] = v
    else:
        raise ValueError("Eurostat response has no JSON-stat value array")
    if len(vals) != len(periods):
        raise ValueError(f"Eurostat time/value length mismatch: {len(periods)} != {len(vals)}")
    out: list[tuple[str, float]] = []
    for period, value in zip(periods, vals):
        if value is None:
            continue
        out.append((period, float(value)))
    if len(out) < 2:
        raise ValueError("need at least two Eurostat monthly observations")
    return out


def resolve_ids() -> tuple[str, str, str, str]:
    series = load_json(SERIES_PATH)
    heat = load_json(HEATMAP_PATH)
    h = heat["currencies"]["EUR"]["labour"]
    heat_series_id = str(h["series_id"])
    rows = series["EUR"]
    exact = [r for r in rows if str(r.get("id")) == heat_series_id]
    if len(exact) != 1:
        hits = []
        for r in rows:
            text = " ".join(str(r.get(k, "")) for k in ("id", "name", "title", "indicator", "label")).lower()
            if "unemp" in text or "disoccup" in text:
                hits.append(r)
        if len(hits) != 1:
            raise ValueError(f"cannot resolve unique EUR unemployment MACRO_SERIES row; heatmap series_id={heat_series_id!r}")
        macro_series_id = str(hits[0]["id"])
    else:
        macro_series_id = str(exact[0]["id"])
    return macro_series_id, heat_series_id, str(h.get("frequency", "M")), str(h.get("transformation", "level"))


def fetch_payload(geo: str = "EA21") -> dict[str, Any]:
    params = {
        "lang": "en",
        "freq": "M",
        "s_adj": "SA",
        "unit": "PC_ACT",
        "age": "TOTAL",
        "sex": "T",
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
    observations = extract_observations(payload)
    latest = observations[-1]
    previous = observations[-2]
    macro_series_id, heat_series_id, frequency, transformation = resolve_ids()
    candidate = {
        "currency": "EUR",
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
        "mode": "live",
        "dataset": DATASET,
        "geo": geo,
        "filters": {"freq": "M", "s_adj": "SA", "unit": "PC_ACT", "age": "TOTAL", "sex": "T"},
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
    ap = argparse.ArgumentParser(description="Build canonical EUR unemployment candidate from Eurostat")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--audit-output", type=Path)
    ap.add_argument("--geo", default="EA21")
    args = ap.parse_args()

    payload = fetch_payload(args.geo)
    candidate, audit = build_candidate(payload, args.geo)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.audit_output:
        args.audit_output.parent.mkdir(parents=True, exist_ok=True)
        args.audit_output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "candidate": candidate, "audit": audit}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
