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
    ("2026-10-23T03:59:00+02:00", False),
    ("2026-10-23T04:00:00+02:00", True),
    ("2026-10-23T04:43:00+02:00", True),  # new CEST primary prebrief
    ("2026-10-23T04:59:00+02:00", True),
    ("2026-10-23T05:00:00+02:00", True),
    ("2026-10-23T09:59:00+02:00", True),
    ("2026-10-23T10:00:00+02:00", False),
    ("2026-10-25T08:00:00+01:00", False),  # Sunday DST transition
    ("2026-10-26T03:59:00+01:00", False),
    ("2026-10-26T04:00:00+01:00", True),
    ("2026-10-26T04:43:00+01:00", True),  # new CET primary prebrief
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
    good[name]["last_checked_at_utc"] = "2026-10-26T05:30:00Z"
# Freeze the historical Monday-morning content vintage too, not just the
# generated_at timestamp. Current live News Pulse has advanced past Oct 22.
# This test explicitly exercises the nonblocking STALE_NEWS_CONTENT receipt.
news_fixture=good["NEWS_PULSE_OPERATIONAL.json"]
news_fixture["content_as_of"]="2026-10-22"
for item in news_fixture["items"]:
    item["as_of"]="2026-10-22"
for c in good["MACRO_THERMOMETER_DATA.json"]["currencies"].values():
    for key in ("inflation", "labour"):
        c[key]["as_of"] = "2026-09"
# Pin independent research coverage gaps so this remains deterministic.
for ccy in ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"):
    good["NATIVE_RATES_DATA.json"][ccy]["date"] = "2026-10-23"
    good["NATIVE_RATES_DATA.json"][ccy]["quality"] = "FULL_CURRENT_OFFICIAL"
good["NATIVE_RATES_DATA.json"]["CHF"]["date"] = "2026-09-30"
good["NATIVE_RATES_DATA.json"]["NZD"]["date"] = "2026-10-16"
for ccy, status in {
    "USD": "GREEN_ESTIMATED", "EUR": "WITHHELD",
    "GBP": "GREEN_OFFICIAL", "JPY": "GREEN_OFFICIAL",
    "CHF": "WITHHELD", "CAD": "GREEN_OFFICIAL",
    "AUD": "GREEN_OFFICIAL", "NZD": "WITHHELD",
}.items():
    good["OIS_OPERATIONAL_VIEW.json"]["currencies"][ccy]["operational_status"] = status

# The 04:43 source gate must be active BEFORE the primary workflow publishes.
# A legitimate early producer receipt must be judged at its actual timestamp,
# not falsely failed because the later 07:45 fixtures have not happened yet.
early = at("2026-10-26T04:43:00+01:00")
early_good = copy.deepcopy(good)
for name in ("NEWS_PULSE_OPERATIONAL.json", "CALENDAR_OPERATIONAL_VIEW.json"):
    early_good[name]["generated_at_utc"] = "2026-10-26T02:20:00Z"
    early_good[name]["last_checked_at_utc"] = "2026-10-26T02:20:00Z"
early_passed = evaluate(early, early_good)
assert early_passed["morning_gate_required"] is True
assert early_passed["status"] == "PASS_MORNING_SOURCES_VERIFIED", early_passed
assert early_passed["window"] == "WEEKDAYS_04_00_TO_10_00_EUROPE_ROME"
early_missing = copy.deepcopy(early_good)
early_missing["PAIR_SETUP_OPERATIONAL_VIEW.json"]["pairs"].pop(
    next(iter(early_missing["PAIR_SETUP_OPERATIONAL_VIEW.json"]["pairs"]))
)
early_blocked = evaluate(early, early_missing)
assert early_blocked["status"] == "BLOCK_MORNING_INPUTS_INCOMPLETE", early_blocked
assert "PAIR_SOURCE_INTEGRITY" in early_blocked["critical_daily_problems"]
# A source refresh not yet performed must not get credited to early prebrief.
early_future = copy.deepcopy(early_good)
early_future["NEWS_PULSE_OPERATIONAL.json"]["last_checked_at_utc"] = "2026-10-26T05:30:00Z"
assert evaluate(early, early_future)["status"] == "BLOCK_MORNING_INPUTS_INCOMPLETE"

passed = evaluate(monday, good)
assert passed["status"] == "PASS_MORNING_SOURCES_VERIFIED", passed
assert passed["evidence_as_of"] == {
    "FX_OFFICIAL_FIXING": "2026-10-23",
    "PAIR_PRICE": "2026-10-23",
    "VIX_OFFICIAL_CLOSE": "2026-10-23",
}
assert passed["critical_daily_problems"] == []
assert passed["status"] == "PASS_MORNING_SOURCES_VERIFIED"
# The source was checked today even if its meaningful news content is older.
for name in ("NEWS_PULSE_OPERATIONAL.json", "CALENDAR_OPERATIONAL_VIEW.json"):
    unchanged = copy.deepcopy(good)
    unchanged[name]["generated_at_utc"] = "2026-10-23T06:52:00Z"
    assert evaluate(monday, unchanged)["status"] == "PASS_MORNING_SOURCES_VERIFIED"

# Monday's file was regenerated for this test, but its newest underlying
# market signal is still from Thursday. The Pages receipt must not erase it.
assert passed["news_content_vintage"]["content_as_of"] == "2026-10-22", passed
assert passed["news_content_vintage"]["status"] == "OLDER_THAN_PREVIOUS_TRADING_SESSION", passed
assert passed["documented_nonblocking_gaps"] == [
    "NEWS_CONTENT_OLDER_THAN_PREVIOUS_SESSION",
    "RATES_2Y_10Y_LAG_OR_BLOCKED:CHF,NZD",
    "OIS_G8_UNAVAILABLE:CHF,EUR,NZD",
], passed


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
assert evaluate(at("2026-10-25T07:45:00+01:00"), bad_source)["documented_nonblocking_gaps"] == []
assert evaluate(at("2026-10-25T07:45:00+01:00"), bad_source)["news_content_vintage"] is None


print("PAGES_ALL_TRIGGER_MORNING_READINESS_POLICY_PASS")

# The policy must be executed inside the writer itself, before gh-pages push;
# covering only the parent orchestrator would leave push/workflow_run open.
workflow = (Path(__file__).resolve().parents[2] /
            ".github/workflows/publish-dashboard-pages-v1.yml").read_text()
marker = "Block incomplete morning sources before any Pages write"
publish = "Publish dashboard runtime and operational assets to gh-pages with lease"
assert workflow.count(marker) == 1
assert workflow.index(marker) < workflow.index(publish)
assert "check_pages_morning_readiness_v1.py \\" in workflow
assert "if: github.event_name != 'pull_request'" in workflow
for trigger in ("push:", "workflow_run:", "workflow_dispatch:"):
    assert trigger in workflow
