#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULE_PATH = HERE / "build_cb_pricing_estimated_v1.py"
spec = importlib.util.spec_from_file_location("build_cb_pricing_estimated_v1", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def main():
    cb = json.loads((ROOT / "live_data/sections/NATIVE_CB_DATA.json").read_text(encoding="utf-8"))
    ois = json.loads((ROOT / "live_data/sections/OIS_DATA.json").read_text(encoding="utf-8"))
    current = json.loads((ROOT / "live_data/sections/CB_PRICING_ESTIMATED.json").read_text(encoding="utf-8"))
    built = mod.build(cb, ois)
    assert built == current, "Committed estimated snapshot drifted from deterministic builder"

    assert set(built["currencies"]) == {"USD", "EUR", "CHF", "NZD"}
    assert built["currencies"]["USD"]["status"] == "ESTIMATED_ACTIVE"
    assert built["currencies"]["EUR"]["status"] == "ESTIMATED_ACTIVE"
    assert built["currencies"]["CHF"]["status"] == "ESTIMATED_ACTIVE"
    assert built["currencies"]["NZD"]["status"] == "ESTIMATED_PARTIAL"
    assert built["currencies"]["NZD"]["horizons"]["6m"]["rate"] is None
    assert built["currencies"]["NZD"]["horizons"]["12m"]["rate"] is None

    for ccy, row in built["currencies"].items():
        assert row["official_ois_status"] == "WITHHELD"
        assert row["governance"]["informational_only"] is True
        assert row["governance"]["core_score_effect"] == "NONE"
        assert row["governance"]["bias_effect"] == "NONE"
        assert row["governance"]["sizing_effect"] == "NONE"
        assert row["governance"]["pair_engine_effect"] == "NONE"
        assert row["governance"]["backtest_eligible_as_official_ois"] is False
        assert row["change_1d_bp"] is None
        assert row["change_1w_bp"] is None

    # Never allow the estimated layer to shadow an official ACTIVE currency.
    x = mod.build_currency("USD", cb["USD"], {"status": "ACTIVE"})
    assert x["status"] == "NOT_APPLICABLE_OFFICIAL_ACTIVE"

    print("CB_PRICING_ESTIMATED_V1: PASS")


if __name__ == "__main__":
    main()
