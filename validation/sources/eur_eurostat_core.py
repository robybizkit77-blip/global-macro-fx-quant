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
API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
SOURCE = "Eurostat"

CONFIG: dict[str, dict[str, Any]] = {
    "inflation": {
        "dataset": "prc_hicp_minr",
        "filters": {"freq": "M", "unit": "RCH_A", "coicop": "CP00", "geo": "EA21"},
        "source_url": "https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/default/table?lang=en",
        "expected_heatmap_series_id": "EA_HICP_HEADLINE_YOY",
        "expected_transformation": "reported_yoy_rate",
        "unit": "% YoY",
    },
    "labour": {
        "dataset": "une_rt_m",
        "filters": {"freq": "M", "s_adj": "SA", "age": "TOTAL", "unit": "PC_ACT", "sex": "T", "geo": "EA21"},
        "source_url": "https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table?lang=en",
        "expected_heatmap_series_id": "EA_UNEMP",
        "expected_transformation": "level",
        "unit": "%",
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def category_positions(category: dict[str, Any]) -> dict[str, int]:
    index = category.get("index")
    if isinstance(index, dict):
        return {str(k): int(v) for k, v in index.items()}
    if isinstance(index, list):
        return {str(code): i for i, code in enumerate(index)}
    raise ValueError("JSON-stat category.index must be an object or list")


def linear_index(coords: list[int], sizes: list[int]) -> int:
    if len(coords) != len(sizes):
        raise ValueError("coordinate/size length mismatch")
    idx = 0
    stride = 1
    for pos in range(len(sizes) - 1, -1, -1):
        idx += coords[pos] * stride
        stride *= sizes[pos]
    return idx


def get_value(values: Any, idx: int) -> Any:
    if isinstance(values, list):
        return values[idx] if 0 <= idx < len(values) else None
    if isinstance(values, dict):
        return values.get(str(idx), values.get(idx))
    raise ValueError("JSON-stat value must be list or object")


def extract_series(payload: dict[str, Any], expected_filters: dict[str, str]) -> list[tuple[str, float]]:
    if payload.get("class") not in (None, "dataset"):
        raise ValueError(f"unexpected JSON-stat class: {payload.get('class')!r}")
    ids = payload.get("id")
    sizes = payload.get("size")
    dims = payload.get("dimension")
    values = payload.get("value")
    if not isinstance(ids, list) or not isinstance(sizes, list) or not isinstance(dims, dict):
        raise ValueError("invalid JSON-stat dataset structure")
    ids = [str(x) for x in ids]
    sizes = [int(x) for x in sizes]
    if len(ids) != len(sizes):
        raise ValueError("JSON-stat id/size mismatch")
    if "time" not in ids:
        raise ValueError("JSON-stat response has no time dimension")

    selected_positions: dict[str, int] = {}
    for dim_code, expected_code in expected_filters.items():
        if dim_code not in ids:
            raise ValueError(f"missing expected Eurostat dimension {dim_code!r}")
        d = dims.get(dim_code)
        if not isinstance(d, dict):
            raise ValueError(f"invalid dimension object for {dim_code!r}")
        positions = category_positions(d.get("category", {}))
        if expected_code not in positions:
            raise ValueError(
                f"Eurostat response does not contain expected {dim_code}={expected_code}; "
                f"available={list(positions)[:20]}"
            )
        if len(positions) != 1:
            raise ValueError(f"filtered dimension {dim_code!r} is not singleton: {list(positions)}")
        selected_positions[dim_code] = positions[expected_code]

    time_dim = dims.get("time")
    if not isinstance(time_dim, dict):
        raise ValueError("invalid time dimension")
    time_positions = category_positions(time_dim.get("category", {}))
    if not time_positions:
        raise ValueError("Eurostat response contains no time observations")

    out: list[tuple[str, float]] = []
    time_axis = ids.index("time")
    for period, tpos in sorted(time_positions.items(), key=lambda item: item[1]):
        if len(period) != 7 or period[4] != "-":
            continue
        coords = [0] * len(ids)
        for dim_code, pos in selected_positions.items():
            coords[ids.index(dim_code)] = pos
        coords[time_axis] = tpos
        raw = get_value(values, linear_index(coords, sizes))
        if raw is None:
            continue
        value = float(raw)
        out.append((period, value))
    if len(out) < 2:
        raise ValueError(f"need at least two monthly Eurostat observations; got {len(out)}")
    return out


def resolve_macro_series_id(dimension: str, heat_series_id: str) -> str:
    series = load_json(SERIES_PATH)
    rows = series["EUR"]
    by_id = {str(r.get("id")): r for r in rows if isinstance(r, dict) and r.get("id") is not None}
    candidates = [
        heat_series_id,
        f"EA_{heat_series_id}_history_value",
        f"EU_{heat_series_id}_history_value",
        f"EUR_{heat_series_id}_history_value",
    ]
    if dimension == "inflation":
        candidates += ["EA_HICP_HEADLINE_YOY_history_value", "EA_HICP_YoY_history_value"]
    else:
        candidates += ["EA_UNEMP_history_value", "EA_UNRATE_history_value"]
    hits = [cid for cid in dict.fromkeys(candidates) if cid in by_id]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        raise ValueError(f"ambiguous EUR {dimension} canonical IDs: {hits}")

    semantic: list[dict[str, Any]] = []
    for row in rows:
        text = " ".join(str(row.get(k, "")) for k in ("id", "label", "name", "title", "indicator")).lower()
        if dimension == "inflation" and ("hicp" in text or "infl" in text):
            semantic.append(row)
        elif dimension == "labour" and ("unemp" in text or "disoccup" in text):
            semantic.append(row)
    if len(semantic) != 1:
        raise ValueError(
            f"cannot resolve unique EUR {dimension} MACRO_SERIES row; "
            f"heatmap series_id={heat_series_id!r}; semantic_hits={len(semantic)}"
        )
    return str(semantic[0]["id"])


def resolve_heatmap_contract(dimension: str) -> tuple[str, str, str]:
    heat = load_json(HEATMAP_PATH)
    row = heat["currencies"]["EUR"][dimension]
    cfg = CONFIG[dimension]
    series_id = str(row.get("series_id"))
    frequency = str(row.get("frequency"))
    transformation = str(row.get("transformation"))
    if series_id != cfg["expected_heatmap_series_id"]:
        raise ValueError(f"EUR {dimension} heatmap series ID changed: {series_id!r}")
    if frequency != "M":
        raise ValueError(f"EUR {dimension} frequency changed: {frequency!r}")
    if transformation != cfg["expected_transformation"]:
        raise ValueError(f"EUR {dimension} transformation changed: {transformation!r}")
    return series_id, frequency, transformation


def build_api_url(dimension: str) -> str:
    cfg = CONFIG[dimension]
    query = {"lang": "en", **cfg["filters"]}
    return f"{API_BASE}/{cfg['dataset']}?{urllib.parse.urlencode(query)}"


def fetch_payload(dimension: str) -> dict[str, Any]:
    url = build_api_url(dimension)
    req = urllib.request.Request(url, headers={"User-Agent": "global-macro-fx-quant/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if not isinstance(payload, dict):
        raise ValueError("Eurostat response root is not an object")
    return payload


def build_candidate(dimension: str, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = CONFIG[dimension]
    observations = extract_series(payload, cfg["filters"])
    latest_period, latest_value = observations[-1]
    prior_period, prior_value = observations[-2]
    heat_series_id, frequency, transformation = resolve_heatmap_contract(dimension)
    macro_series_id = resolve_macro_series_id(dimension, heat_series_id)

    candidate = {
        "currency": "EUR",
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
        "dataset": cfg["dataset"],
        "filters": cfg["filters"],
        "api_url": build_api_url(dimension),
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
    ap = argparse.ArgumentParser(description="Build EUR core macro candidate from official Eurostat JSON-stat API")
    ap.add_argument("--dimension", choices=sorted(CONFIG), required=True)
    ap.add_argument("--fixture", type=Path, help="Read deterministic JSON-stat fixture instead of network")
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
