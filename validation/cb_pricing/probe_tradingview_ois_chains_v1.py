#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.request

CHAINS = {
    "USD": ("https://www.tradingview.com/symbols/CBOT-ZQ1%21/contracts/", "ZQV2026", "CBOT:ZQV2026"),
    "EUR": ("https://www.tradingview.com/symbols/EUREX-FST31%21/contracts/", "FST3U2026", "EUREX:FST3U2026"),
    "CHF": ("https://www.tradingview.com/symbols/ICEEUR-SA31%21/contracts/", "SA3U2026", "ICEEUR:SA3U2026"),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/155 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
SCANNER_URL = "https://scanner.tradingview.com/futures/scan"
COLUMNS = ["name", "description", "close", "change", "change_abs", "Perf.W", "exchange"]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", errors="replace")
        if r.status != 200:
            raise SystemExit(f"HTTP {r.status} {url}")
        return body


def scan(symbols: list[str]) -> dict[str, dict]:
    payload = {
        "symbols": {"tickers": symbols, "query": {"types": []}},
        "columns": COLUMNS,
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, len(symbols) - 1],
    }
    req = urllib.request.Request(
        SCANNER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={**HEADERS, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
        if r.status != 200:
            raise SystemExit(f"scanner HTTP {r.status}")
    out = {}
    for row in data.get("data") or []:
        values = row.get("d") or []
        out[row.get("s")] = dict(zip(COLUMNS, values))
    return out


def main():
    out = {}
    symbols = []
    for ccy, (url, anchor, symbol) in CHAINS.items():
        html = fetch(url)
        idx = html.find(anchor)
        excerpt = ""
        if idx >= 0:
            excerpt = re.sub(r"\s+", " ", html[max(0, idx-300):idx+800])
        out[ccy] = {
            "status": "PASS" if idx >= 0 else "ANCHOR_NOT_FOUND",
            "bytes": len(html.encode("utf-8")),
            "anchor": anchor,
            "anchor_found": idx >= 0,
            "full_symbol": symbol,
            "excerpt": excerpt[:500],
        }
        symbols.append(symbol)
    if not all(x["anchor_found"] for x in out.values()):
        raise SystemExit("One or more TradingView chains are not server-visible on runner")

    quotes = scan(symbols)
    for ccy, (_, _, symbol) in CHAINS.items():
        q = quotes.get(symbol)
        if not q:
            raise SystemExit(f"{ccy}: scanner did not return {symbol}")
        close = q.get("close")
        if close is None or not (50.0 < float(close) < 120.0):
            raise SystemExit(f"{ccy}: implausible scanner close {close}")
        out[ccy]["scanner"] = q

    print(json.dumps(out, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
