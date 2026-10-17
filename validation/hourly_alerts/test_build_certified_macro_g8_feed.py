from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).with_name("build_certified_macro_g8_feed.py")
spec = importlib.util.spec_from_file_location("macro_feed", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

NOW = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)
EVENT = {"event_id": "US-CPI-2026-10-17T08:30:00Z", "currency": "USD", "indicator": "CPI YoY", "period": "2026-09",
         "release_timestamp_utc": "2026-10-17T08:30:00Z", "as_of_utc": "2026-10-17T08:31:00Z", "actual": 3.0,
         "consensus": 2.9, "previous": 2.8, "revisions": [],
         "source": {"authority": "U.S. Bureau of Labor Statistics", "release_url": "https://example.invalid/bls-release",
                    "consensus_provider": "licensed-provider", "consensus_as_of_utc": "2026-10-17T08:29:00Z"}}

def main() -> None:
    good = module.build({"schema": module.SCHEMA, "as_of_utc": "2026-10-17T08:31:00Z", "events": [EVENT]}, NOW)
    assert good["alert_eligible"] is True and len(good["events"]) == 1
    duplicate = module.build({"schema": module.SCHEMA, "as_of_utc": "2026-10-17T08:31:00Z", "events": [EVENT, EVENT]}, NOW)
    assert duplicate["alert_eligible"] is False and not duplicate["events"]
    missing_consensus = {**EVENT, "consensus": None}
    bad = module.build({"schema": module.SCHEMA, "as_of_utc": "2026-10-17T08:31:00Z", "events": [missing_consensus]}, NOW)
    assert bad["alert_eligible"] is False
    seen = module.build({"schema": module.SCHEMA, "as_of_utc": "2026-10-17T08:31:00Z", "events": [EVENT]}, NOW, {EVENT["event_id"]})
    assert seen["alert_eligible"] is False
    print("CERTIFIED_MACRO_G8_FEED_PASS")

if __name__ == "__main__":
    main()
