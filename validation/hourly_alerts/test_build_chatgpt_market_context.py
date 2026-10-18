#!/usr/bin/env python3
"""Fail-closed ChatGPT market-context regression tests, safe on future days."""
from __future__ import annotations

import copy
import importlib.util
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


HERE = Path(__file__).resolve().parent


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


snapshot = imported("certified_snapshot_context_test", HERE / "build_certified_alert_snapshot.py")
context = imported("chatgpt_context_test", HERE / "build_chatgpt_market_context.py")


def main():
    today = datetime.now(ZoneInfo("Europe/Rome")).date()
    receipt = snapshot.build(today)
    inputs = (
        context.read_json(context.SECTIONS / "OIS_OPERATIONAL_VIEW.json"),
        context.read_json(context.SECTIONS / "NATIVE_RATES_DATA.json"),
        context.read_json(context.SECTIONS / "V250_COT_CHART_DATA.json"),
        context.read_json(context.SECTIONS / "PAIR_SETUP_OPERATIONAL_VIEW.json"),
        context.read_json(context.SECTIONS / "ECB_G8_PRICE_HISTORY.json"),
    )
    data = context.build(receipt, *inputs)
    assert data["schema"] == context.SCHEMA
    assert data["policy"]["no_inference_of_post_event_reaction"] is True
    assert data["evaluation_date_europe_rome"] == today.isoformat()
    assert data["generated_at_utc"] == receipt["generated_at_utc"]
    for name, lane in (("ois_official", "ois"), ("government_rates", "g8_bonds")):
        for ccy in context.CCYS:
            row = data["sections"][name][ccy]
            eligibility = receipt["lanes"][lane][ccy]["alert_eligible"] is True
            if not eligibility:
                assert row["state"] != "AVAILABLE_CERTIFIED", (name, ccy)
                assert "horizons" not in row
                assert "government_2y_pct" not in row
            elif row["state"] == "AVAILABLE_CERTIFIED":
                assert row["as_of"] == receipt["lanes"][lane][ccy]["as_of"]
                assert row["source"] == receipt["lanes"][lane][ccy]["source"]
    for ccy in ("USD", "EUR", "CHF", "NZD"):
        assert data["sections"]["ois_official"][ccy]["state"] != "AVAILABLE_CERTIFIED"
        assert "horizons" not in data["sections"]["ois_official"][ccy]
    cot = data["sections"]["cot_weekly"]
    if receipt["lanes"]["cot"]["alert_eligible"]:
        assert cot["state"] == "AVAILABLE_CERTIFIED"
        assert len(cot["currencies"]) == 8
    else:
        assert cot["state"] != "AVAILABLE_CERTIFIED"
        assert "currencies" not in cot
    fx = data["sections"]["fx_ecb_fixing"]
    if receipt["lanes"]["fx"]["alert_eligible"]:
        assert fx["state"] == "AVAILABLE_CERTIFIED"
        assert len(fx["pairs"]) == 28
        assert fx["kind"] == "ECB_EUR_BASED_REFERENCE_FIXINGS_NOT_INTRADAY_SPOT_OR_CLOSE"
        price_row = inputs[-1]["rows"][-1]
        assert abs(fx["pairs"]["EURUSD"]["fixing"] - price_row["USD"]) < 0.00002
    else:
        assert fx["state"] != "AVAILABLE_CERTIFIED"
        assert "pairs" not in fx
    assert data["unavailable"]["credit_spreads"] == "WITHHELD_NO_CERTIFIED_ADAPTER"

    # Synthetic exact-boundary conventions do not depend on next Friday's CFTC data.
    cot_receipt = copy.deepcopy(receipt)
    cot_receipt["lanes"]["cot"].update(
        {"state": "AVAILABLE_CERTIFIED", "alert_eligible": True,
         "as_of": inputs[2]["USD"]["dates"][-1],
         "source": "CFTC Legacy Commitments of Traders (weekly, Tuesday position date)"}
    )
    synthetic = copy.deepcopy(inputs[2])
    synthetic["USD"]["percentile"][-1] = 79.8
    synthetic["AUD"]["netoi"][-1] = -29.96  # displayed -30.0 qualifies
    tested = context.cot_view(cot_receipt, synthetic)
    assert tested["state"] == "AVAILABLE_CERTIFIED"
    assert tested["currencies"]["USD"]["percentile_104w_rounded"] == 80
    assert tested["currencies"]["USD"]["signal"] == "EXTREME_LONG"
    assert tested["currencies"]["AUD"]["net_oi_pct"] == -30.0
    assert tested["currencies"]["AUD"]["net_oi_alert_abs_ge_30pct"] is True

    # A fabricated newer source date is never promoted using an old certificate.
    mismatched = copy.deepcopy(inputs[0])
    mismatched["currencies"]["JPY"]["as_of"] = "2099-01-01"
    rejected = context.ois_view(receipt, mismatched)
    assert rejected["JPY"]["state"] != "AVAILABLE_CERTIFIED"
    print("CHATGPT_MARKET_CONTEXT_GUARDRAILS_PASS")


if __name__ == "__main__":
    main()
