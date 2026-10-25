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
data["PAIR_SETUP_OPERATIONAL_VIEW.json"]["price_audit"].update(
    status="PASS", as_of="2026-10-22", history_asof="2026-10-22",
    overlay_asof="2026-10-22")
data["D.json"]["asOf"] = "2026-09-25"
data["D.json"]["risk"]["VIX"]["last_date"] = "2026-10-22"
data["D.json"]["risk"]["VIX"]["dates"][-1] = "2026-10-22"
data["D.json"]["risk"]["VIX"]["last_value"] = 19.03
data["NEWS_PULSE_OPERATIONAL.json"]["generated_at_utc"] = "2026-10-23T05:52:00Z"
data["CALENDAR_OPERATIONAL_VIEW.json"]["generated_at_utc"] = "2026-10-23T05:52:00Z"
data["NATIVE_RATES_DATA.json"]["CHF"]["date"] = "2026-09-30"
data["NATIVE_RATES_DATA.json"]["NZD"]["date"] = "2026-10-16"
# Pin the entire OIS test-state fixture: this is a *deterministic synthetic
# readiness test*, not a copy of whatever live OIS statuses happen to exist
# when the GitHub Actions runner checks out the repository. In particular,
# CHF's informational futures proxy is NOT an authenticated official OIS
# curve and must remain in the unverified/withheld bucket.
ois_test_status = {
    "AUD": "GREEN_OFFICIAL",
    "CAD": "GREEN_OFFICIAL",
    "CHF": "WITHHELD",
    "EUR": "WITHHELD",
    "GBP": "GREEN_OFFICIAL",
    "JPY": "GREEN_OFFICIAL",
    "NZD": "WITHHELD",
    "USD": "GREEN_ESTIMATED",
}
assert set(ois_test_status) == set(data["OIS_OPERATIONAL_VIEW.json"]["currencies"])
for ccy, state in ois_test_status.items():
    data["OIS_OPERATIONAL_VIEW.json"]["currencies"][ccy]["operational_status"] = state
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
# All 16 observed periods are visible, but their labels are not release instants
# or newly computed Macro scores. Quarterly observations need not be daily-fresh.
macro = out["evidence"]["MACRO_OBSERVATIONS_G8"]
assert macro["observed"] == 16 and macro["expected"] == 16 and macro["invalid"] == []
assert len(macro["rows"]) == 16
assert not macro["release_timestamps_verified"]
assert not macro["full_first_release_pit_certified"]
assert not macro["scores_recomputed"]
assert macro["rows"]["JPY.inflation"]["reference_period"] == "2026-09"
assert macro["rows"]["AUD.inflation"]["reference_period"] == "2026-06"
assert macro["rows"]["NZD.labour"]["reference_period"] == "2026-06"
assert "mirror" in macro["rows"]["NZD.labour"]["source_label"]
assert all(x["state"] == "OBSERVED_PERIOD_ONLY_NOT_RELEASE_DATE"
           for x in macro["rows"].values())
assert sorted(out["evidence"]["OIS_G8"]["withheld"]) == ["CHF", "EUR", "NZD"]
assert out["evidence"]["OIS_G8"]["official"] == ["AUD", "CAD", "GBP", "JPY"]
assert out["evidence"]["OIS_G8"]["estimated"] == ["USD"]
assert "CHF" not in out["evidence"]["OIS_G8"]["estimated"]
assert "CHF" not in out["evidence"]["OIS_G8"]["official"]
assert "CHF" not in [k for k,v in out["evidence"]["RATES_2Y_10Y"].items() if v["status"] == "RECENT_OFFICIAL"]
assert "NZD" not in [k for k,v in out["evidence"]["RATES_2Y_10Y"].items() if v["status"] == "RECENT_OFFICIAL"]
assert out["core_effect"] == "NONE"
assert out["refresh_pipeline_outcome"] == "success"
assert rome_build_day("2026-10-22T22:30:00Z") == "2026-10-23"
assert rome_build_day("2026-10-22T21:30:00+00:00") == "2026-10-22"
assert rome_build_day("2026-10-25T23:30:00Z") == "2026-10-26"
assert rome_build_day("2026-10-23T08:00:00") is None
assert rome_build_day("invalid") is None
# Corrupt or future economic periods must fail closed without inventing a release.
for mutation in (
    lambda x: x["MACRO_THERMOMETER_DATA.json"]["currencies"]["USD"]["inflation"].update(source=""),
    lambda x: x["MACRO_THERMOMETER_DATA.json"]["currencies"]["EUR"]["labour"].update(as_of="2026-12"),
    lambda x: x["MACRO_THERMOMETER_DATA.json"]["currencies"]["AUD"]["inflation"].update(latest_value=999.0),
):
    bad = copy.deepcopy(data)
    mutation(bad)
    invalid = inspect(bad, asof)
    assert "MACRO_OBSERVATION_SOURCE_INTEGRITY" in invalid["critical_daily_problems"]
    assert invalid["evidence"]["MACRO_OBSERVATIONS_G8"]["observed"] == 15
    assert invalid["operational_state"] == "DAILY_INPUTS_INCOMPLETE"

# News build date and economic signal date are independent.
assert out["evidence"]["NEWS_CONTENT_VINTAGE"]["content_as_of"] == "2026-10-22"
assert out["evidence"]["NEWS_CONTENT_VINTAGE"]["status"] == "PREVIOUS_TRADING_SESSION_OR_NEWER"
assert out["documented_nonblocking_gaps"] == []

for mutation in (
    lambda x: x["NEWS_PULSE_OPERATIONAL.json"].update(content_as_of="2026-12-01"),
    lambda x: x["NEWS_PULSE_OPERATIONAL.json"]["items"][0].update(as_of="2026-12-01"),
    lambda x: x["NEWS_PULSE_OPERATIONAL.json"].update(content_as_of="invalid"),
):
    bad = copy.deepcopy(data)
    mutation(bad)
    news_bad = inspect(bad, asof)
    assert "NEWS_CONTENT_VINTAGE_INTEGRITY" in news_bad["critical_daily_problems"]
    assert news_bad["evidence"]["NEWS_CONTENT_VINTAGE"]["status"] == "INVALID_OR_FUTURE_VINTAGE"

# A failed collector must still be visible even when all surviving feeds are fresh.
partial = inspect(data, asof, pipeline_outcome="failure")
assert partial["operational_state"] == "DAILY_INPUTS_INCOMPLETE"
assert partial["critical_daily_problems"] == ["REFRESH_PIPELINE_NOT_SUCCESS"]
assert partial["refresh_pipeline_outcome"] == "failure"

# A future time on the same Rome date must NOT certify the 08:00 briefing.
for feed_name,problem in (
    ("NEWS_PULSE_OPERATIONAL.json", "NEWS_PULSE_REFRESH"),
    ("CALENDAR_OPERATIONAL_VIEW.json", "CALENDAR_REFRESH"),
):
    future = copy.deepcopy(data)
    future[feed_name]["generated_at_utc"] = "2026-10-23T06:52:00Z"  # 08:52 CEST
    future_state = inspect(future, asof)
    assert future_state["evidence"][problem]["status"] == "FUTURE_DATED"
    assert problem in future_state["critical_daily_problems"]
    assert future_state["operational_state"] == "DAILY_INPUTS_INCOMPLETE"
    missing_timezone = copy.deepcopy(data)
    missing_timezone[feed_name]["generated_at_utc"] = "2026-10-23T05:52:00"
    assert problem in inspect(missing_timezone, asof)["critical_daily_problems"]

midnight_news = copy.deepcopy(data)
midnight_news["NEWS_PULSE_OPERATIONAL.json"]["generated_at_utc"] = "2026-10-22T22:30:00Z"
assert "NEWS_PULSE_REFRESH" not in inspect(midnight_news, asof)["critical_daily_problems"]
midnight_cal = copy.deepcopy(data)
midnight_cal["CALENDAR_OPERATIONAL_VIEW.json"]["generated_at_utc"] = "2026-10-22T22:30:00Z"
assert "CALENDAR_REFRESH" not in inspect(midnight_cal, asof)["critical_daily_problems"]

# A declared 28-pair count does not certify 28 distinct G8 crosses.
# All 28 actual keys and the corresponding official fixing audit must agree.
for mutation in (
    lambda x: x["PAIR_SETUP_OPERATIONAL_VIEW.json"]["pairs"].pop("EURUSD"),
    lambda x: x["PAIR_SETUP_OPERATIONAL_VIEW.json"]["price_audit"].update(as_of="2026-10-21"),
    lambda x: x["PAIR_SETUP_OPERATIONAL_VIEW.json"]["price_audit"].update(history_asof="2026-10-21"),
    lambda x: x["PAIR_SETUP_OPERATIONAL_VIEW.json"]["price_audit"].update(complete_pair_count=27),
    lambda x: x["PAIR_SETUP_OPERATIONAL_VIEW.json"]["price_audit"].update(no_lookahead=False),
):
    broken_pair = copy.deepcopy(data)
    mutation(broken_pair)
    result_bad = inspect(broken_pair, asof)
    assert "PAIR_SOURCE_INTEGRITY" in result_bad["critical_daily_problems"], result_bad["critical_daily_problems"]
    assert result_bad["operational_state"] == "DAILY_INPUTS_INCOMPLETE"

# At 08:00 local, a current-day ECB close or VIX close cannot be
# represented as a verified already-published previous session.
for target in ("FX", "PAIR", "VIX"):
    impossible = copy.deepcopy(data)
    if target == "FX":
        impossible["ECB_G8_PRICE_HISTORY.json"]["last_as_of"] = "2026-10-23"
        impossible["ECB_G8_PRICE_HISTORY.json"]["rows"][-1]["Date"] = "2026-10-23"
        impossible["PAIR_SETUP_OPERATIONAL_VIEW.json"]["price_asof"] = "2026-10-23"
        impossible["PAIR_SETUP_OPERATIONAL_VIEW.json"]["price_audit"].update(as_of="2026-10-23",history_asof="2026-10-23",overlay_asof="2026-10-23")
        expected_problem = "FX_OFFICIAL_FIXING"
    elif target == "PAIR":
        impossible["PAIR_SETUP_OPERATIONAL_VIEW.json"]["price_asof"] = "2026-10-23"
        impossible["PAIR_SETUP_OPERATIONAL_VIEW.json"]["price_audit"].update(as_of="2026-10-23",overlay_asof="2026-10-23")
        expected_problem = "PAIR_PRICE"
    else:
        impossible["D.json"]["risk"]["VIX"]["last_date"] = "2026-10-23"
        impossible["D.json"]["risk"]["VIX"]["dates"][-1] = "2026-10-23"
        expected_problem = "VIX_OFFICIAL_CLOSE"
    morning_out = inspect(impossible, asof)
    assert expected_problem in morning_out["critical_daily_problems"], morning_out["critical_daily_problems"]

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
monday_feed["PAIR_SETUP_OPERATIONAL_VIEW.json"]["price_audit"].update(as_of="2026-10-23",history_asof="2026-10-23",overlay_asof="2026-10-23")
monday_feed["D.json"]["risk"]["VIX"]["last_date"] = "2026-10-23"
monday_feed["D.json"]["risk"]["VIX"]["dates"][-1] = "2026-10-23"
monday_feed["NEWS_PULSE_OPERATIONAL.json"]["generated_at_utc"] = "2026-10-26T05:10:00Z"
monday_feed["CALENDAR_OPERATIONAL_VIEW.json"]["generated_at_utc"] = "2026-10-26T05:10:00Z"
monday_check = inspect(monday_feed, monday)
assert not monday_check["critical_daily_problems"]
assert monday_check["evidence"]["NEWS_CONTENT_VINTAGE"]["status"] == "OLDER_THAN_PREVIOUS_TRADING_SESSION"
assert monday_check["documented_nonblocking_gaps"] == ["NEWS_CONTENT_OLDER_THAN_PREVIOUS_SESSION"]

broken = copy.deepcopy(data)
broken["ECB_G8_PRICE_HISTORY.json"]["rows"][-1]["Date"] = "2026-10-21"
assert "FX_SOURCE_INTEGRITY" in inspect(broken, asof)["critical_daily_problems"]
broken = copy.deepcopy(data)
broken["D.json"]["risk"]["VIX"]["dates"][-1] = "2026-10-21"
assert "VIX_SOURCE_INTEGRITY" in inspect(broken, asof)["critical_daily_problems"]
# Saturday is not a weekday market session: Friday is the correct comparison.
assert prior_weekday(dt.date(2026,10,24)).isoformat() == "2026-10-23"
print("GMFQ_MORNING_READINESS_SOURCE_AND_DST_GUARDS_PASS")
