#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import math
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERIES_PATH = ROOT / "live_data" / "sections" / "MACRO_SERIES.json"
HEATMAP_PATH = ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json"
CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
DIMENSIONS = ("inflation", "labour")


def load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: pathlib.Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def percentile(history: list[float], value: float) -> float:
    if not history:
        raise ValueError("empty history")
    below = sum(1 for x in history if x < value)
    equal = sum(1 for x in history if x == value)
    return round(100.0 * (below + 0.5 * equal) / len(history), 1)


def temperature_label(pct: float, thresholds: list[dict[str, Any]]) -> str:
    for row in thresholds:
        lo, hi = float(row["min"]), float(row["max"])
        if lo <= pct < hi or (pct == 100.0 and hi == 100.0):
            return str(row["label"])
    raise ValueError(f"percentile outside configured thresholds: {pct}")


def direction(values: list[float]) -> str:
    if len(values) < 2:
        return "STABILE"
    d = values[-1] - values[-2]
    eps = 1e-12
    return "SALE" if d > eps else "SCENDE" if d < -eps else "STABILE"


def acceleration(values: list[float]) -> str:
    if len(values) < 3:
        return "STABILE"
    d1 = values[-2] - values[-3]
    d2 = values[-1] - values[-2]
    eps = 1e-12
    if abs(d2) <= eps and abs(d1) <= eps:
        return "STABILE"
    if abs(d2) > abs(d1) + eps:
        return "ACCELERA"
    if abs(d2) + eps < abs(d1):
        return "RALLENTA"
    return "STABILE"


def validate_roots(series: Any, heatmap: Any) -> None:
    if not isinstance(series, dict):
        raise ValueError("MACRO_SERIES root must be an object")
    missing = [c for c in CURRENCIES if c not in series or not isinstance(series[c], list)]
    if missing:
        raise ValueError(f"MACRO_SERIES missing currency arrays: {missing}")
    if heatmap.get("schema_version") != "GMFQ_MACRO_HEATMAP_V1":
        raise ValueError("unexpected heatmap schema")
    currencies = heatmap.get("currencies")
    if not isinstance(currencies, dict):
        raise ValueError("heatmap currencies missing")
    for c in CURRENCIES:
        row = currencies.get(c)
        if not isinstance(row, dict):
            raise ValueError(f"heatmap missing {c}")
        for d in DIMENSIONS:
            if not isinstance(row.get(d), dict):
                raise ValueError(f"heatmap missing {c}.{d}")


def find_series(rows: list[dict[str, Any]], series_id: str) -> dict[str, Any]:
    hits = [x for x in rows if isinstance(x, dict) and x.get("id") == series_id]
    if len(hits) != 1:
        raise ValueError(f"macro_series_id must match exactly one series; got {len(hits)} for {series_id}")
    return hits[0]


def normalize_candidate(c: dict[str, Any]) -> dict[str, Any]:
    required = (
        "currency", "dimension", "macro_series_id", "observation_date", "value",
        "source", "series_id", "frequency", "transformation"
    )
    missing = [k for k in required if k not in c]
    if missing:
        raise ValueError(f"candidate missing fields: {missing}")
    if c["currency"] not in CURRENCIES:
        raise ValueError("unsupported currency")
    if c["dimension"] not in DIMENSIONS:
        raise ValueError("dimension must be inflation or labour")
    if not isinstance(c["observation_date"], str) or len(c["observation_date"]) < 7:
        raise ValueError("observation_date must be YYYY-MM or YYYY-MM-DD")
    value = float(c["value"])
    if not math.isfinite(value):
        raise ValueError("value must be finite")
    out = dict(c)
    out["value"] = value
    return out


def apply_candidate(series: dict[str, Any], heatmap: dict[str, Any], cand: dict[str, Any]) -> dict[str, Any]:
    c = normalize_candidate(cand)
    currency = c["currency"]
    dimension = c["dimension"]
    obs_date = c["observation_date"]
    value = c["value"]

    series_row = find_series(series[currency], c["macro_series_id"])
    dates = series_row.get("dates")
    values = series_row.get("values")
    if not isinstance(dates, list) or not isinstance(values, list) or len(dates) != len(values):
        raise ValueError("target MACRO_SERIES entry has invalid dates/values")

    if obs_date in dates:
        idx = dates.index(obs_date)
        old_value = float(values[idx])
        if idx != len(dates) - 1 and not c.get("allow_historical_revision", False):
            raise ValueError("historical revision blocked unless allow_historical_revision=true")
        values[idx] = value
        action = "REPLACE_EXISTING"
    else:
        if dates and obs_date < str(dates[-1]):
            raise ValueError("out-of-order observation blocked")
        old_value = None
        dates.append(obs_date)
        values.append(value)
        action = "APPEND_NEW"

    series_row["last_date"] = dates[-1]
    series_row["last_value"] = values[-1]
    if c.get("unit") is not None:
        series_row["unit"] = c["unit"]
    series_row["frequency"] = c["frequency"]

    hrow = heatmap["currencies"][currency][dimension]
    if str(hrow.get("series_id")) != str(c["series_id"]) and not c.get("allow_series_id_change", False):
        raise ValueError(
            f"heatmap series_id mismatch: current={hrow.get('series_id')} candidate={c['series_id']}"
        )
    hrow["series_id"] = c["series_id"]
    hrow["source"] = c["source"]
    hrow["frequency"] = c["frequency"]
    hrow["transformation"] = c["transformation"]
    hrow["latest_value"] = value
    hrow["as_of"] = obs_date

    hist = hrow.get("history")
    if not isinstance(hist, list):
        raise ValueError("heatmap history missing")
    hist_values = [float(x) for x in hist]
    detail_key = "unemployment" if dimension == "labour" else "inflation"
    previous_as_of = heatmap["currencies"][currency].get("as_of_detail", {}).get(detail_key)
    if previous_as_of == obs_date and hist_values:
        hist_values[-1] = value
    else:
        hist_values.append(value)
    preferred_months = int(heatmap.get("lookback_rule", {}).get("preferred_years", 10)) * 12
    if preferred_months > 0 and len(hist_values) > preferred_months:
        hist_values = hist_values[-preferred_months:]
    hrow["history"] = hist_values

    pct = percentile(hist_values, value)
    hrow["percentile"] = pct
    hrow["temperature_score"] = pct
    hrow["temperature_label"] = temperature_label(pct, heatmap["thresholds"])
    hrow["direction"] = direction(hist_values)
    hrow["acceleration"] = acceleration(hist_values)
    hrow["validation"] = {
        "source": True,
        "history": len(hist_values) >= int(heatmap.get("lookback_rule", {}).get("minimum_observations", 24)),
        "latest": True,
        "transformation": True,
    }
    heatmap["currencies"][currency].setdefault("as_of_detail", {})[detail_key] = obs_date

    return {
        "currency": currency,
        "dimension": dimension,
        "macro_series_id": c["macro_series_id"],
        "observation_date": obs_date,
        "old_value": old_value,
        "new_value": value,
        "series_action": action,
        "history_observations": len(hist_values),
        "percentile": pct,
        "temperature_label": hrow["temperature_label"],
        "direction": hrow["direction"],
        "acceleration": hrow["acceleration"],
    }


def synthetic_functional_test() -> dict[str, Any]:
    series = {c: [{"id": f"{c}_TEST", "dates": ["2026-01"], "values": [1.0], "last_date": "2026-01", "last_value": 1.0}] for c in CURRENCIES}
    heatmap = {
        "schema_version": "GMFQ_MACRO_HEATMAP_V1",
        "lookback_rule": {"preferred_years": 10, "minimum_observations": 2},
        "thresholds": [
            {"min": 0, "max": 20, "label": "MOLTO_FREDDO"},
            {"min": 20, "max": 40, "label": "FREDDO"},
            {"min": 40, "max": 60, "label": "NORMALE"},
            {"min": 60, "max": 80, "label": "CALDO"},
            {"min": 80, "max": 100, "label": "MOLTO_CALDO"},
        ],
        "currencies": {
            c: {
                "inflation": {"series_id": f"{c}_INF", "history": [1.0, 2.0], "as_of": "2026-01"},
                "labour": {"series_id": f"{c}_LAB", "history": [4.0, 4.1], "as_of": "2026-01"},
                "as_of_detail": {"inflation": "2026-01", "unemployment": "2026-01"},
            }
            for c in CURRENCIES
        },
    }
    validate_roots(series, heatmap)
    candidate = {
        "currency": "JPY", "dimension": "labour", "macro_series_id": "JPY_TEST",
        "observation_date": "2026-02", "value": 4.3, "source": "SELF_TEST",
        "series_id": "JPY_LAB", "frequency": "M", "transformation": "level"
    }
    result = apply_candidate(series, heatmap, candidate)
    if series["JPY"][0]["last_date"] != "2026-02" or series["JPY"][0]["last_value"] != 4.3:
        raise ValueError("synthetic MACRO_SERIES mutation failed")
    if heatmap["currencies"]["JPY"]["labour"]["latest_value"] != 4.3:
        raise ValueError("synthetic heatmap mutation failed")
    if heatmap["currencies"]["JPY"]["as_of_detail"]["unemployment"] != "2026-02":
        raise ValueError("synthetic as_of propagation failed")
    return result


def self_test(series: dict[str, Any], heatmap: dict[str, Any]) -> dict[str, Any]:
    validate_roots(series, heatmap)
    counts = {c: len(series[c]) for c in CURRENCIES}
    if any(v == 0 for v in counts.values()):
        raise ValueError(f"empty currency series arrays: {counts}")
    checks = {
        c: {
            d: {
                "series_id": heatmap["currencies"][c][d].get("series_id"),
                "history_n": len(heatmap["currencies"][c][d].get("history", [])),
                "as_of": heatmap["currencies"][c][d].get("as_of"),
            }
            for d in DIMENSIONS
        }
        for c in CURRENCIES
    }
    synthetic = synthetic_functional_test()
    return {
        "status": "PASS",
        "mode": "SELF_TEST_READ_ONLY",
        "currencies": list(CURRENCIES),
        "macro_series_counts": counts,
        "heatmap_dimensions": checks,
        "synthetic_functional_test": synthetic,
        "writes_live_data": False,
        "changes_engine_rules": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build macro/heatmap replacement candidates without touching live data")
    ap.add_argument("--candidate", help="Validated observation candidate JSON")
    ap.add_argument("--output-dir", default="/tmp/gmfq-macro-candidate")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    series = load(SERIES_PATH)
    heatmap = load(HEATMAP_PATH)
    validate_roots(series, heatmap)

    if args.self_test:
        print(json.dumps(self_test(series, heatmap), ensure_ascii=False, indent=2))
        return 0
    if not args.candidate:
        raise SystemExit("--candidate is required unless --self-test is used")

    candidate = load(pathlib.Path(args.candidate))
    new_series = copy.deepcopy(series)
    new_heatmap = copy.deepcopy(heatmap)
    summary = apply_candidate(new_series, new_heatmap, candidate)

    out = pathlib.Path(args.output_dir)
    dump(out / "MACRO_SERIES.json", new_series)
    dump(out / "MACRO_THERMOMETER_DATA.json", new_heatmap)
    (out / "summary.json").write_text(
        json.dumps({"status": "PASS", "mode": "CANDIDATE_ONLY", "live_data_modified": False, **summary}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "output_dir": str(out), **summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
