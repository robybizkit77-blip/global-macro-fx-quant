#!/usr/bin/env python3
"""Deterministic guardrail tests against the real canonical source snapshots."""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path


HERE = Path(__file__).resolve().parent


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


snapshot = imported("certified_snapshot_context_test", HERE / "build_certified_alert_snapshot.py")
context = imported("chatgpt_context_test", HERE / "build_chatgpt_market_context.py")


def build_for(day):
    receipt = snapshot.build(day)
    data = context.build(
        receipt,
        context.read_json(context.SECTIONS / "OIS_OPERATIONAL_VIEW.json"),
        context.read_json(context.SECTIONS / "NATIVE_RATES_DATA.json"),
        context.read_json(context.SECTIONS / "V250_COT_CHART_DATA.json"),
        context.read_json(context.SECTIONS / "PAIR_SETUP_OPERATIONAL_VIEW.json"),
        context.read_json(context.SECTIONS / "ECB_G8_PRICE_HISTORY.json"),
    )
    return receipt, data


def main():
    receipt, data = build_for(date(2026, 10, 18))
    assert data["schema"] == context.SCHEMA
    assert data["policy"]["no_inference_of_post_event_reaction"] is True
    assert data["evaluation_date_europe_rome"] == "2026-10-18"
    assert data["generated_at_utc"] == receipt["generated_at_utc"]
    ois = data["sections"]["ois_official"]
    assert ois["JPY"]["state"] == "AVAILABLE_CERTIFIED"
    assert ois["CAD"]["state"] == "AVAILABLE_CERTIFIED"
    assert ois["AUD"]["state"] == "AVAILABLE_CERTIFIED"
    assert len(ois["CAD"]["horizons"]) == 3
    assert "change_1w_bp" in ois["CAD"]["horizons"]["3m"]
    assert ois["GBP"]["state"] == "STALE"  # 14 Oct as-of, 18 Oct Sunday = 4 days
    assert "horizons" not in ois["GBP"]
    for ccy in ("USD", "EUR", "CHF", "NZD"):
        assert ois[ccy]["state"] == "UNAVAILABLE"
        assert "horizons" not in ois[ccy]  # Never promote secondary/proxy OIS.
    rates = data["sections"]["government_rates"]
    assert rates["USD"]["state"] == "AVAILABLE_CERTIFIED"
    assert rates["USD"]["government_2y_pct"] > 0
    assert rates["USD"]["government_10y_pct"] > 0
    assert rates["CHF"]["state"] == "STALE"
    assert "government_2y_pct" not in rates["CHF"]
    cot = data["sections"]["cot_weekly"]
    assert cot["state"] == "AVAILABLE_CERTIFIED"
    assert cot["as_of"] == "2026-10-13"
    assert len(cot["currencies"]) == 8
    assert cot["currencies"]["USD"]["percentile_104w_rounded"] == 80
    assert cot["currencies"]["USD"]["signal"] == "EXTREME_LONG"
    assert cot["currencies"]["AUD"]["net_oi_alert_abs_ge_30pct"] is True
    assert cot["currencies"]["GBP"]["net_oi_alert_abs_ge_30pct"] is True
    fx = data["sections"]["fx_ecb_fixing"]
    assert fx["state"] == "AVAILABLE_CERTIFIED"
    assert fx["as_of"] == "2026-10-16"
    assert len(fx["pairs"]) == 28
    assert fx["kind"] == "ECB_EUR_BASED_REFERENCE_FIXINGS_NOT_INTRADAY_SPOT_OR_CLOSE"
    assert abs(fx["pairs"]["EURUSD"]["fixing"] - 1.1253) < 0.00001
    assert data["unavailable"]["credit_spreads"] == "WITHHELD_NO_CERTIFIED_ADAPTER"
    assert data["unavailable"]["macro_release_event"] == "UNAVAILABLE"

    # All sources become stale, but old numeric values may not leak into alerts.
    _, stale = build_for(date(2026, 11, 5))
    assert all(x["state"] != "AVAILABLE_CERTIFIED" for x in stale["sections"]["ois_official"].values())
    assert all("horizons" not in x for x in stale["sections"]["ois_official"].values())
    assert all("government_2y_pct" not in x for x in stale["sections"]["government_rates"].values())
    assert stale["sections"]["cot_weekly"]["state"] != "AVAILABLE_CERTIFIED"
    assert stale["sections"]["fx_ecb_fixing"]["state"] != "AVAILABLE_CERTIFIED"
    assert "pairs" not in stale["sections"]["fx_ecb_fixing"]
    print("CHATGPT_MARKET_CONTEXT_GUARDRAILS_PASS")


if __name__ == "__main__":
    main()
