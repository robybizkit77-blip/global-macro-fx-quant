#!/usr/bin/env python3
"""CME probe tests: no stale quote, wrong date, bad price or cross-date join."""
from __future__ import annotations

import datetime as dt

import probe_usd_cme_public_settlements_v1 as mod


def payload(date: str, n=13) -> dict:
    months = ["NOV", "DEC", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
              "JUL", "AUG", "SEP", "OCT", "NOV"]
    rows = []
    for i, month in enumerate(months[:n]):
        year = "26" if i < 2 else "27"
        rows.append({"month": f"{month} {year}", "settle": "96.7000"})
    return {"tradeDate": date, "settlements": rows}


def run():
    now = dt.datetime(2026, 10, 19, 10, 30, tzinfo=dt.timezone.utc)
    dates = mod.target_dates(now)
    assert dates == (dt.date(2026, 10, 16), dt.date(2026, 10, 15), dt.date(2026, 10, 9)), dates
    good = mod.classify(payload("10/16/2026"), dates[0])
    assert good["state"] == "DATE_EXACT_CONTRACTS_PRESENT", good
    assert good["rows"] == 12, good
    assert mod.classify(payload("10/15/2026"), dates[0])["state"] == "DATE_MISMATCH"
    assert mod.classify(payload("10/16/2026", n=5), dates[0])["state"] == "INSUFFICIENT_DATED_CONTRACTS"
    assert mod.classify({"tradeDate": "10/16/2026", "settlements": [{"month": "DEC 26", "settle": "N/A"}]}, dates[0])["state"] == "INSUFFICIENT_DATED_CONTRACTS"
    assert mod.classify([], dates[0])["state"] == "INVALID_PAYLOAD"
    saved = mod.get_public_page_json
    try:
        mod.get_public_page_json = lambda pid, date: ("HTTP_200", payload(date.strftime("%m/%d/%Y")))
        result = mod.probe(now)
        assert result["status"] == "PUBLIC_EOD_ACCESS_CANDIDATE_FOUND", result
        assert result["price_levels_collected_or_logged"] is False
        assert result["official_OIS_status_change_allowed"] is False
        assert result["access_terms_or_redistribution_rights_certified"] is False
        assert result["common_contract_count"] >= 9
        mod.get_public_page_json = lambda pid, date: ("HTTP_403", None)
        no_access = mod.probe(now)
        assert no_access["status"] == "PUBLIC_EOD_ACCESS_NOT_PROVEN"
        assert all(x["http_result"] == "HTTP_403" for x in no_access["checks"])
        mod.get_public_page_json = lambda pid, date: ("HTTP_200", payload("10/16/2026"))
        mismatched = mod.probe(now)
        assert mismatched["status"] == "PUBLIC_EOD_ACCESS_NOT_PROVEN", mismatched
    finally:
        mod.get_public_page_json = saved
    print("CME_PUBLIC_ZQ_DATE_AND_ENTITLEMENT_GATE_V1_PASS")


if __name__ == "__main__":
    run()
