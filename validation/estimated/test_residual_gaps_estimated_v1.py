#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "validation/estimated/RESIDUAL_GAPS_ESTIMATED_CONTRACT_V1_2026-10-15.json"
SNAPSHOT = ROOT / "live_data/sections/ESTIMATED_RESIDUAL_GAPS.json"

c = json.loads(CONTRACT.read_text())
s = json.loads(SNAPSHOT.read_text())

assert c["status"] == "INFORMATIONAL_ONLY"
assert c["governance"]["official_runtime_untouched"] is True
assert s["official_lanes_untouched"] is True
for key in ("core_score_effect","bias_effect","sizing_effect","pair_engine_effect","forward_logger_effect"):
    assert s["governance"][key] == "NONE"
assert s["governance"]["backtest_eligible_as_official"] is False

jpy = s["lanes"]["JPY.reserve_balances"]
assert jpy["status"] in {"ESTIMATED_ACTIVE", "ESTIMATED_ACTIVE_AUTO_REFRESH_OFFICIAL_PROXY"}
if jpy["status"] == "ESTIMATED_ACTIVE":
    assert jpy["absolute_difference"] == 460.0
else:
    assert jpy["proxy_as_of"] >= "2026-09"
    assert jpy["proxy_value"] > 0
    assert jpy["official_canonical_untouched"] is True
    assert jpy["original_runtime_validation"]["period"] == "2026-08"
    assert jpy["original_runtime_validation"]["official_proxy_value"] == 3905362.0
    assert jpy["original_runtime_validation"]["absolute_difference"] == 460.0
    assert jpy["original_runtime_validation"]["original_runtime_vintage_equivalence_claimed"] is False
    assert jpy["continuity_anchor"]["period"] == "2026-09"
    assert jpy["continuity_anchor"]["expected_official_value"] == 3849859.0
    assert jpy["continuity_anchor"]["matched"] is True

assert s["lanes"]["CHF.credit"]["confidence"] == "B/C"
assert s["lanes"]["CHF.sight_deposits"]["confidence"] == "C"

brent = s["lanes"]["BRENT.market_proxy"]
assert brent["status"] in {"MARKET_PROXY_READY_NO_LIVE_VALUE", "MARKET_PROXY_ACTIVE_SECONDARY"}
if brent["status"] == "MARKET_PROXY_READY_NO_LIVE_VALUE":
    assert brent.get("value") is None
else:
    assert brent.get("value") is not None and brent["value"] > 0
    assert brent.get("change_1d_pct") is not None
    assert brent.get("official_canonical_untouched") is True
    assert brent.get("vendor_symbol") == "BZ=F"
    assert "Yahoo Finance" in brent.get("source", "")

print("PASS residual estimated gaps V1")
