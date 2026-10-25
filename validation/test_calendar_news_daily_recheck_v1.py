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
