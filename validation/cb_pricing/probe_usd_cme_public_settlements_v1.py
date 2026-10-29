#!/usr/bin/env python3
"""Non-mutating proof of CME's public website ZQ settlement availability.

The historical CME delayed_snap API needs OAuth, entitlement and redistribution
license. This probe does NOT call that API. It only checks whether the public
product settlement webpage's JSON endpoint is usable for dated contracts.
An optional FOMC event-window check verifies the same contract IDs were present
on BOTH sides of the event without recording levels or calculating repricing.
It never prints or saves settlement prices, edits runtime, or certifies redistribution.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

WEB_ENDPOINT = "https://www.cmegroup.com/CmeWS/mvc/Settlements/Futures/Settlements/{product_id}/FUT"
SOURCE_URL = "https://www.cmegroup.com/markets/interest-rates/stirs/30-day-federal-fund.settlements.html"
CANDIDATES = ("305", "41")
MONTHS = {v: k for k, v in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                                     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}
CHICAGO = ZoneInfo("America/Chicago")


def bd_before(day: dt.date, n: int) -> dt.date:
    result = day
    for _ in range(n):
        result -= dt.timedelta(days=1)
        while result.weekday() > 4:
            result -= dt.timedelta(days=1)
    return result


def target_dates(now: dt.datetime) -> tuple[dt.date, dt.date, dt.date]:
    if now.tzinfo is None:
        raise ValueError("offset-aware timestamp required")
    # Public CME website settlement is posted only after midnight CT. Never
    # mix current intraday partial quotes and final settlements.
    local = now.astimezone(CHICAGO).date()
    t = bd_before(local, 1)
    return (t, bd_before(t, 1), bd_before(t, 5))


def classify(payload: object, requested: dt.date) -> dict:
    """Validate returned date and plausible *anonymous* per-contract levels."""
    if not isinstance(payload, dict):
        return {"state": "INVALID_PAYLOAD", "rows": 0}
    reported = payload.get("tradeDate")
    accepted_dates = (requested.strftime("%m/%d/%Y"), requested.isoformat())
    if str(reported) not in accepted_dates:
        return {"state": "DATE_MISMATCH", "rows": 0, "date_match": False}
    rows = payload.get("settlements")
    if not isinstance(rows, list):
        return {"state": "INVALID_ROWS", "rows": 0}
    symbols = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        m = re.fullmatch(r"([A-Z]{3})\s+(\d{2})", str(row.get("month", "")).strip().upper())
        if not m or m.group(1) not in MONTHS:
            continue
        year = 2000 + int(m.group(2))
        month = MONTHS[m.group(1)]
        if not (requested.year - 1 <= year <= requested.year + 5):
            continue
        settle = str(row.get("settle", "")).replace(",", "").strip()
        try:
            px = float(settle)
        except (TypeError, ValueError):
            continue
        if not (70.0 < px < 105.0):
            continue
        symbols.add(f"{year:04d}-{month:02d}")
    return {
        "state": "DATE_EXACT_CONTRACTS_PRESENT" if len(symbols) >= 9 else "INSUFFICIENT_DATED_CONTRACTS",
        "rows": len(symbols),
        "date_match": True,
        "contracts": symbols,
    }


def get_public_page_json(product_id: str, trade_date: dt.date) -> tuple[str, object | None]:
    params = urllib.parse.urlencode({
        "strategy": "DEFAULT",
        "tradeDate": trade_date.strftime("%m/%d/%Y"),
        "pageSize": 500,
    })
    url = WEB_ENDPOINT.format(product_id=product_id) + "?" + params
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; GMFQ-Internal-Source-Access-Probe/1.0)",
        "Accept": "application/json",
        "Referer": SOURCE_URL,
    })
    try:
        with urllib.request.urlopen(req, timeout=16) as response:
            if response.status != 200:
                return f"HTTP_{response.status}", None
            body = response.read(900_001)
            if len(body) > 900_000:
                return "RESPONSE_TOO_LARGE", None
        return "HTTP_200", json.loads(body)
    except urllib.error.HTTPError as exc:
        return f"HTTP_{exc.code}", None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return type(exc).__name__.upper(), None
    except (ValueError, UnicodeDecodeError):
        return "NON_JSON_RESPONSE", None


def probe(today: dt.datetime, event_date: dt.date | None = None) -> dict:
    dates = target_dates(today)
    # Product ID 305 is the current CME website product reference for ZQ;
    # 41 is a CME clearing/product code, not proof of the website product ID.
    # Only 305 is probed automatically; never fall back to 41 without review.
    pid = CANDIDATES[0]
    cache = {}
    def check_date(d: dt.date) -> tuple[dict, set[str]]:
        # Never persist returned settlement prices; only date/identity and
        # anonymous contract availability. Reuse requests across two windows.
        if d not in cache:
            access, payload = get_public_page_json(pid, d)
            c = classify(payload, d) if access == "HTTP_200" else {"state": "SOURCE_UNAVAILABLE", "rows": 0}
            contracts = c.pop("contracts", set())
            cache[d] = ({"date": d.isoformat(), "http_result": access, **c}, contracts)
        return cache[d]

    checks = []
    common: set[str] | None = None
    for d in dates:
        c, contracts = check_date(d)
        if c["state"] == "DATE_EXACT_CONTRACTS_PRESENT":
            common = contracts if common is None else common & contracts
        else:
            common = set()
        checks.append(c)
    event_audit = None
    if event_date is not None:
        chicago_day = today.astimezone(CHICAGO).date()
        before = bd_before(event_date, 1)
        audit = {
            "event": "FOMC_2026_10_28" if event_date.isoformat() == "2026-10-28" else "CUSTOM_DATED_EVENT",
            "event_date": event_date.isoformat(),
            "pre_event_trade_date": before.isoformat(),
            "post_event_trade_date": event_date.isoformat(),
            "levels_recorded": False,
            "repricing_computed": False,
            "official_pricing_promotion_allowed": False,
        }
        if chicago_day <= event_date:
            audit["status"] = "EVENT_NOT_YET_PAST"
            audit["checks"] = []
            audit["matched_contract_count"] = 0
        elif (chicago_day - event_date).days > 14:
            audit["status"] = "EVENT_WINDOW_EXPIRED_NO_NEW_REQUESTS"
            audit["checks"] = []
            audit["matched_contract_count"] = 0
        else:
            pre, pre_contracts = check_date(before)
            post, post_contracts = check_date(event_date)
            overlap = len(pre_contracts & post_contracts) if all(
                c["state"] == "DATE_EXACT_CONTRACTS_PRESENT" for c in (pre, post)
            ) else 0
            audit["checks"] = [pre, post]
            audit["matched_contract_count"] = overlap
            audit["status"] = ("DATE_MATCHED_EVENT_ACCESS_CANDIDATE" if overlap >= 9
                               else "EVENT_ACCESS_NOT_PROVEN")
        event_audit = audit
    shared = sorted(common or [])
    enough_shared = len(shared) >= 9
    all_valid = all(c["state"] == "DATE_EXACT_CONTRACTS_PRESENT" for c in checks)
    # A probe is NOT a license, a downstream market-data contract or an OIS feed.
    return {
        "schema": "GMFQ_CME_PUBLIC_ZQ_ACCESS_PROBE_V1",
        "status": "PUBLIC_EOD_ACCESS_CANDIDATE_FOUND" if all_valid and enough_shared else "PUBLIC_EOD_ACCESS_NOT_PROVEN",
        "product_id_candidate": pid,
        "product_identity_certified": False,
        "access_terms_or_redistribution_rights_certified": False,
        "official_OIS_status_change_allowed": False,
        "automated_price_ingestion_enabled": False,
        "source_url": SOURCE_URL,
        "trade_dates_checked": [x.isoformat() for x in dates],
        "checks": checks,
        "common_contract_count": len(shared),
        "price_levels_collected_or_logged": False,
        "fomc_event_window": event_audit,
        "interpretation": "Public website endpoint availability only, not a licensed official historical-data feed; requires source-identity and permitted-use review.",
        "licensed_api_note": "CME delayed_snap histSettlements requires OAuth + data entitlements and a Public Website (Delayed) Redistribution licence. Never call without credentials.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/tmp/cme-zq-public-source-proof.json")
    parser.add_argument("--summary")
    parser.add_argument("--event-date", type=dt.date.fromisoformat, default=None,
                        help="Optional completed issuer decision day; match contracts on event and prior session, no price capture")
    args = parser.parse_args()
    result = probe(dt.datetime.now(dt.timezone.utc), event_date=args.event_date)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("CME_PUBLIC_ZQ_SOURCE_PROOF", json.dumps(result, sort_keys=True))
    if args.summary:
        with Path(args.summary).open("a", encoding="utf-8") as fh:
            fh.write("### USD CME public EOD access probe (no market prices)\n\n")
            fh.write(f"Result: **{result['status']}**. No official-source activation or data redistribution.\n\n")
            fh.write("| Requested T/T-1/T-5 | Public HTTP | Returned-date validation | Contract rows |\n")
            fh.write("|---|---|---|---|\n")
            for r in result["checks"]:
                fh.write(f"| {r['date']} | {r['http_result']} | {r['state']} | {r['rows']} |\n")


if __name__ == "__main__":
    main()
