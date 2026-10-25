#!/usr/bin/env python3
"""Calendar/News may be verified today even when valid market content is unchanged."""
from __future__ import annotations

import datetime as dt
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import build_calendar_operational_v1 as calendar
import build_news_pulse_operational_v1 as news
from refresh_macro_consensus_secondary_v1 import series_compatible

UTC = dt.timezone.utc


def at(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value)


def test_builder(module) -> None:
    # Friday vintage persisted before the Sunday and Monday validation runs.
    old_time = "2026-10-23T06:52:00Z"
    friday_content = {"schema": "TEST_NO_NEW_SIGNAL", "items": [{"as_of": "2026-10-22"}]}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "output.json"
        original = dict(friday_content, generated_at_utc=old_time)
        path.write_text(json.dumps(original), encoding="utf-8")
        with patch.object(module, "OUT", path):
            # Sunday check is not a content update.
            assert module.stable_write(friday_content, at("2026-10-25T08:10:00+01:00")) is False
            sunday = json.loads(path.read_text(encoding="utf-8"))
            assert sunday["generated_at_utc"] == old_time
            assert sunday["last_checked_at_utc"] == "2026-10-25T07:10:00Z"
            assert sunday["items"][0]["as_of"] == "2026-10-22"

            # Monday 05:00 CET: source re-verified, same last meaningful signal.
            assert module.stable_write(friday_content, at("2026-10-26T05:12:00+01:00")) is False
            monday = json.loads(path.read_text(encoding="utf-8"))
            assert monday["generated_at_utc"] == old_time
            assert monday["last_checked_at_utc"] == "2026-10-26T04:12:00Z"
            assert monday["items"][0]["as_of"] == "2026-10-22"

            # Subsequent runs on same Rome date do not churn main with a new
            # timestamp; this avoids repeat publication loops.
            before = path.read_bytes()
            assert module.stable_write(friday_content, at("2026-10-26T07:48:00+01:00")) is False
            assert path.read_bytes() == before

            # A real new signal does advance the content-generated time too.
            changed = {"schema": "TEST_NO_NEW_SIGNAL", "items": [{"as_of": "2026-10-26"}]}
            assert module.stable_write(changed, at("2026-10-26T08:01:00+01:00")) is True
            latest = json.loads(path.read_text(encoding="utf-8"))
            assert latest["generated_at_utc"] == "2026-10-26T07:01:00Z"
            assert latest["last_checked_at_utc"] == "2026-10-26T07:01:00Z"
            assert latest["items"][0]["as_of"] == "2026-10-26"


for builder in (calendar, news):
    test_builder(builder)

print("CALENDAR_NEWS_TRUE_RECHECK_VINTAGE_CET_CEST_PASS")


# The same country and date do not make two macro indicators the same
# economic series. Regressions documented from the 25 October public feed.
bad_pairs = [
    ("AUD", "INFLATION", "Consumer Price Index, Australia", "Import Prices q/q"),
    ("EUR", "GROWTH", "Euro area preliminary flash GDP", "French Flash GDP q/q"),
    ("EUR", "LABOUR", "Euro area unemployment", "German Unemployment Change"),
    ("JPY", "LABOUR", "Labour Force Survey - Basic Tabulation", "Unemployment Rate"),
    ("AUD", "INFLATION", "Consumer Price Index, Australia", "CPI m/m"),
]
for ccy, event_type, official_title, provider_title in bad_pairs:
    assert not series_compatible(
        {"ccy": ccy, "event_type": event_type, "title": official_title},
        {"event": provider_title}
    ), (official_title, provider_title)

good_pairs = [
    ("USD", "LABOUR_COST", "Employment Cost Index", "Employment Cost Index q/q"),
    ("CAD", "GROWTH", "Gross domestic product by industry", "GDP m/m"),
    ("EUR", "GROWTH", "Euro area preliminary flash GDP", "Eurozone Flash GDP q/q"),
    ("EUR", "LABOUR", "Euro area unemployment", "Eurozone Unemployment Rate"),
]
for ccy, event_type, official_title, provider_title in good_pairs:
    assert series_compatible(
        {"ccy": ccy, "event_type": event_type, "title": official_title},
        {"event": provider_title}
    ), (official_title, provider_title)

# Defense in depth: even when the previously persisted secondary JSON still
# carries invalid matches, the independently rebuilt public calendar must
# quarantine their values before they are ever exposed to the user.
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    day = "2099-10-28"
    examples = [
        ("AUD", "INFLATION", "Consumer Price Index, Australia", "Import Prices q/q"),
        ("EUR", "GROWTH", "Euro area preliminary flash GDP", "French Flash GDP q/q"),
        ("EUR", "LABOUR", "Euro area unemployment", "German Unemployment Change"),
        ("USD", "LABOUR_COST", "Employment Cost Index", "Employment Cost Index q/q"),
    ]
    macro_rows = [
        {"ccy": ccy, "date": day, "event_type": kind,
         "title": title, "quality": "OFFICIAL_CALENDAR"}
        for ccy, kind, title, provider in examples
    ]
    consensus_rows = [
        {"event_key": "|".join((ccy, day, kind, title)),
         "status": "AVAILABLE", "consensus": "1.8%", "previous": "5.7%",
         "provider_event": provider, "provider": "TEST"}
        for ccy, kind, title, provider in examples
    ]
    cb_file = root / "cb.json"
    official_file = root / "official.json"
    consensus_file = root / "consensus.json"
    public_file = root / "calendar.json"
    cb_file.write_text(json.dumps({}, indent=2))
    official_file.write_text(json.dumps({"events": macro_rows}, indent=2))
    consensus_file.write_text(json.dumps({"events": consensus_rows}, indent=2))
    with (patch.object(calendar, "CB", cb_file),
          patch.object(calendar, "MACRO", official_file),
          patch.object(calendar, "CONSENSUS", consensus_file),
          patch.object(calendar, "OUT", public_file)):
        calendar.main()
    result = json.loads(public_file.read_text(encoding="utf-8"))
    assert len(result["events"]) == 4
    assert result["coverage"]["consensus_available_events"] == 1
    for event in result["events"]:
        if event["ccy"] == "USD":
            assert event["consensus_status"] == "AVAILABLE"
            assert event["consensus"] == "1.8%"
        else:
            assert event["consensus_status"] == "NOT_PRESENT"
            assert "consensus" not in event and "previous" not in event

print("MACRO_CONSENSUS_EXACT_SERIES_AND_REGION_GUARDS_PASS")
