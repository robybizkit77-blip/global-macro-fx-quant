#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SERIES_PATH = ROOT / "live_data" / "sections" / "MACRO_SERIES.json"
HEATMAP_PATH = ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json"
DEFAULT_STATS_DATA_ID = "0002060004"
DEFAULT_API_URL = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
SOURCE = "Statistics Bureau of Japan / e-Stat"
SOURCE_URL = "https://www.stat.go.jp/english/data/roudou/results/month/index.html"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def class_maps(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    stat = payload["GET_STATS_DATA"]["STATISTICAL_DATA"]
    objs = stat.get("CLASS_INF", {}).get("CLASS_OBJ", [])
    if isinstance(objs, dict):
        objs = [objs]
    out: dict[str, dict[str, str]] = {}
    for obj in objs:
        dim = str(obj.get("@id", ""))
        classes = obj.get("CLASS", [])
        if isinstance(classes, dict):
            classes = [classes]
        out[dim] = {str(x.get("@code", "")): str(x.get("@name", "")) for x in classes}
    return out


def values(payload: dict[str, Any]) -> list[dict[str, Any]]:
    vals = payload["GET_STATS_DATA"]["STATISTICAL_DATA"].get("DATA_INF", {}).get("VALUE", [])
    if isinstance(vals, dict):
        vals = [vals]
    return vals


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def labelled_value(v: dict[str, Any], maps: dict[str, dict[str, str]]) -> str:
    labels: list[str] = []
    for k, code in v.items():
        if not k.startswith("@"):
            continue
        dim = k[1:]
        label = maps.get(dim, {}).get(str(code))
        if label:
            labels.append(label)
    return norm(" | ".join(labels))


def score_semantics(label: str) -> int:
    target = (
        "unemployment rate" in label
        or "unemployed rate" in label
        or ("rate" in label and "unemployed person" in label)
    )
    if not target:
        return -10_000
    score = 100
    positives = (
        ("both sexes", 20), ("total", 8), ("all japan", 15), ("japan", 5),
        ("15 years old or more", 20), ("15 years and over", 20),
        ("seasonally adjusted", 30),
    )
    negatives = (
        ("male", -8), ("female", -8), ("excluding", -5),
        ("original series", -15), ("not seasonally adjusted", -20),
    )
    for token, points in positives + negatives:
        if token in label:
            score += points
    return score


def parse_period(label: str, code: str) -> str:
    text = f"{label} {code}"
    m = re.search(r"(?P<year>(?:19|20)\d{2})[-/ ](?P<month>0?[1-9]|1[0-2])\b", text)
    if m:
        return f"{int(m.group('year')):04d}-{int(m.group('month')):02d}"
    m = re.search(r"\b((?:19|20)\d{2})(0[1-9]|1[0-2])\b", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    months = {m.lower(): i for i, m in enumerate(
        ["January","February","March","April","May","June","July","August","September","October","November","December"], 1)}
    months.update({k[:3]: v for k, v in list(months.items())})
    lower = text.lower().replace(".", "")
    y = re.search(r"\b((?:19|20)\d{2})\b", lower)
    if y:
        for name, month in months.items():
            if re.search(rf"\b{re.escape(name)}\b", lower):
                return f"{int(y.group(1)):04d}-{month:02d}"
    raise ValueError(f"cannot parse monthly period from time label/code: {label!r} / {code!r}")


def is_official_unemployment_rate_row(v: dict[str, Any], maps: dict[str, dict[str, str]]) -> bool:
    required_codes = {
        "@tab": "02",
        "@cat01": "000",
        "@cat02": "0",
        "@cat03": "08",
        "@cat04": "00",
        "@area": "00000",
    }
    if all(str(v.get(k, "")) == code for k, code in required_codes.items()):
        return str(v.get("@unit", "%")) == "%"
    label = labelled_value(v, maps)
    return score_semantics(label) > 0


def extract_observations(payload: dict[str, Any]) -> list[tuple[str, float, str]]:
    maps = class_maps(payload)
    selected: list[tuple[dict[str, Any], str]] = []
    for v in values(payload):
        if is_official_unemployment_rate_row(v, maps):
            selected.append((v, labelled_value(v, maps)))
    if not selected:
        raise ValueError("no e-Stat values matched official Japan unemployment-rate dimensions")

    obs: dict[str, tuple[float, str]] = {}
    for v, label in selected:
        raw = v.get("$")
        if raw in (None, "", "***", "-"):
            continue
        time_code = str(v.get("@time", ""))
        time_label = maps.get("time", {}).get(time_code, time_code)
        period = parse_period(time_label, time_code)
        value = float(str(raw).replace(",", ""))
        if period in obs and abs(obs[period][0] - value) > 1e-12:
            raise ValueError(f"ambiguous selected e-Stat values for {period}")
        obs[period] = (value, label)
    if len(obs) < 2:
        raise ValueError("need at least two monthly unemployment observations")
    return [(p, obs[p][0], obs[p][1]) for p in sorted(obs)]


def resolve_ids() -> tuple[str, str, str, str]:
    series = load_json(SERIES_PATH)
    heat = load_json(HEATMAP_PATH)
    h = heat["currencies"]["JPY"]["labour"]
    heat_series_id = str(h["series_id"])
    rows = series["JPY"]
    exact = [r for r in rows if str(r.get("id")) == heat_series_id]
    if len(exact) != 1:
        hits = []
        for r in rows:
            text = " ".join(str(r.get(k, "")) for k in ("id", "name", "title", "indicator", "label")).lower()
            if "unemp" in text:
                hits.append(r)
        if len(hits) != 1:
            raise ValueError(f"cannot resolve unique JPY unemployment MACRO_SERIES row; heatmap series_id={heat_series_id!r}")
        macro_series_id = str(hits[0]["id"])
    else:
        macro_series_id = str(exact[0]["id"])
    return macro_series_id, heat_series_id, str(h.get("frequency", "M")), str(h.get("transformation", "level"))


def fetch_payload(app_id: str, stats_data_id: str) -> dict[str, Any]:
    params = urllib.parse.urlencode({
        "appId": app_id,
        "statsDataId": stats_data_id,
        "metaGetFlg": "Y",
        "cntGetFlg": "N",
        "lang": "E",
        "limit": 100000,
    })
    req = urllib.request.Request(f"{DEFAULT_API_URL}?{params}", headers={"User-Agent": "global-macro-fx-quant/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    result = payload.get("GET_STATS_DATA", {}).get("RESULT", {})
    status = str(result.get("STATUS", "0"))
    if status not in ("0", "000"):
        raise ValueError(f"e-Stat API error: status={status} error={result.get('ERROR_MSG')}")
    return payload


def build_candidate(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    observations = extract_observations(payload)
    latest = observations[-1]
    previous = observations[-2]
    macro_series_id, heat_series_id, frequency, transformation = resolve_ids()
    candidate = {
        "currency": "JPY",
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
        "stats_data_id": DEFAULT_STATS_DATA_ID,
        "latest_period": latest[0],
        "latest_value": latest[1],
        "prior_period": previous[0],
        "prior_value": previous[1],
        "delta": round(latest[1] - previous[1], 10),
        "matched_semantics": latest[2],
        "candidate_only": True,
        "live_data_written": False,
    }
    return candidate, audit


def main() -> int:
    ap = argparse.ArgumentParser(description="Build canonical JPY unemployment candidate from Statistics Bureau/e-Stat data")
    ap.add_argument("--fixture", type=Path, help="Read deterministic e-Stat JSON fixture instead of network")
    ap.add_argument("--output", type=Path, required=True, help="Candidate JSON output path")
    ap.add_argument("--audit-output", type=Path, help="Optional extraction audit JSON output")
    ap.add_argument("--stats-data-id", default=DEFAULT_STATS_DATA_ID)
    args = ap.parse_args()

    if args.fixture:
        payload = load_json(args.fixture)
        mode = "fixture"
    else:
        app_id = os.environ.get("E_STAT_APP_ID", "").strip()
        if not app_id:
            raise SystemExit("E_STAT_APP_ID is required for live e-Stat fetch; no credential is stored in the repository")
        payload = fetch_payload(app_id, args.stats_data_id)
        mode = "live"

    candidate, audit = build_candidate(payload)
    audit["mode"] = mode
    audit["stats_data_id"] = args.stats_data_id
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.audit_output:
        args.audit_output.parent.mkdir(parents=True, exist_ok=True)
        args.audit_output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "candidate": candidate, "audit": audit}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
