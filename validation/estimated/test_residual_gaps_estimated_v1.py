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
for key in ("core_score_effect","bias_effect","sizing_effect","pair_engine_effect","forward_logger_effect"):
    assert s["governance"][key] == "NONE"
assert s["lanes"]["JPY.reserve_balances"]["status"] == "ESTIMATED_ACTIVE"
assert s["lanes"]["JPY.reserve_balances"]["absolute_difference"] == 460.0
assert s["lanes"]["CHF.credit"]["confidence"] == "B/C"
assert s["lanes"]["CHF.sight_deposits"]["confidence"] == "C"
assert s["lanes"]["BRENT.market_proxy"]["value"] is None
assert s["lanes"]["BRENT.market_proxy"]["status"] == "MARKET_PROXY_READY_NO_LIVE_VALUE"
print("PASS residual estimated gaps V1")
