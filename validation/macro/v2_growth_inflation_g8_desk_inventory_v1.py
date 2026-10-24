#!/usr/bin/env python3
"""Read-only G8 Growth/Inflation inventory with period-aware labels, NEVER PIT-certified.

A reference period, even when dated YYYY-MM-DD, is *not* a first-publication timestamp.
Recency is relative to the end of the observed calendar period; cadence cutoffs are
research heuristics, not evidence that an actual release has occurred or is current.
"""
import argparse
import calendar
import json
import math
import re
from datetime import date
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import ROOT, require

CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
CATS = {"growth": "Crescita", "inflation": "Inflazione"}
AS_OF = date(2026, 10, 23)
# Descriptive cadence checks only: neither a release schedule nor a freshness SLA.
CADENCE_DAYS = {"M": 75, "Q": 135}


def parse_reference_period(raw, frequency):
    """Return (period_end, granularity) without fabricating a release timestamp.

    Accepted observation labels: YYYY-MM-DD, YYYY-MM, YYYYQ1..YYYYQ4.
    Frequency M/Q determines the *reference period*, even when a first-of-month
    date is used as the storage convention. Reject incompatible/malformed labels.
    """
    if not isinstance(raw, str) or not raw:
        return None
    freq = (frequency or "").upper()
    if freq not in ("", "M", "Q", "D"):
        return None
    q = re.fullmatch(r"(\d{4})Q([1-4])", raw)
    if q:
        if freq not in ("", "Q"):
            return None
        year, quarter = int(q.group(1)), int(q.group(2))
        month = quarter * 3
        if year < 1:
            return None
        return date(year, month, calendar.monthrange(year, month)[1]), "quarter"
    month = re.fullmatch(r"(\d{4})-(\d{2})", raw)
    if month:
        if freq == "D":
            return None
        year, mm = int(month.group(1)), int(month.group(2))
        if not 1 <= year <= 9999 or not 1 <= mm <= 12:
            return None
        if freq == "Q" and mm not in (3, 6, 9, 12):
            return None
        return date(year, mm, calendar.monthrange(year, mm)[1]), ("quarter" if freq == "Q" else "month")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return None
    try:
        observed = date.fromisoformat(raw)
    except ValueError:
        return None
    if freq == "Q":
        if observed.month not in (3, 6, 9, 12):
            return None
        return date(observed.year, observed.month, calendar.monthrange(observed.year, observed.month)[1]), "quarter"
    if freq == "M":
        return date(observed.year, observed.month, calendar.monthrange(observed.year, observed.month)[1]), "month"
    # Unspecified frequency with an exact date must NOT be silently recast as monthly.
    return observed, "day"


def inspect(data, *, as_of=AS_OF):
    require(set(data) == set(CURRENCIES), "G8 series keys drift")
    rows = []
    for ccy in CURRENCIES:
        for pillar, cat in CATS.items():
            candidates = [x for x in data[ccy] if x.get("category") == cat]
            require(candidates, ccy + " " + pillar + " has no observed series")
            selected = []
            for x in candidates:
                parsed = parse_reference_period(x.get("last_date"), x.get("frequency"))
                value = x.get("last_value")
                if (parsed is None or type(value) not in (int, float)
                        or not math.isfinite(value) or parsed[0] > as_of):
                    continue
                selected.append((parsed[0], x["id"], x, parsed[1]))
            if selected:
                period_end, _, series, granularity = max(selected, key=lambda item: (item[0], item[1]))
                period_age_days = (as_of - period_end).days
                frequency = (series.get("frequency") or "").upper()
                cadence = CADENCE_DAYS.get(frequency)
                recency = ("REFERENCE_PERIOD_CADENCE_UNKNOWN" if cadence is None else
                           "REFERENCE_PERIOD_WITHIN_EXPECTED_CADENCE" if period_age_days <= cadence else
                           "REFERENCE_PERIOD_OLDER_THAN_EXPECTED_CADENCE")
            else:
                period_end, series, granularity, period_age_days, cadence = None, None, None, None, None
                recency = "NO_VALID_DATED_VALUE"
            raw_period = series.get("last_date") if series else None
            rows.append({
                "currency": ccy,
                "pillar": pillar,
                "series_id": series["id"] if series else None,
                # Legacy exact-date-only field: never invent a day for monthly/quarterly labels.
                "latest_observed_on": raw_period if raw_period and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_period) else None,
                "reference_period_raw": raw_period,
                "reference_period_end": period_end.isoformat() if period_end else None,
                "reference_period_granularity": granularity,
                "latest_observed_value": series["last_value"] if series else None,
                "unit": (series.get("unit") or "SOURCE_UNIT_NOT_DECLARED") if series else None,
                "frequency": series.get("frequency") if series else None,
                "source_file_hint_unverified": series.get("source_file") if series else None,
                "candidate_series_count": len(candidates),
                "reference_period_age_days": period_age_days,
                "observation_age_days": period_age_days,  # Deprecated: same period-end age, NOT release age.
                "expected_cadence_heuristic_days": cadence,
                "research_freshness": recency,
                "release_freshness": "UNKNOWN_NO_RELEASE_TIMESTAMP",
                "release_age_days": None,
                "release_timestamp_first_vintage_verified": False,
                "source_consensus_verified": False,
                "growth_or_inflation_macro_score": None,
                "note": "Reference period end is derived from the source label; first-release date and data vintage are not verified",
            })
    return {
        "schema": "GMFQ_MACRO_V2_G8_GROWTH_INFLATION_DESK_INVENTORY_V1",
        "temporal_parser_revision": "PERIOD_AWARE_M_Q_2026_10_23",
        "as_of": as_of.isoformat(),
        "status": "OBSERVED_SERIES_RESEARCH_ONLY_NOT_PIT",
        "rows": rows,
        "currencies": 8,
        "pillars": 16,
        "older_than_cadence_slots": sum(r["research_freshness"] == "REFERENCE_PERIOD_OLDER_THAN_EXPECTED_CADENCE" for r in rows),
        "cadence_unknown_slots": sum(r["research_freshness"] == "REFERENCE_PERIOD_CADENCE_UNKNOWN" for r in rows),
        "missing_valid_dated_value_slots": sum(r["reference_period_age_days"] is None for r in rows),
        "certified_first_release_slots": 0,
        "observational_selection_method": "latest_reference_period_among_currently_available_source_series_not_model_selection",
        "source_selection_validated_for_scoring": False,
        "economic_score_computed": False,
        "eligible_for_backtest": False,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "writes_live_data": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    data = json.loads((ROOT / "live_data/sections/MACRO_SERIES.json").read_text())
    result = inspect(data)
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")), "research receipts only /tmp")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"pillars": result["pillars"],
                      "periods_older_than_cadence": result["older_than_cadence_slots"],
                      "unknown_release_dates": result["pillars"] - result["certified_first_release_slots"],
                      "missing": result["missing_valid_dated_value_slots"],
                      "certified": result["certified_first_release_slots"]}))


if __name__ == "__main__":
    main()
