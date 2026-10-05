#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SERIES = ROOT / "live_data" / "sections" / "MACRO_SERIES.json"
DEFAULT_HEATMAP = ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json"
CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
DIMENSIONS = ("inflation", "labour")
DETAIL_KEY = {"inflation": "inflation", "labour": "unemployment"}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def same_value(a: Any, b: Any) -> bool:
    try:
        return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=1e-10)
    except (TypeError, ValueError):
        return False


def bind_series(rows: list[dict[str, Any]], source_series_id: str) -> tuple[dict[str, Any] | None, str, int]:
    exact = [r for r in rows if isinstance(r, dict) and str(r.get("id")) == source_series_id]
    if len(exact) == 1:
        return exact[0], "EXACT", 1
    if len(exact) > 1:
        return None, "EXACT_AMBIGUOUS", len(exact)

    # Historical IDs in MACRO_SERIES wrap the source ID, e.g. EA_UNEMP_history_value.
    # Only accept a unique containment match; ambiguity is a hard failure.
    contained = [
        r for r in rows
        if isinstance(r, dict)
        and source_series_id
        and source_series_id.lower() in str(r.get("id", "")).lower()
    ]
    if len(contained) == 1:
        return contained[0], "UNIQUE_CONTAINMENT", 1
    return None, "CONTAINMENT_AMBIGUOUS" if contained else "NOT_FOUND", len(contained)


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify MACRO_SERIES latest points are aligned with Macro Heatmap")
    ap.add_argument("--series-path", type=Path, default=DEFAULT_SERIES)
    ap.add_argument("--heatmap-path", type=Path, default=DEFAULT_HEATMAP)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    series = load(args.series_path)
    heatmap = load(args.heatmap_path)
    checks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for currency in CURRENCIES:
        rows = series.get(currency, [])
        hccy = heatmap.get("currencies", {}).get(currency, {})
        for dimension in DIMENSIONS:
            hrow = hccy.get(dimension, {})
            source_series_id = str(hrow.get("series_id", ""))
            item: dict[str, Any] = {
                "currency": currency,
                "dimension": dimension,
                "heatmap_series_id": source_series_id,
            }
            row, binding, matches = bind_series(rows, source_series_id)
            item["binding"] = binding
            if row is None:
                item.update({"status": "FAIL", "reason": "SERIES_BINDING", "matches": matches})
                failures.append(item)
                checks.append(item)
                continue

            item["macro_series_id"] = row.get("id")
            dates = row.get("dates")
            values = row.get("values")
            if not isinstance(dates, list) or not isinstance(values, list) or not dates or len(dates) != len(values):
                item.update({"status": "FAIL", "reason": "INVALID_SERIES_HISTORY"})
                failures.append(item)
                checks.append(item)
                continue

            series_date = str(dates[-1])
            series_value = values[-1]
            row_last_date = str(row.get("last_date"))
            row_last_value = row.get("last_value")
            heat_date = str(hrow.get("as_of"))
            heat_value = hrow.get("latest_value")
            detail_date = str(hccy.get("as_of_detail", {}).get(DETAIL_KEY[dimension]))

            reasons = []
            if row_last_date != series_date:
                reasons.append("ROW_LAST_DATE")
            if not same_value(row_last_value, series_value):
                reasons.append("ROW_LAST_VALUE")
            # Heatmap dates can be YYYY-MM while MACRO_SERIES can be YYYY-MM-DD.
            if not series_date.startswith(heat_date):
                reasons.append("HEATMAP_AS_OF")
            if not series_date.startswith(detail_date):
                reasons.append("AS_OF_DETAIL")
            if not same_value(series_value, heat_value):
                reasons.append("HEATMAP_LATEST_VALUE")

            item.update({
                "status": "FAIL" if reasons else "PASS",
                "reason": reasons or None,
                "series_date": series_date,
                "series_value": series_value,
                "row_last_date": row_last_date,
                "row_last_value": row_last_value,
                "heatmap_as_of": heat_date,
                "heatmap_latest_value": heat_value,
                "as_of_detail": detail_date,
            })
            if reasons:
                failures.append(item)
            checks.append(item)

    result = {
        "status": "PASS" if not failures else "FAIL",
        "checks": len(checks),
        "failures": len(failures),
        "failure_items": failures,
        "details": checks,
        "read_only": True,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
