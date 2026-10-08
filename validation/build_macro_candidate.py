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
    dd = d2 - d1
    eps = 1e-12
    if dd > eps:
        return "ACCELERA"
    if dd < -eps:
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


def monthly_key(date: Any) -> str:
    text = str(date)
    if len(text) < 7 or text[4] != "-":
        raise ValueError(f"invalid monthly observation date: {text!r}")
    return text[:7]


def resolve_storage_date(dates: list[Any], obs_date: str, frequency: str) -> tuple[str, int | None]:
    """Resolve source date precision against the canonical storage convention.

    Monthly official sources commonly emit YYYY-MM while MACRO_SERIES stores
    YYYY-MM-01.  Treat those as the same economic observation, preserving the
    existing canonical date string on replacements and the established date
    precision on appends.  This does not relax historical-revision safeguards.
    """
    if frequency != "M":
        try:
            return obs_date, dates.index(obs_date)
        except ValueError:
            return obs_date, None

    obs_month = monthly_key(obs_date)
    hits = [i for i, d in enumerate(dates) if monthly_key(d) == obs_month]
    if len(hits) > 1:
        raise ValueError(f"duplicate monthly observations in target series for {obs_month}")
    if hits:
        idx = hits[0]
        return str(dates[idx]), idx

    uses_day_precision = bool(dates) and all(len(str(d)) >= 10 for d in dates)
    storage_date = f"{obs_month}-01" if uses_day_precision else obs_date
    return storage_date, None


def same_period(left: Any, right: Any, frequency: str) -> bool:
    if left is None or right is None:
        return False
    if frequency == "M":
        return monthly_key(left) == monthly_key(right)
    return str(left) == str(right)


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

    storage_date, match_idx = resolve_storage_date(dates, obs_date, str(c["frequency"]))
    if match_idx is not None:
        idx = match_idx
        old_value = float(values[idx])
        if idx != len(dates) - 1 and not c.get("allow_historical_revision", False):
            raise ValueError("historical revision blocked unless allow_historical_revision=true")
        values[idx] = value
        action = "REPLACE_EXISTING"
    else:
        if dates and storage_date < str(dates[-1]):
            raise ValueError("out-of-order observation blocked")
        old_value = None
        dates.append(storage_date)
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
    if same_period(previous_as_of, obs_date, str(c["frequency"])) and hist_values:
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
        "storage_date": storage_date,
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

    precision_series = copy.deepcopy(series)
    precision_heatmap = copy.deepcopy(heatmap)
    precision_series["USD"][0]["dates"] = ["2026-01-01", "2026-02-01"]
    precision_series["USD"][0]["values"] = [1.0, 2.0]
    precision_series["USD"][0]["last_date"] = "2026-02-01"
    precision_series["USD"][0]["last_value"] = 2.0
    precision_heatmap["currencies"]["USD"]["inflation"]["history"] = [1.0, 2.0]
    precision_heatmap["currencies"]["USD"]["inflation"]["as_of"] = "2026-02-01"
    precision_heatmap["currencies"]["USD"]["as_of_detail"]["inflation"] = "2026-02-01"
    precision_candidate = {
        "currency": "USD", "dimension": "inflation", "macro_series_id": "USD_TEST",
        "observation_date": "2026-02", "value": 2.1, "source": "SELF_TEST",
        "series_id": "USD_INF", "frequency": "M", "transformation": "level"
    }
    precision_result = apply_candidate(precision_series, precision_heatmap, precision_candidate)
    if precision_result["series_action"] != "REPLACE_EXISTING":
        raise ValueError("monthly date precision normalization did not replace the existing month")
    if precision_result["storage_date"] != "2026-02-01":
        raise ValueError("monthly date precision normalization did not preserve canonical storage date")
    if precision_series["USD"][0]["dates"] != ["2026-01-01", "2026-02-01"]:
        raise ValueError("monthly date precision normalization duplicated a stored month")
    if precision_heatmap["currencies"]["USD"]["inflation"]["history"] != [1.0, 2.1]:
        raise ValueError("monthly date precision normalization duplicated heatmap history")

    return {"append_case": result, "monthly_precision_case": precision_result}


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
    ap.add_argument("--series-input", help="Read MACRO_SERIES from this snapshot instead of live_data (read-only replay)")
    ap.add_argument("--heatmap-input", help="Read MACRO_THERMOMETER_DATA from this snapshot instead of live_data (read-only replay)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if bool(args.series_input) != bool(args.heatmap_input):
        raise SystemExit("--series-input and --heatmap-input must be supplied together")
    series_input = pathlib.Path(args.series_input) if args.series_input else SERIES_PATH
    heatmap_input = pathlib.Path(args.heatmap_input) if args.heatmap_input else HEATMAP_PATH
    series = load(series_input)
    heatmap = load(heatmap_input)
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
