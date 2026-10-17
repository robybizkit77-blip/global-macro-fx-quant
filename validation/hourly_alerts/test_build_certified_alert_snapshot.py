from __future__ import annotations

import importlib.util
from datetime import date, datetime, timezone
from pathlib import Path


SCRIPT = Path(__file__).with_name("build_certified_alert_snapshot.py")
spec = importlib.util.spec_from_file_location("hourly_alert_snapshot", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def main() -> None:
    result = module.build(date(2026, 10, 17))
    assert result["schema"] == "GMFQ_HOURLY_ALERT_CERTIFIED_SNAPSHOT_V1"
    assert result["policy"]["fail_closed"] is True
    assert result["policy"]["government_bond_2y_is_not_ois"] is True
    assert result["policy"]["last_verified_value_is_not_post_event_reaction"] is True
    assert result["summary"]["green"] is False
    assert result["lanes"]["ois"]["NZD"]["state"] == "UNAVAILABLE"
    assert result["lanes"]["ois"]["EUR"]["state"] == "UNAVAILABLE"
    assert result["lanes"]["ois"]["USD"]["state"] == "UNAVAILABLE"
    assert result["lanes"]["ois"]["CHF"]["state"] == "UNAVAILABLE"
    assert result["lanes"]["ois"]["GBP"]["state"] == "AVAILABLE_CERTIFIED"
    assert result["lanes"]["ois"]["JPY"]["state"] == "AVAILABLE_CERTIFIED"
    assert result["lanes"]["ois"]["CAD"]["state"] == "AVAILABLE_CERTIFIED"
    assert result["lanes"]["ois"]["AUD"]["state"] == "AVAILABLE_CERTIFIED"
    assert result["lanes"]["treasury"]["state"] == "AVAILABLE_CERTIFIED"
    assert result["lanes"]["g8_bonds"]["CHF"]["state"] == "STALE"
    assert result["lanes"]["g8_bonds"]["NZD"]["state"] == "STALE"
    assert result["lanes"]["cot"]["state"] == "AVAILABLE_CERTIFIED"
    assert result["lanes"]["fx"]["state"] == "AVAILABLE_CERTIFIED"
    assert result["lanes"]["macro"]["state"] == "UNAVAILABLE"
    assert result["lanes"]["credit_liquidity"]["USD"]["state"] == "UNAVAILABLE"
    assert result["lanes"]["equity_sectors"]["state"] == "UNAVAILABLE"
    assert result["summary"]["state"] == "WITHHELD"
    assert result["lanes"]["cot"]["as_of"] == "2026-10-13"
    assert result["lanes"]["fx"]["as_of"] == "2026-10-16"
    assert result["lanes"]["fx"]["source"] == "ECB euro foreign exchange reference rates"
    assert result["lanes"]["treasury"]["value_scope"] == "LAST_VERIFIED_OBSERVATION_NOT_POST_EVENT_REACTION"

    missing_source = module.record(
        name="TEST", as_of="2026-10-17", today=date(2026, 10, 17),
        max_age_days=3, certified=True, source=None,
    )
    assert missing_source["state"] == "UNAVAILABLE"
    assert missing_source["alert_eligible"] is False

    feed_spec = importlib.util.spec_from_file_location("macro_feed", Path(__file__).with_name("build_certified_macro_g8_feed.py"))
    feed_module = importlib.util.module_from_spec(feed_spec)
    assert feed_spec.loader is not None
    feed_spec.loader.exec_module(feed_module)
    feed_event = {
        "event_id": "UK-CPI-2026-10-17T08:00:00Z", "currency": "GBP", "indicator": "CPI YoY", "period": "2026-09",
        "release_timestamp_utc": "2026-10-17T08:00:00Z", "as_of_utc": "2026-10-17T08:01:00Z",
        "actual": 3.2, "consensus": 3.1, "previous": 3.0, "revisions": [],
        "source": {"authority": "UK Office for National Statistics", "release_url": "https://example.invalid/ons",
                   "consensus_provider": "licensed-provider", "consensus_as_of_utc": "2026-10-17T07:59:00Z"},
    }
    feed = feed_module.build({"schema": feed_module.SCHEMA, "as_of_utc": "2026-10-17T08:01:00Z", "events": [feed_event]}, datetime(2026, 10, 17, 10, tzinfo=timezone.utc))
    integrated = module.build(date(2026, 10, 17), feed)
    assert integrated["lanes"]["macro"]["alert_eligible"] is True
    assert integrated["lanes"]["macro"]["event"]["event_id"] == feed_event["event_id"]
    print("HOURLY_ALERT_CERTIFIED_SNAPSHOT_PASS")


if __name__ == "__main__":
    main()
