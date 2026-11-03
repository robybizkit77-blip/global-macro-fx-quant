#!/usr/bin/env python3
"""Read-only G8 source-clock audit for the canonical Control Room v10.

An official observation need not be current. RBA F2 has weekly file cadence,
NZD B2 is manual-reviewed, CHF same-basis yield is an older SNB observation.
A futures scenario is not an official synchronized OIS curve. Record those
differences without editing any source, model, pair thesis or published rate.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from build_rates_audit_metadata import source_status

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ROOT / "live_data" / "sections"
G8 = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
RECENT_RATE_STATES = {
    "RECENT_OFFICIAL_OBSERVATION", "SOURCE_CADENCE_VALIDATED",
    "MANUAL_REVIEWED_RECENT",
}
RECENT_OIS_DAYS = 5


def parse_age(value, today):
    try:
        age = (today - dt.date.fromisoformat(value)).days
        return age if age >= 0 else None
    except (TypeError, ValueError):
        return None


def evaluate(*, rates=None, ois=None, today=None):
    """Keep known historical gaps separate from actionable source contradictions."""
    if today is None:
        today = dt.datetime.now(dt.timezone.utc).date()
    if rates is None:
        rates = json.loads((SECTIONS / "NATIVE_RATES_DATA.json").read_text())
    if ois is None:
        ois = json.loads((SECTIONS / "OIS_OPERATIONAL_VIEW.json").read_text())
    assert set(rates) == set(G8), "Exactly eight source rate rows are required"
    assert set(ois.get("currencies") or {}) == set(G8), "Exactly eight OIS rows are required"

    rows, known_gaps, integrity_issues = [], [], []
    for c in G8:
        r = rates[c]
        observed = r.get("date")
        r_age = parse_age(observed, today)
        try:
            r_status = source_status(c, observed, today.isoformat()) if r_age is not None else None
        except (TypeError, ValueError):
            r_status = None
        if r_status is None:
            integrity_issues.append({"layer": "RATES", "ccy": c, "issue": "INVALID_OR_FUTURE_SOURCE_DATE"})
            status_name = "UNVERIFIED"
        else:
            status_name = r_status["status"]
            if status_name not in RECENT_RATE_STATES:
                known_gaps.append({"layer": "RATES", "ccy": c,
                                   "issue": status_name, "last_observation": observed,
                                   "source_access": r_status["source_access"]})
        o = ois["currencies"][c]
        o_status = o.get("operational_status")
        o_age = parse_age(o.get("as_of"), today)
        horizons = o.get("horizons") or {}
        points = [horizons.get(t) for t in ("3m", "6m", "12m")]
        if o_status == "GREEN_OFFICIAL":
            complete = all(isinstance(q, dict) and
                           type(q.get("rate")) in (int, float) for q in points)
            if not complete or o_age is None:
                integrity_issues.append({"layer": "OIS", "ccy": c,
                                         "issue": "OFFICIAL_MARKED_GREEN_BUT_INVALID"})
            elif o_age > RECENT_OIS_DAYS:
                known_gaps.append({"layer": "OIS", "ccy": c,
                                   "issue": "OFFICIAL_OBSERVATION_LAGGING",
                                   "last_observation": o.get("as_of")})
            o_class = "OFFICIAL_DATED"
        elif o_status == "GREEN_ESTIMATED":
            # Dated futures observations may span different sessions; never
            # claim an official, synchronized expected-policy curve.
            o_class = "INDICATIVE_FUTURES_NOT_OFFICIAL_OIS"
            if o_age is None:
                integrity_issues.append({"layer": "OIS", "ccy": c,
                                         "issue": "INVALID_INDICATIVE_SOURCE_DATE"})
        else:
            o_class = "NO_CERTIFIED_CURRENT_OIS_CURVE"
            if o_status != "WITHHELD":
                integrity_issues.append({"layer": "OIS", "ccy": c,
                                         "issue": "UNRECOGNIZED_OPERATIONAL_STATUS"})
            else:
                known_gaps.append({"layer": "OIS", "ccy": c,
                                   "issue": "NO_CERTIFIED_CURRENT_OIS_CURVE",
                                   "last_observation": o.get("as_of")})
        rows.append({
            "ccy": c, "rates_as_of": observed, "rates_age_calendar_days": r_age,
            "rates_source_status": status_name,
            "rates_current_by_source_cadence": status_name in RECENT_RATE_STATES,
            "ois_as_of": o.get("as_of"), "ois_operational_status": o_status,
            "ois_source_class": o_class,
            "ois_age_calendar_days": o_age,
        })

    return {
        "schema": "GMFQ_SOURCE_FRESHNESS_AUDIT_V1",
        "as_of": today.isoformat(),
        "status": "SOURCE_INTEGRITY_ISSUE" if integrity_issues else (
            "HISTORICAL_OR_UNCERTIFIED_GAPS" if known_gaps else "PASS"),
        "rows": rows, "known_gaps": known_gaps,
        "integrity_issues": integrity_issues,
        "writes_live_data": False, "promotes_estimates_to_official": False,
        "modifies_fx_pair_signals": False,
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2, ensure_ascii=False))
