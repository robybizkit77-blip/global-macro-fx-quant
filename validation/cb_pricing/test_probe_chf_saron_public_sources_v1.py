#!/usr/bin/env python3
"""CHF product-identity, stale product quote and no-price-leak fixture tests."""
from __future__ import annotations

import json

from probe_chf_saron_public_sources_v1 import check_identity, probe


def main():
    ice = "<h1>Three Month Saron Index Futures</h1><span>SA3</span>"
    eurex = """<h1>3M SARON Futures (FSR3)</h1><div>DE000A3CTV01</div>
       <div>Trading Date 09/09/2026</div>
       <table><th>D. Settle</th><td>99.99</td></table>"""
    i = check_identity("ICE", "HTTP_200", ice)
    e = check_identity("EUREX", "HTTP_200", eurex)
    assert i["contract_identity_visible"], i
    assert e["contract_identity_visible"], e
    assert e["displayed_trading_date_uncertified"] == "2026-09-09"
    assert e["daily_settlement_column_visible"] is True
    assert not e["dated_T_T1_T5_settlement_history_certified"]
    assert not e["market_prices_captured_or_exported"]
    assert "99.99" not in json.dumps(e)
    assert not check_identity("EUREX", "HTTP_200", eurex.replace("FSR3", "FSO3"))["contract_identity_visible"]
    assert not check_identity("ICE", "HTTP_403", ice)["contract_identity_visible"]
    assert not check_identity("EUREX", "HTTP_200", "<h1>3M SARON Futures (FSO3)</h1>")["contract_identity_visible"]

    import probe_chf_saron_public_sources_v1 as p
    fetch = p.fetch
    try:
        def canned(url):
            return "HTTP_200", ice if "ice.com" in url else eurex
        p.fetch = canned
        result = probe()
        assert result["status"] == "CONTRACT_IDENTITIES_VISIBLE_BUT_EOD_HISTORY_NOT_CERTIFIED"
        assert result["current_eurex_code"] == "FSR3"
        assert result["legacy_eurex_contract_status"] == "DISCONTINUED_2021"
        assert not result["operational_status_promotion_allowed"]
        assert not result["redistribution_rights_or_subscription_certified"]
        assert not result["historical_same_contracts_T_T1_T5_proven"]
        assert not result["ice_and_eurex_are_interchangeable"]
        assert "99.99" not in json.dumps(result)

        p.fetch = lambda url: ("HTTP_403", "")
        blocked = probe()
        assert blocked["status"] == "CONTRACT_IDENTITY_OR_ACCESS_INCOMPLETE"
    finally:
        p.fetch = fetch
    print("CHF_SARON_EXCHANGE_IDENTITY_GOVERNANCE_V1_PASS")


if __name__ == "__main__":
    main()
