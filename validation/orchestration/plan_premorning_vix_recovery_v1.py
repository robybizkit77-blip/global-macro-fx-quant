#!/usr/bin/env python3
"""Read-only 07:45 Rome VIX recovery: skip only after official previous-session close.

A green workflow result is not source-date proof. This assesses current main
D.json only; it never modifies market data or infers an unpublished VIX close.
Its RETRY decision permits the already existing official Cboe fetch workflow.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
SCHEMA = "GMFQ_PREMORNING_VIX_RECOVERY_V1"


def previous_weekday(day: dt.date) -> dt.date:
    day -= dt.timedelta(days=1)
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day


def assess(now: dt.datetime, model: dict | None) -> dict:
    if not isinstance(now, dt.datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware evaluation clock required")
    local = now.astimezone(ROME)
    expected = previous_weekday(local.date()).isoformat()
    risk = model.get("risk") if isinstance(model, dict) else None
    row = risk.get("VIX") if isinstance(risk, dict) else None
    row = row if isinstance(row, dict) else {}
    asof = row.get("last_date")
    dates, values, value = row.get("dates"), row.get("values"), row.get("last_value")
    date_valid = False
    if isinstance(asof, str):
        try:
            date_valid = dt.date.fromisoformat(asof).isoformat() == asof
        except ValueError:
            pass
    value_valid = (type(value) in (int, float) and math.isfinite(value)
                   and isinstance(values, list) and bool(values)
                   and type(values[-1]) in (int, float) and math.isfinite(values[-1])
                   and abs(values[-1] - value) < 1e-8)
    series_valid = (value_valid and isinstance(dates, list) and bool(dates)
                    and len(dates) == len(values) and dates[-1] == asof)
    # A stale or invalid market snapshot is a request for another source check,
    # NOT an invitation to backfill a fabricated observation.
    current = date_valid and asof == expected and series_valid
    return {
        "schema": SCHEMA,
        "checked_at_rome": local.isoformat(timespec="seconds"),
        "required_previous_weekday": expected,
        "observed_official_date": asof if date_valid else None,
        "source_history_integrity": bool(series_valid),
        "status": "SKIP_OFFICIAL_PREVIOUS_CLOSE_VERIFIED" if current else "RETRY_OFFICIAL_CBOE_CHECK",
        "official_market_data_only": True,
        "core_scoring_effect": "NONE",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-file", type=Path, required=True)
    p.add_argument("--as-of", help="Timezone-aware ISO clock for deterministic tests only")
    args = p.parse_args()
    try:
        now = dt.datetime.fromisoformat(args.as_of) if args.as_of else dt.datetime.now(dt.timezone.utc)
        data = json.loads(args.source_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("PREMORNING_VIX_RECOVERY", json.dumps({
            "schema": SCHEMA, "status": "RETRY_OFFICIAL_CBOE_CHECK",
            "reason": type(exc).__name__, "source_history_integrity": False
        }))
        return 1
    result = assess(now, data)
    print("PREMORNING_VIX_RECOVERY", json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "SKIP_OFFICIAL_PREVIOUS_CLOSE_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
