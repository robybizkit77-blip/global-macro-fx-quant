#!/usr/bin/env python3
from build_public_macro_alerts import build


def receipt(event=None):
    return {"generated_at_utc": "2026-10-17T10:00:00Z", "as_of_evaluation_date": "2026-10-17",
            "lanes": {"macro": {"alert_eligible": event is not None, "event": event}}}


def event():
    return {"event_id": "gbp-cpi-20261017", "currency": "GBP", "indicator": "CPI", "period": "2026-09",
            "release_timestamp_utc": "2026-10-17T09:00:00Z", "as_of_utc": "2026-10-17T09:02:00Z",
            "actual": 3.0, "consensus": 2.9, "previous": 2.8, "revisions": [],
            "source": {"authority": "ONS", "release_url": "https://example.test/ons", "consensus_provider": "licensed", "consensus_as_of_utc": "2026-10-17T08:00:00Z"}}


def test_empty_feed_is_withheld_and_does_not_invent_history():
    x = build(receipt(), {"kind": "FALLBACK", "withheld_reason": "No fresh event."}, None)
    assert x["state"] == "WITHHELD" and x["today"] == [] and x["history"] == []


def test_certified_event_is_deduplicated_and_preserves_history():
    out = {"kind": "SIGNIFICANT"}
    one = build(receipt(event()), out, None)
    two = build(receipt(event()), out, one)
    assert one["state"] == "ACTIVE" and one["today"][0]["related_pairs"] == ["GBPUSD", "EURGBP"]
    assert len(two["history"]) == 1 and two["history"][0]["event_id"] == "gbp-cpi-20261017"
