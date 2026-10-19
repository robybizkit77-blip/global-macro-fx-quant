#!/usr/bin/env python3
"""Read-only CHF SARON product-identity and public-source availability probe.

ICE SA3 and Eurex FSR3 are separate instruments. Legacy Eurex FSO3 was
delisted in 2021; do not search or combine its settlement history with FSR3.

The public exchange contract page may be accessible while reproducible T/T-1/T-5
daily settlement files remain unavailable. Product identity and a single quote
page can never activate CHF OIS or authorize market-data redistribution.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import urllib.error
import urllib.request
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo

ICE_URL = "https://www.ice.com/products/72270612/Three-Month-Saron-Index-Futures-Contract"
EUREX_URL = "https://www.eurex.com/ex-en/markets/int/mon/saron-futures/saron/3M-SARON-Futures-1410330"
ICE_LICENSE_URL = "https://www.ice.com/report-center/data-subscription"
EUREX_TERMS_URL = "https://www.eurex.com/ex-en/data/trading-files"
IDENTITY = {
    "ICE": {"symbol": "SA3", "required": ("Three Month Saron", "SA3")},
    "EUREX": {"symbol": "FSR3", "required": ("SARON", "FSR3", "DE000A3CTV01")},
}


def fetch(url: str) -> tuple[str, str]:
    req = urllib.request.Request(
        url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; GMFQ-CHF-Source-Probe/1.0)",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            if res.status != 200:
                return "HTTP_" + str(res.status), ""
            body = res.read(1_400_001)
            if len(body) > 1_400_000:
                return "RESPONSE_TOO_LARGE", ""
            return "HTTP_200", body.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return "HTTP_" + str(exc.code), ""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return type(exc).__name__.upper(), ""


def check_identity(exchange: str, http_result: str, html: str) -> dict:
    expected = IDENTITY[exchange]
    normalized = unescape(html)
    product_verified = http_result == "HTTP_200" and all(
        token.lower() in normalized.lower() for token in expected["required"]
    )
    # A scraped headline "settlement" or a quoted single maturity is not
    # evidence of three same-date official historical settlements.
    # Never emit market price fields from this probe.
    date_match = re.search(r"Trading\s+Date\s*[:\s]*([0-3]?\d/[01]?\d/20\d{2})", normalized, re.I)
    displayed_date = None
    if date_match:
        try:
            displayed_date = dt.datetime.strptime(date_match.group(1), "%d/%m/%Y").date().isoformat()
        except ValueError:
            pass
    has_quoted_settle_header = bool(re.search(r"D\.\s*Settle", normalized, re.I))
    zero_liquidity_text = bool(re.search(r"\bVolume\s+0\b.*?\bOpen\s+Interest\s+0\b", normalized, re.I | re.S))
    return {
        "symbol_expected": expected["symbol"],
        "http_result": http_result,
        "contract_identity_visible": product_verified,
        "displayed_trading_date_uncertified": displayed_date,
        "daily_settlement_column_visible": has_quoted_settle_header,
        "zero_volume_and_open_interest_text_detected": zero_liquidity_text,
        "dated_T_T1_T5_settlement_history_certified": False,
        "market_prices_captured_or_exported": False,
    }


def probe() -> dict:
    checks = {}
    for exchange, url in (("ICE", ICE_URL), ("EUREX", EUREX_URL)):
        status, html = fetch(url)
        checks[exchange] = {"source_url": url, **check_identity(exchange, status, html)}
    return {
        "schema": "GMFQ_CHF_SARON_PUBLIC_SOURCE_PROBE_V1",
        "status": "CONTRACT_IDENTITIES_VISIBLE_BUT_EOD_HISTORY_NOT_CERTIFIED"
        if all(c["contract_identity_visible"] for c in checks.values())
        else "CONTRACT_IDENTITY_OR_ACCESS_INCOMPLETE",
        "currency": "CHF",
        "legacy_eurex_code": "FSO3",
        "legacy_eurex_contract_status": "DISCONTINUED_2021",
        "current_eurex_code": "FSR3",
        "ice_code": "SA3",
        "ice_and_eurex_are_interchangeable": False,
        "source_checks": checks,
        "historical_same_contracts_T_T1_T5_proven": False,
        "redistribution_rights_or_subscription_certified": False,
        "market_prices_captured_or_exported": False,
        "operational_status_promotion_allowed": False,
        "official_ois_data_mutation_allowed": False,
        "licence_references": [ICE_LICENSE_URL, EUREX_TERMS_URL],
        "activation_gate": "Complete independent exchange-specific T/T-1/T-5 dated settlement series, methodology and source-entitlement certification. Never join ICE SA3 with Eurex FSR3.",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="/tmp/chf-saron-source-proof.json")
    p.add_argument("--summary")
    a = p.parse_args()
    result = probe()
    Path(a.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("CHF_SARON_SOURCE_PROOF", json.dumps(result, sort_keys=True))
    if a.summary:
        with Path(a.summary).open("a", encoding="utf-8") as out:
            out.write("### CHF SARON exchange source identities — non-trading probe\n\n")
            for exch, row in result["source_checks"].items():
                out.write(f"- {exch} {row['symbol_expected']}: {row['http_result']}; "
                          f"contract identity visible={row['contract_identity_visible']}; "
                          f"displayed trading date (not certified)={row['displayed_trading_date_uncertified']}\n")
            out.write("\n**No historical T/T-1/T-5, prices, redistribution licence or CHF OIS promotion certified.**\n")


if __name__ == "__main__":
    main()
