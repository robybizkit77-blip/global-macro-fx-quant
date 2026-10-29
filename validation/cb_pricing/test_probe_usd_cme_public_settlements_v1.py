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
    assert good["rows"] == 13, good
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
        assert result["weekly_same_contract_access_proven"] is True
        # Public page may expose the event pair but not T-5 on same basis.
        def short_lookback(pid,date):
            if date==dates[2]:
                return ("HTTP_200",{"tradeDate":date.strftime("%m/%d/%Y"),"settlements":[]})
            return ("HTTP_200",payload(date.strftime("%m/%d/%Y")))
        mod.get_public_page_json = short_lookback
        partial = mod.probe(now)
        assert partial["status"] == "PUBLIC_EOD_PARTIAL_ROLLING_ACCESS"
        assert partial["latest_two_dates_accessible"] is True
        assert partial["weekly_same_contract_access_proven"] is False
        assert partial["checks"][2]["rows"] == 0

        mod.get_public_page_json = lambda pid, date: ("HTTP_403", None)
        no_access = mod.probe(now)
        assert no_access["status"] == "PUBLIC_EOD_ACCESS_NOT_PROVEN"
        assert all(x["http_result"] == "HTTP_403" for x in no_access["checks"])
        mod.get_public_page_json = lambda pid, date: ("HTTP_200", payload("10/16/2026"))
        mismatched = mod.probe(now)
        assert mismatched["status"] == "PUBLIC_EOD_ACCESS_NOT_PROVEN", mismatched
        # 29 Oct Chicago date: dated 27 Oct pre-FOMC and 28 Oct post-FOMC
        # settlements must BOTH exist and share the SAME listed contracts.
        event = dt.date(2026,10,28)
        event_now = dt.datetime(2026,10,29,8,50,tzinfo=dt.timezone.utc)
        calls = []
        def good_event(pid,date):
            calls.append(date.isoformat())
            return ("HTTP_200", payload(date.strftime("%m/%d/%Y")))
        mod.get_public_page_json = good_event
        checked = mod.probe(event_now, event_date=event)
        assert checked["fomc_event_window"]["status"] == "DATE_MATCHED_EVENT_ACCESS_CANDIDATE", checked
        assert checked["fomc_event_window"]["matched_contract_count"] >= 9
        assert [x["date"] for x in checked["fomc_event_window"]["checks"]] == ["2026-10-27","2026-10-28"]
        assert checked["fomc_event_window"]["levels_recorded"] is False
        assert checked["fomc_event_window"]["repricing_computed"] is False
        assert checked["fomc_event_window"]["official_pricing_promotion_allowed"] is False
        assert checked["price_levels_collected_or_logged"] is False
        assert len(calls)==3, "same event dates must be read only once when rolling probe overlaps"
        # Even one incorrectly dated CME response fails closed.
        mod.get_public_page_json = lambda pid,date: ("HTTP_200", payload("10/27/2026"))
        bad = mod.probe(event_now, event_date=event)
        assert bad["fomc_event_window"]["status"] == "EVENT_ACCESS_NOT_PROVEN", bad
        assert bad["fomc_event_window"]["matched_contract_count"] == 0
        # HTTP 403 is a source failure, not an artificial unchanged quote.
        mod.get_public_page_json = lambda pid,date: ("HTTP_403", None)
        blocked = mod.probe(event_now, event_date=event)
        assert blocked["fomc_event_window"]["status"] == "EVENT_ACCESS_NOT_PROVEN"
        assert all(x["http_result"]=="HTTP_403" for x in blocked["fomc_event_window"]["checks"])
        # Do not query future FOMC settlements or repeatedly probe an expired event.
        calls.clear()
        mod.get_public_page_json = good_event
        early = mod.probe(dt.datetime(2026,10,28,16,0,tzinfo=dt.timezone.utc),event_date=event)
        assert early["fomc_event_window"]["status"] == "EVENT_NOT_YET_PAST"
        assert "2026-10-28" not in calls
        late = mod.probe(dt.datetime(2026,11,16,14,0,tzinfo=dt.timezone.utc),event_date=event)
        assert late["fomc_event_window"]["status"] == "EVENT_WINDOW_EXPIRED_NO_NEW_REQUESTS"
        assert late["fomc_event_window"]["checks"] == []
    finally:
        mod.get_public_page_json = saved
    print("CME_PUBLIC_ZQ_DATE_AND_ENTITLEMENT_GATE_V1_PASS")


if __name__ == "__main__":
    run()
