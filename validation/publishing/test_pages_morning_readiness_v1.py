#!/usr/bin/env python3
"""Deterministic coverage for every Pages trigger and CET/CEST transition."""
from __future__ import annotations

import copy
import datetime as dt
from zoneinfo import ZoneInfo

from check_pages_morning_readiness_v1 import evaluate, in_morning_window
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "orchestration"))
from check_morning_readiness_v1 import read_feeds

ROME = ZoneInfo("Europe/Rome")


def at(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text)


for when, expected in (
    ("2026-10-23T04:59:00+02:00", False),
    ("2026-10-23T05:00:00+02:00", True),
    ("2026-10-23T09:59:00+02:00", True),
    ("2026-10-23T10:00:00+02:00", False),
    ("2026-10-25T08:00:00+01:00", False),  # Sunday DST transition
    ("2026-10-26T05:00:00+01:00", True),  # Monday in CET
    ("2026-10-26T09:59:00+01:00", True),
    ("2026-10-26T10:00:00+01:00", False),
    ("2027-03-29T05:00:00+02:00", True),  # Monday in CEST
):
    assert in_morning_window(at(when)) is expected, when

try:
    in_morning_window(dt.datetime(2026, 10, 26, 8, 0))
except ValueError:
    pass
else:
    raise AssertionError("Naive publication time cannot bypass Rome clock gate")

monday = at("2026-10-26T07:45:00+01:00")
raw = read_feeds()
# Make a stable, known-good 26 Oct test scenario from validated feed shapes.
good = copy.deepcopy(raw)
fx = good["ECB_G8_PRICE_HISTORY.json"]
fx["status"] = "CURRENT_OFFICIAL_HISTORY"
fx["last_as_of"] = fx["rows"][-1]["Date"] = "2026-10-23"
fx["row_count"] = len(fx["rows"])
pair = good["PAIR_SETUP_OPERATIONAL_VIEW.json"]
pair["status"] = "CURRENT_CANONICAL_ENGINE"
pair["pair_count"] = 28
pair["price_asof"] = "2026-10-23"
pair["macro_baseline_asof"] = good["D.json"]["asOf"]
pair["price_audit"].update(
    status="PASS", as_of="2026-10-23", history_asof="2026-10-23",
    overlay_asof="2026-10-23", pair_count=28, complete_pair_count=28,
    no_lookahead=True, returns_complete=True
)
vix = good["D.json"]["risk"]["VIX"]
vix["last_date"] = "2026-10-23"
vix["dates"][-1] = "2026-10-23"
for name in ("NEWS_PULSE_OPERATIONAL.json", "CALENDAR_OPERATIONAL_VIEW.json"):
    good[name]["generated_at_utc"] = "2026-10-26T05:30:00Z"
for c in good["MACRO_THERMOMETER_DATA.json"]["currencies"].values():
    for key in ("inflation", "labour"):
        c[key]["as_of"] = "2026-09"

passed = evaluate(monday, good)
assert passed["status"] == "PASS_MORNING_SOURCES_VERIFIED", passed
assert passed["evidence_as_of"] == {
    "FX_OFFICIAL_FIXING": "2026-10-23",
    "PAIR_PRICE": "2026-10-23",
    "VIX_OFFICIAL_CLOSE": "2026-10-23",
}
assert passed["critical_daily_problems"] == []

missing_pair = copy.deepcopy(good)
missing_pair["PAIR_SETUP_OPERATIONAL_VIEW.json"]["pairs"].pop(
    next(iter(missing_pair["PAIR_SETUP_OPERATIONAL_VIEW.json"]["pairs"]))
)
blocked = evaluate(monday, missing_pair)
assert blocked["status"] == "BLOCK_MORNING_INPUTS_INCOMPLETE"
assert "PAIR_SOURCE_INTEGRITY" in blocked["critical_daily_problems"]

future_news = copy.deepcopy(good)
future_news["NEWS_PULSE_OPERATIONAL.json"]["generated_at_utc"] = "2026-10-26T08:00:00Z"
blocked = evaluate(monday, future_news)
assert blocked["status"] == "BLOCK_MORNING_INPUTS_INCOMPLETE"
assert "NEWS_PULSE_REFRESH" in blocked["critical_daily_problems"]

bad_source = copy.deepcopy(good)
del bad_source["D.json"]
assert evaluate(monday, bad_source)["status"] == "BLOCK_SOURCE_AUDIT_EXCEPTION"

# Out-of-window publications continue under their existing structural gates.
assert evaluate(at("2026-10-26T11:00:00+01:00"), bad_source)["status"] == "PASS_OUTSIDE_MORNING_WINDOW"
assert evaluate(at("2026-10-25T07:45:00+01:00"), bad_source)["status"] == "PASS_OUTSIDE_MORNING_WINDOW"

print("PAGES_ALL_TRIGGER_MORNING_READINESS_POLICY_PASS")
