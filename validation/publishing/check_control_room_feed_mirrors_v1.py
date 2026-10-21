#!/usr/bin/env python3
"""Control Room v10: each fetched source has one authorized public mirror owner.

The UI deliberately reads raw/main, not a gh-pages copy. Still, third-party
public readers of /live_data/sections/ must never get silently stale feeds.
This gate does not assess model validity or promote any proxy to an OIS source.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site/control-room-preview/home-navigation-v10.js"
DASH = ROOT / ".github/workflows/publish-dashboard-pages-v1.yml"
MARKET = ROOT / ".github/workflows/publish-control-room-market-data-v1.yml"
PUBLIC = ROOT / "validation/publishing/verify_pages_http_delivery_v1.py"

DASH_OWNED = {
    "D.json", "ESTIMATED_RESIDUAL_GAPS.json",
    "MACRO_THERMOMETER_DATA.json", "OIS_OPERATIONAL_VIEW.json",
    "V247_COT_STORIES.json", "NATIVE_CB_DATA.json",
    "CHF_SNB_10Y_SPOT_CONTEXT.json",
    "NZD_CB_PRICING_DIRECTIONAL_PROXY.json",
    "OIS_SOURCE_READINESS_VIEW.json",
}
MARKET_OWNED = {
    "NATIVE_RATES_DATA.json", "V250_COT_CHART_DATA.json",
    "PAIR_SETUP_OPERATIONAL_VIEW.json", "ECB_G8_PRICE_HISTORY.json",
    "DXY_SYNTHETIC_ECB.json",
}


def main() -> int:
    site = SITE.read_text(encoding="utf-8")
    dash = DASH.read_text(encoding="utf-8")
    market = MARKET.read_text(encoding="utf-8")
    public = PUBLIC.read_text(encoding="utf-8")
    called = set(re.findall(r"\bfeed\('([^']+\.json)'\)", site))
    all_owned = DASH_OWNED | MARKET_OWNED
    assert not (DASH_OWNED & MARKET_OWNED), "duplicate feed owners"
    assert called == all_owned, {
        "unowned": sorted(called - all_owned),
        "discontinued": sorted(all_owned - called),
    }
    for name in sorted(all_owned):
        path = ROOT / "live_data/sections" / name
        assert path.is_file(), f"Missing canonical feed {name}"
        obj = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(obj, dict) and obj, f"Invalid feed {name}"
    copy_loop = next(line for line in dash.splitlines()
                     if line.strip().startswith("for f in OIS_OPERATIONAL_VIEW.json "))
    copied = set(copy_loop.strip().split("; do", 1)[0].split()[3:])
    for name in sorted(DASH_OWNED):
        assert dash.count("live_data/sections/" + name) >= 3, (
            "Pages mirror trigger/allowlist/stage/proof incomplete", name
        )
        assert name in copied, f"Dashboard publisher does not copy {name}"
        assert '"' + "live_data/sections/" + name + '"' in public, (
            "Missing standalone public SHA proof", name
        )
    for name in sorted(MARKET_OWNED):
        assert market.count("live_data/sections/" + name) >= 3, (
            "Market mirror trigger/copy/allowlist incomplete", name
        )
    # Legacy narrative is source-derived, not a fresh policy/OIS view.
    assert "const ROOT='https://raw.githubusercontent.com/" in site
    assert "/main/live_data/sections/';" in site
    print("CONTROL_ROOM_ALL_14_FEED_MIRRORS_OWNED_GREEN", json.dumps({
        "mode": "READ_ONLY_NO_SCORE_EFFECT",
        "total": len(all_owned),
        "dashboard_publisher": sorted(DASH_OWNED),
        "market_publisher": sorted(MARKET_OWNED),
        "missing": [], "duplicate_owners": [],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
