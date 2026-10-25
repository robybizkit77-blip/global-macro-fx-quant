#!/usr/bin/env python3
"""Deterministic Rome 08:00 SLA contract, including the 2026 DST transition."""
from __future__ import annotations

import copy
import datetime as dt
from zoneinfo import ZoneInfo

from check_morning_delivery_sla_v1 import evaluate

ROME = ZoneInfo("Europe/Rome")


def at(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value)


good = {
    "schema": "GMFQ_MORNING_READINESS_V1",
    "operational_state": "DAILY_READY_WITH_DOCUMENTED_GAPS",
    "refresh_pipeline_outcome": "success",
    "critical_daily_problems": [],
    "checked_at_rome": "2026-10-26T07:44:00+01:00",
}

for phase in ("prebrief", "premorning"):
    ontime = evaluate(phase, good, at("2026-10-26T07:59:59+01:00"))
    assert ontime["status"] == "PASS_DELIVERED_BY_0800", ontime
    assert ontime["on_time"] is True
    assert ontime["target_rome"] == "2026-10-26T08:00:00+01:00"
    late = evaluate(phase, good, at("2026-10-26T08:00:01+01:00"))
    assert late["status"] == "LATE_SOURCES_READY_AFTER_DEADLINE"
    assert late["source_and_publication_sequence_successful"] is True
    assert late["on_time"] is False

# 25 October CEST->CET: the previous Friday is not a reason to shift 08:00.
before_dst = copy.deepcopy(good)
before_dst["checked_at_rome"] = "2026-10-23T07:44:00+02:00"
out = evaluate("premorning", before_dst, at("2026-10-23T07:59:00+02:00"))
assert out["target_rome"] == "2026-10-23T08:00:00+02:00" and out["on_time"]

# Replayed Friday receipt, future-dated audit, missing artifact and bad runs all fail.
for changed in (
    None,
    {},
    dict(good, checked_at_rome="2026-10-23T07:59:00+02:00"),
    dict(good, checked_at_rome="2026-10-26T08:01:00+01:00"),
    dict(good, checked_at_rome="2026-10-26T07:44:00"),
    dict(good, operational_state="DAILY_INPUTS_INCOMPLETE"),
    dict(good, refresh_pipeline_outcome="failure"),
    dict(good, critical_daily_problems=["PAIR_SOURCE_INTEGRITY"]),
):
    state = evaluate("prebrief", changed, at("2026-10-26T07:59:00+01:00"))
    assert state["status"] == "FAIL_INCOMPLETE_OR_UNVERIFIED", state

try:
    evaluate("night", good, at("2026-10-26T07:59:00+01:00"))
except ValueError:
    pass
else:
    raise AssertionError("Non-morning phases must never certify 08:00")

try:
    evaluate("prebrief", good, dt.datetime(2026, 10, 26, 7, 59))
except ValueError:
    pass
else:
    raise AssertionError("Naive timestamps must never certify Rome 08:00")

print("MORNING_0800_DELIVERY_SLA_CET_CEST_PASS")
