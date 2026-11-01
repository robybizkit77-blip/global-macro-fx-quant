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
    assert built["currencies"]["USD"]["status"] == "ESTIMATED_ACTIVE"
    assert built["currencies"]["EUR"]["status"] == "ESTIMATED_ACTIVE"
    assert built["currencies"]["CHF"]["status"] == "ESTIMATED_ACTIVE"
    assert built["currencies"]["NZD"]["status"] == "ESTIMATED_PARTIAL"
    assert built["currencies"]["NZD"]["horizons"]["6m"]["rate"] is None
    assert built["currencies"]["NZD"]["horizons"]["12m"]["rate"] is None

    if live is not None:
        for ccy in ("USD", "EUR", "CHF"):
            row = built["currencies"][ccy]
            assert row["input_mode"] in ("LIVE_SECONDARY_OVERLAY",
                                         "LIVE_SECONDARY_CONFLICT_INDICATIVE"), row
            if row["input_mode"] == "LIVE_SECONDARY_CONFLICT_INDICATIVE":
                assert row["source_conflict_status"] == "UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT"
                assert row["source_conflict_keys"]
                assert row["source_quality"] == "SECONDARY_CONFLICTED_INDICATIVE_NOT_OIS"
                assert row["confidence_grade"] == "C"
                assert row["direction_vs_policy"] == "WITHHELD"
                assert all(row["horizons"][h]["policy_delta_bp"] is None
                           for h in ("3m", "6m", "12m"))
            assert row["method_id"] == "TRADINGVIEW_DATED_FUTURES_SSR_V2", row
            assert row["method_id"] == mod.LIVE_METHOD_ID, row
            assert row["freshness_status"] in (
                "LIVE_OR_RECENT_SESSION", "SAME_DAY_SOURCE_CONFLICT_UNRESOLVED"), row
            for h in ("3m", "6m", "12m"):
                x = row["horizons"][h]
                assert x["rate"] is not None, x
                assert "!" not in str(x.get("contract") or ""), x
                assert "!" not in str(x.get("symbol") or ""), x
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

    # EUR native quote is date-ambiguous and over a month old. If the live
    # overlay fails, do not resurrect that snapshot as active market pricing.
    eur_without_live = mod.build_currency("EUR", cb["EUR"], {"status": "WITHHELD"}, None)
    assert eur_without_live["status"] == "WITHHELD", eur_without_live
    assert eur_without_live["freshness_status"] == "STALE_SOURCE_WITHHELD", eur_without_live
    assert all(eur_without_live["horizons"][h]["rate"] is None for h in ("3m", "6m", "12m"))
    assert eur_without_live["policy_rate"] == cb["EUR"]["rate"]
    assert eur_without_live["governance"]["core_score_effect"] == "NONE"

    # Even a strictly dated quote older than five days is not a fresh fallback.
    from datetime import date, timedelta
    from copy import deepcopy
    ecb_old = deepcopy(cb["EUR"])
    ecb_old["market_pricing"]["as_of"] = (date.today() - timedelta(days=6)).isoformat()
    assert mod.build_currency("EUR", ecb_old, {"status": "WITHHELD"}, None)["status"] == "WITHHELD"
    ecb_recent = deepcopy(cb["EUR"])
    ecb_recent["market_pricing"]["as_of"] = date.today().isoformat()
    assert mod.build_currency("EUR", ecb_recent, {"status": "WITHHELD"}, None)["status"] == "ESTIMATED_ACTIVE"

    # Never allow the estimated layer to shadow an official ACTIVE currency.
    x = mod.build_currency("USD", cb["USD"], {"status": "ACTIVE"}, None)
    assert x["status"] == "NOT_APPLICABLE_OFFICIAL_ACTIVE"

    # Quote freshness cannot be inferred from Offer.priceValidUntil alone.
    import sys
    from datetime import date
    sys.path.insert(0, str(HERE))
    from collect_cb_pricing_estimated_live_v1 import parse_quote
    offer = ('ZQZ2026 <script>{"offers":{"price":"95.93",'
             '"priceCurrency":"USD","priceValidUntil":"2026-10-16T21:40:22Z"}}</script>')
    bare = parse_quote(offer, "ZQZ2026", date(2026, 10, 19))
    assert bare["quote_timestamp_verified"] is False and bare["quote_as_of"] is None
    bar = '"daily_bar":{"close":"95.93","data_update_time":"1792186822.720112"}'
    verified = parse_quote(offer + bar, "ZQZ2026", date(2026, 10, 19))
    assert verified["quote_timestamp_verified"] is True, verified
    assert verified["quote_as_of"] == "2026-10-16", verified
    mismatched = parse_quote(offer + bar.replace("95.93", "95.94"), "ZQZ2026", date(2026, 10, 19))
    assert mismatched["quote_timestamp_verified"] is False, mismatched


    # ICE official rule: SA3 contract names mark the START of compounded
    # 3-month SARON accrual, not the final settlement date.
    from collect_cb_pricing_estimated_live_v1 import saron_window, select_contracts
    futures = []
    for contract in ("SA3U2026","SA3Z2026","SA3H2027",
                     "SA3M2027","SA3U2027","SA3Z2027"):
        begin, end = saron_window(contract)
        futures.append({"contract":contract,"symbol":"ICEEUR:"+contract,
                        "expiration":end, "description":contract})
    assert saron_window("SA3U2026") == (date(2026,9,16), date(2026,12,15))
    assert saron_window("SA3Z2026") == (date(2026,12,16), date(2027,3,16))
    assert saron_window("SA3H2027") == (date(2027,3,17), date(2027,6,15))
    selected=select_contracts(futures,date(2026,10,30),currency="CHF")
    assert {h:x["contract"] for h,x in selected.items()} == {
        "3m":"SA3Z2026","6m":"SA3H2027","12m":"SA3U2027"
    },selected
    assert selected["6m"]["accrual_start"] == date(2027,3,17)
    assert not any(x["contract"]=="SA3U2026" for x in selected.values())
    misdated=[{**x,"expiration":date(2026,12,1)} if x["contract"]=="SA3H2027"
              else x for x in futures]
    assert select_contracts(misdated,date(2026,10,30),currency="CHF")["6m"]["contract"]=="SA3M2027"
    try:
        saron_window("SA3V2026")
        raise AssertionError("monthly/unknown SARON contract accepted")
    except ValueError:
        pass

    print("CB_PRICING_ESTIMATED_V1: PASS")


if __name__ == "__main__":
    main()
