from __future__ import annotations

import importlib.util
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path


SCRIPT = Path(__file__).with_name("build_certified_alert_snapshot.py")
spec = importlib.util.spec_from_file_location("hourly_alert_snapshot", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def expected_state(as_of, today, limit, certified, source):
    """Independent eligibility expectation; preserve future, stale and absent."""
    try:
        day = date.fromisoformat(as_of[:10])
        age = (today - day).days
    except (ValueError, TypeError, KeyError):
        age = None
    if not certified or not isinstance(source, str) or not source.strip() or age is None or age < 0:
        return "UNAVAILABLE"
    if age > limit:
        return "STALE"
    return "AVAILABLE_CERTIFIED"


def main() -> None:
    # Unit tests must use the same Rome-local civil day as the scheduled
    # classifier. A pinned 17 October date makes newly certified quotes look
    # future-dated and blocks every scheduled run before the outbox is built.
    today = datetime.now(ZoneInfo("Europe/Rome")).date()
    result = module.build(today)
    assert result["schema"] == "GMFQ_HOURLY_ALERT_CERTIFIED_SNAPSHOT_V1"
    assert result["as_of_evaluation_date"] == today.isoformat()
    assert result["policy"]["fail_closed"] is True
    assert result["policy"]["government_bond_2y_is_not_ois"] is True
    assert result["policy"]["last_verified_value_is_not_post_event_reaction"] is True
    assert result["summary"]["green"] is False
    assert result["summary"]["state"] == "WITHHELD"

    official = module.load("OIS_OPERATIONAL_VIEW.json")["currencies"]
    for ccy in module.CCYS:
        row = official[ccy]
        certified = (ccy in module.CERTIFIED_OIS_CCYS
                     and row.get("operational_status") == "GREEN_OFFICIAL"
                     and row.get("official_status") == "ACTIVE"
                     and row.get("quality") == "OFFICIAL_CERTIFIED"
                     and row.get("backtest_eligible_as_official") is True)
        receipt = result["lanes"]["ois"][ccy]
        expected = expected_state(row.get("as_of"), today, 3, certified, row.get("source"))
        assert receipt["state"] == expected, (ccy, receipt, expected)
        assert receipt["alert_eligible"] is (expected == "AVAILABLE_CERTIFIED")
        if ccy not in module.CERTIFIED_OIS_CCYS:
            assert receipt["state"] == "UNAVAILABLE", (ccy, receipt)
            assert receipt["alert_eligible"] is False

    rates = module.load("NATIVE_RATES_DATA.json")
    for ccy in module.CCYS:
        row = rates[ccy]
        certified = (row.get("freshness_status") in module.OFFICIAL_RATE_FRESHNESS
                     and row.get("quality") in module.OFFICIAL_RATE_QUALITY)
        receipt = result["lanes"]["g8_bonds"][ccy]
        expected = expected_state(row.get("date"), today, 3, certified, row.get("source"))
        assert receipt["state"] == expected, (ccy, receipt, expected)
        assert receipt["alert_eligible"] is (expected == "AVAILABLE_CERTIFIED")

    assert result["lanes"]["treasury"]["state"] == result["lanes"]["g8_bonds"]["USD"]["state"]
    assert result["lanes"]["treasury"]["value_scope"] == "LAST_VERIFIED_OBSERVATION_NOT_POST_EVENT_REACTION"
    cot = module.load("V250_COT_CHART_DATA.json")
    cot_day = module.latest_cot_date(cot)
    cot_receipt = result["lanes"]["cot"]
    assert cot_receipt["as_of"] == cot_day
    assert cot_receipt["state"] == expected_state(
        cot_day, today, 10, cot_day is not None, cot_receipt["source"])
    pairs = module.load("PAIR_SETUP_OPERATIONAL_VIEW.json")
    fx = result["lanes"]["fx"]
    assert fx["as_of"] == pairs["price_asof"]
    assert fx["source"] == pairs["price_source"]
    assert fx["state"] == expected_state(
        pairs["price_asof"], today, 3,
        pairs.get("schema") == "GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1"
        and pairs.get("status") == "CURRENT_CANONICAL_ENGINE"
        and isinstance(pairs.get("price_source"), str)
        and "ECB" in pairs["price_source"],
        pairs.get("price_source"))
    assert result["lanes"]["macro"]["state"] == "UNAVAILABLE"
    assert result["lanes"]["credit_liquidity"]["USD"]["state"] == "UNAVAILABLE"
    assert result["lanes"]["equity_sectors"]["state"] == "UNAVAILABLE"

    for label, as_of, certified, source, expected in (
        ("positive", today.isoformat(), True, "certified fixture", "AVAILABLE_CERTIFIED"),
        ("stale", (today - timedelta(days=4)).isoformat(), True, "certified fixture", "STALE"),
        ("future", (today + timedelta(days=1)).isoformat(), True, "certified fixture", "UNAVAILABLE"),
        ("missing source", today.isoformat(), True, None, "UNAVAILABLE"),
        ("unapproved proxy", today.isoformat(), False, "proxy fixture", "UNAVAILABLE"),
    ):
        row = module.record(name=label, as_of=as_of, today=today,
                            max_age_days=3, certified=certified, source=source)
        assert row["state"] == expected, (label, row)
        assert row["alert_eligible"] is (expected == "AVAILABLE_CERTIFIED")

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
