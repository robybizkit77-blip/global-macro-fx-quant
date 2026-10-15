#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.request

CHAINS = {
    "USD": {
        "url": "https://www.tradingview.com/symbols/CBOT-ZQ1%21/contracts/",
        "anchor": "ZQV2026",
        "scanner_candidates": ["CBOT:ZQV2026", "CBOT:ZQ1!"],
    },
    "EUR": {
        "url": "https://www.tradingview.com/symbols/EUREX-FST31%21/contracts/",
        "anchor": "FST3U2026",
        "scanner_candidates": ["EUREX:FST3U2026", "EUREX:FFST3U2026", "EUREX:FST31!"],
    },
    "CHF": {
        "url": "https://www.tradingview.com/symbols/ICEEUR-SA31%21/contracts/",
        "anchor": "SA3U2026",
        "scanner_candidates": ["ICEEUR:SA3U2026", "ICEEUR:FSA3U2026", "ICEEUR:SA31!"],
    },
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
        "range": [0, max(0, len(symbols) - 1)],
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
    candidates = []
    for ccy, spec in CHAINS.items():
        html = fetch(spec["url"])
        idx = html.find(spec["anchor"])
        excerpt = ""
        if idx >= 0:
            excerpt = re.sub(r"\s+", " ", html[max(0, idx-250):idx+650])
        out[ccy] = {
            "anchor": spec["anchor"],
            "anchor_found": idx >= 0,
            "bytes": len(html.encode("utf-8")),
            "excerpt": excerpt[:450],
            "scanner_candidates": spec["scanner_candidates"],
            "scanner_matches": {},
        }
        candidates.extend(spec["scanner_candidates"])
    if not all(x["anchor_found"] for x in out.values()):
        raise SystemExit("One or more TradingView chains are not server-visible on runner")

    quotes = scan(candidates)
    for ccy, spec in CHAINS.items():
        matches = {s: quotes[s] for s in spec["scanner_candidates"] if s in quotes}
        out[ccy]["scanner_matches"] = matches
        usable = []
        for symbol, q in matches.items():
            close = q.get("close")
            if close is not None and 50.0 < float(close) < 120.0:
                usable.append(symbol)
        out[ccy]["usable_symbols"] = usable
        out[ccy]["status"] = "PASS" if usable else "NO_USABLE_SCANNER_SYMBOL"

    print(json.dumps(out, ensure_ascii=False, sort_keys=True))
    failed = [ccy for ccy, row in out.items() if row["status"] != "PASS"]
    if failed:
        raise SystemExit("No usable scanner symbol for: " + ",".join(failed))


if __name__ == "__main__":
    main()
