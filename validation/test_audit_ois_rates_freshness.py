#!/usr/bin/env python3
"""Read-only G8 source-age classification regression (no external queries)."""
from __future__ import annotations
import copy
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from audit_ois_rates_freshness import evaluate
from build_rates_audit_metadata import RECENT_MAX_CALENDAR_DAYS

ROOT = Path(__file__).resolve().parents[1]
rates = json.loads((ROOT/"live_data/sections/NATIVE_RATES_DATA.json").read_text())
ois = json.loads((ROOT/"live_data/sections/OIS_OPERATIONAL_VIEW.json").read_text())
today = datetime.now(ZoneInfo('Europe/Rome')).date()

proof = evaluate(rates=rates, ois=ois, today=today)
rows = {r["ccy"]: r for r in proof["rows"]}
assert len(rows) == 8
assert rows["CHF"]["rates_source_status"] == "VALIDATED_HISTORICAL_OFFICIAL_SNAPSHOT"
nzd_recent = (today - date.fromisoformat(rates["NZD"]["date"])).days <= RECENT_MAX_CALENDAR_DAYS
aud_recent = (today - date.fromisoformat(rates["AUD"]["date"])).days <= 7
assert rows["NZD"]["rates_source_status"] == ("MANUAL_REVIEWED_RECENT" if nzd_recent else "MANUAL_REVIEWED_LAGGING")
assert rows["AUD"]["rates_source_status"] == ("SOURCE_CADENCE_VALIDATED" if aud_recent else "SOURCE_CADENCE_LAGGING")
assert rows["AUD"]["rates_current_by_source_cadence"] is aud_recent
assert rows["CHF"]["rates_current_by_source_cadence"] is False
assert rows["NZD"]["rates_current_by_source_cadence"] is nzd_recent
# A non-certified, informational futures proxy is not promoted to OIS.
# The production EUR row currently says WITHHELD; this is a known source gap,
# not a source-integrity failure or a publication blocker.
if ois["currencies"]["EUR"]["operational_status"] == "WITHHELD":
    assert rows["EUR"]["ois_source_class"] == "NO_CERTIFIED_CURRENT_OIS_CURVE"
    assert any(g["ccy"] == "EUR" and g["issue"] == "NO_CERTIFIED_CURRENT_OIS_CURVE"
               for g in proof["known_gaps"])
else:
    assert rows["EUR"]["ois_source_class"] in (
        "INDICATIVE_FUTURES_NOT_OFFICIAL_OIS", "OFFICIAL_DATED")
assert rows["GBP"]["ois_source_class"] == "OFFICIAL_DATED"
expected_usd = {
    "WITHHELD": "NO_CERTIFIED_CURRENT_OIS_CURVE",
    "GREEN_ESTIMATED": "INDICATIVE_FUTURES_NOT_OFFICIAL_OIS",
    "GREEN_OFFICIAL": "OFFICIAL_DATED",
}
assert rows["USD"]["ois_source_class"] == expected_usd[ois["currencies"]["USD"]["operational_status"]]
if ois["currencies"]["USD"]["operational_status"] == "GREEN_ESTIMATED":
    assert rows["USD"]["ois_source_class"] != "OFFICIAL_DATED"
assert not proof["integrity_issues"], proof["integrity_issues"]
assert proof["writes_live_data"] is False
assert proof["promotes_estimates_to_official"] is False

# A *separate* hypothetical validated indicative input retains its
# informational classification, never OFFICIAL_DATED.
indicative = copy.deepcopy(ois)
indicative["currencies"]["EUR"]["operational_status"] = "GREEN_ESTIMATED"
flag = evaluate(rates=rates, ois=indicative, today=today)
assert next(x for x in flag["rows"] if x["ccy"] == "EUR")["ois_source_class"] == (
    "INDICATIVE_FUTURES_NOT_OFFICIAL_OIS"
)
assert not flag["integrity_issues"], flag["integrity_issues"]

# Stale is not a broken publisher. An official Green that lacks a price IS.
bad = copy.deepcopy(ois)
bad["currencies"]["GBP"]["horizons"]["3m"]["rate"] = None
flag = evaluate(rates=rates, ois=bad, today=today)
assert any(x["ccy"] == "GBP" and x["issue"] == "OFFICIAL_MARKED_GREEN_BUT_INVALID"
           for x in flag["integrity_issues"])

future = copy.deepcopy(rates)
future["NZD"]["date"] = (today + timedelta(days=1)).isoformat()
flag = evaluate(rates=future, ois=ois, today=today)
assert any(x["ccy"] == "NZD" and x["issue"] == "INVALID_OR_FUTURE_SOURCE_DATE"
           for x in flag["integrity_issues"])

bad = copy.deepcopy(ois)
bad["currencies"]["CHF"]["operational_status"] = "GREEN_ESTIMATED"
bad["currencies"]["CHF"]["as_of"] = (today + timedelta(days=1)).isoformat()
flag = evaluate(rates=rates, ois=bad, today=today)
assert any(x["ccy"] == "CHF" and x["issue"] == "INVALID_INDICATIVE_SOURCE_DATE"
           for x in flag["integrity_issues"])

print("CONTROL_ROOM_G8_SOURCE_FRESHNESS_CADENCE_AND_INTEGRITY_PASS")
