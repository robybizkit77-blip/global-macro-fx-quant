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
    live = mod.load_live_overlay()
    nzd_proxy = mod.load_nzd_directional_proxy()
    built = mod.build(cb, ois, live, nzd_proxy)
    assert built == current, "Committed/generated estimated snapshot drifted from deterministic builder"

    assert set(built["currencies"]) == {"USD", "EUR", "CHF", "NZD"}
    for ccy in ("USD", "EUR", "CHF"):
        assert built["currencies"][ccy]["status"] in ("WITHHELD", "ESTIMATED_PARTIAL", "ESTIMATED_ACTIVE")
    assert built["currencies"]["NZD"]["status"] == "ESTIMATED_PARTIAL"
    assert built["currencies"]["NZD"]["horizons"]["6m"]["rate"] is None
    assert built["currencies"]["NZD"]["horizons"]["12m"]["rate"] is None

    if live is not None:
        for ccy in ("USD", "EUR", "CHF"):
            row = built["currencies"][ccy]
            raw = live["currencies"][ccy]
            if mod._live_usable(ccy, raw):
                assert row["input_mode"] == "LIVE_SECONDARY_OVERLAY", row
                assert row["method_id"] == mod.LIVE_METHOD_ID, row
                for h in ("3m", "6m", "12m"):
                    x = row["horizons"][h]
                    assert x["rate"] is not None, x
                    assert "!" not in str(x.get("contract") or ""), x
                    assert "!" not in str(x.get("symbol") or ""), x
            else:
                assert row["input_mode"] == "NATIVE_CB_FALLBACK", row
                assert row["method_id"] == mod.NATIVE_METHOD_ID, row
                ctx = row["secondary_futures_context"]
                assert ctx["status"] == "INDICATIVE_UNVERIFIED_TIMESTAMP", ctx
                assert ctx["observation_as_of"] is None, ctx
                assert ctx["substitutes_for_ois_level"] is False, ctx
                assert ctx["policy_delta_from_proxy_allowed"] is False, ctx
                assert ctx["repricing_from_proxy_allowed"] is False, ctx
                assert all(ctx["horizons"][h]["futures_price"] is not None for h in ("3m", "6m", "12m"))
        assert built["currencies"]["NZD"]["input_mode"] == "NATIVE_CB_FALLBACK"
        assert built["currencies"]["NZD"]["method_id"] == mod.NATIVE_METHOD_ID

    if nzd_proxy is not None:
        nzd = built["currencies"]["NZD"]
        proxy = nzd.get("market_direction_proxy")
        assert proxy is not None, nzd
        assert proxy["status"] == "LIVE_DIRECTIONAL_PROXY_READY", proxy
        assert proxy["substitutes_for_ois_level"] is False, proxy
        assert proxy["policy_delta_from_proxy_allowed"] is False, proxy
        assert "Bank" in proxy["instrument"] and "Bill Futures" in proxy["instrument"], proxy
        assert all(proxy["horizons"][h]["implied_bank_bill_rate"] is not None for h in ("3m", "6m", "12m")), proxy
        # The ASX proxy must never fill or mutate the native OIS curve.
        assert nzd["horizons"]["3m"]["rate"] == 3.0, nzd
        assert nzd["horizons"]["6m"]["rate"] is None, nzd
        assert nzd["horizons"]["12m"]["rate"] is None, nzd
        assert nzd["direction_vs_policy"] == "UP", nzd

    # A priceValidUntil timestamp MUST NOT be accepted as trade/quote as-of.
    sample = {"status": "LIVE_SECONDARY_READY", "horizons": {
        h: {"rate": 4.0, "contract": "ZQZ2026", "symbol": "CBOT:ZQZ2026",
            "quote_as_of": "2026-10-19", "price_valid_until": "2026-10-19T21:00:00Z"}
        for h in ("3m", "6m", "12m")
    }}
    assert mod._live_usable("USD", sample) is False
    for h in sample["horizons"]:
        sample["horizons"][h]["quote_timestamp_verified"] = True
    assert mod._live_usable("USD", sample) is True

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
    x = mod.build_currency("USD", cb["USD"], {"status": "ACTIVE"}, None)
    assert x["status"] == "NOT_APPLICABLE_OFFICIAL_ACTIVE"

    print("CB_PRICING_ESTIMATED_V1: PASS")


if __name__ == "__main__":
    main()
