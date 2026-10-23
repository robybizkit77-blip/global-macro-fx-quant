#!/usr/bin/env python3
"""Deterministic morning readout regressions; data changes require source parity."""
import copy
import datetime as dt
from zoneinfo import ZoneInfo
from check_morning_readiness_v1 import read_feeds, inspect, prior_weekday, rome_build_day

ROME = ZoneInfo("Europe/Rome")
data = read_feeds()
# A fixed validated as-of fixture: future production refreshes must not
# make these deterministic gate tests depend on today's latest close.
data["ECB_G8_PRICE_HISTORY.json"]["status"] = "CURRENT_OFFICIAL_HISTORY"
data["ECB_G8_PRICE_HISTORY.json"]["last_as_of"] = "2026-10-22"
data["ECB_G8_PRICE_HISTORY.json"]["rows"][-1]["Date"] = "2026-10-22"
data["PAIR_SETUP_OPERATIONAL_VIEW.json"].update(
    status="CURRENT_CANONICAL_ENGINE", pair_count=28,
    price_asof="2026-10-22", macro_baseline_asof="2026-09-25")
data["PAIR_SETUP_OPERATIONAL_VIEW.json"]["price_audit"]["status"] = "PASS"
data["D.json"]["asOf"] = "2026-09-25"
data["D.json"]["risk"]["VIX"]["last_date"] = "2026-10-22"
data["D.json"]["risk"]["VIX"]["dates"][-1] = "2026-10-22"
data["D.json"]["risk"]["VIX"]["last_value"] = 19.03
data["NEWS_PULSE_OPERATIONAL.json"]["generated_at_utc"] = "2026-10-23T06:52:00Z"
data["CALENDAR_OPERATIONAL_VIEW.json"]["generated_at_utc"] = "2026-10-23T06:52:00Z"
data["NATIVE_RATES_DATA.json"]["CHF"]["date"] = "2026-09-30"
data["NATIVE_RATES_DATA.json"]["NZD"]["date"] = "2026-10-16"
data["OIS_OPERATIONAL_VIEW.json"]["currencies"]["EUR"]["operational_status"] = "WITHHELD"
data["OIS_OPERATIONAL_VIEW.json"]["currencies"]["NZD"]["operational_status"] = "WITHHELD"
asof = dt.datetime.fromisoformat("2026-10-23T08:00:00+02:00")
out = inspect(data, asof)
assert out["schema"] == "GMFQ_MORNING_READINESS_V1"
assert out["expected_previous_weekday"] == "2026-10-22"
assert out["operational_state"] == "DAILY_READY_WITH_DOCUMENTED_GAPS", out["critical_daily_problems"]
assert out["critical_daily_problems"] == []
assert out["evidence"]["FX_OFFICIAL_FIXING"]["as_of"] == "2026-10-22"
assert out["evidence"]["VIX_OFFICIAL_CLOSE"]["as_of"] == "2026-10-22"
assert out["evidence"]["MACRO_BASELINE"]["as_of"] == "2026-09-25"
assert out["evidence"]["MACRO_BASELINE"]["state"] == "HISTORICAL_NOT_AUTO_RECALCULATED"
assert sorted(out["evidence"]["OIS_G8"]["withheld"]) == ["EUR", "NZD"]
assert "CHF" not in [k for k,v in out["evidence"]["RATES_2Y_10Y"].items() if v["status"] == "RECENT_OFFICIAL"]
assert "NZD" not in [k for k,v in out["evidence"]["RATES_2Y_10Y"].items() if v["status"] == "RECENT_OFFICIAL"]
assert out["core_effect"] == "NONE"
assert out["refresh_pipeline_outcome"] == "success"
assert rome_build_day("2026-10-22T22:30:00Z") == "2026-10-23"
assert rome_build_day("2026-10-22T21:30:00+00:00") == "2026-10-22"
assert rome_build_day("2026-10-25T23:30:00Z") == "2026-10-26"
assert rome_build_day("2026-10-23T08:00:00") is None
assert rome_build_day("invalid") is None
# A failed collector must still be visible even when all surviving feeds are fresh.
partial = inspect(data, asof, pipeline_outcome="failure")
assert partial["operational_state"] == "DAILY_INPUTS_INCOMPLETE"
assert partial["critical_daily_problems"] == ["REFRESH_PIPELINE_NOT_SUCCESS"]
assert partial["refresh_pipeline_outcome"] == "failure"

midnight_news = copy.deepcopy(data)
midnight_news["NEWS_PULSE_OPERATIONAL.json"]["generated_at_utc"] = "2026-10-22T22:30:00Z"
assert "NEWS_PULSE_REFRESH" not in inspect(midnight_news, asof)["critical_daily_problems"]
midnight_cal = copy.deepcopy(data)
midnight_cal["CALENDAR_OPERATIONAL_VIEW.json"]["generated_at_utc"] = "2026-10-22T22:30:00Z"
assert "CALENDAR_REFRESH" not in inspect(midnight_cal, asof)["critical_daily_problems"]

broken = copy.deepcopy(data)
broken["ECB_G8_PRICE_HISTORY.json"]["last_as_of"] = "2026-10-21"
x = inspect(broken,asof)
assert "FX_OFFICIAL_FIXING" in x["critical_daily_problems"]
assert "PAIR_FX_SOURCE_DATE_DIVERGENCE" in x["critical_daily_problems"]
assert x["operational_state"] == "DAILY_INPUTS_INCOMPLETE"

broken = copy.deepcopy(data)
broken["NEWS_PULSE_OPERATIONAL.json"]["generated_at_utc"] = "2026-10-22T08:00:00Z"
assert "NEWS_PULSE_REFRESH" in inspect(broken, asof)["critical_daily_problems"]

broken = copy.deepcopy(data)
broken["D.json"]["asOf"] = "2026-09-24"
assert "PAIR_MACRO_BASELINE_DIVERGENCE" in inspect(broken, asof)["critical_daily_problems"]

broken = copy.deepcopy(data)
broken["ECB_G8_PRICE_HISTORY.json"]["rows"] = []
assert "FX_SOURCE_INTEGRITY" in inspect(broken, asof)["critical_daily_problems"]

# Monday after Europe switches from CEST to CET: expected last official
# trading session is Friday, not the nonexistent Sunday fixing.
monday = dt.datetime.fromisoformat("2026-10-26T08:00:00+01:00")
assert prior_weekday(monday.date()).isoformat() == "2026-10-23"
monday_feed = copy.deepcopy(data)
monday_feed["ECB_G8_PRICE_HISTORY.json"]["last_as_of"] = "2026-10-23"
monday_feed["ECB_G8_PRICE_HISTORY.json"]["rows"][-1]["Date"] = "2026-10-23"
monday_feed["PAIR_SETUP_OPERATIONAL_VIEW.json"]["price_asof"] = "2026-10-23"
monday_feed["D.json"]["risk"]["VIX"]["last_date"] = "2026-10-23"
monday_feed["D.json"]["risk"]["VIX"]["dates"][-1] = "2026-10-23"
monday_feed["NEWS_PULSE_OPERATIONAL.json"]["generated_at_utc"] = "2026-10-26T05:10:00Z"
monday_feed["CALENDAR_OPERATIONAL_VIEW.json"]["generated_at_utc"] = "2026-10-26T05:10:00Z"
assert not inspect(monday_feed, monday)["critical_daily_problems"]

broken = copy.deepcopy(data)
broken["ECB_G8_PRICE_HISTORY.json"]["rows"][-1]["Date"] = "2026-10-21"
assert "FX_SOURCE_INTEGRITY" in inspect(broken, asof)["critical_daily_problems"]
broken = copy.deepcopy(data)
broken["D.json"]["risk"]["VIX"]["dates"][-1] = "2026-10-21"
assert "VIX_SOURCE_INTEGRITY" in inspect(broken, asof)["critical_daily_problems"]
# Saturday is not a weekday market session: Friday is the correct comparison.
assert prior_weekday(dt.date(2026,10,24)).isoformat() == "2026-10-23"
print("GMFQ_MORNING_READINESS_SOURCE_AND_DST_GUARDS_PASS")
