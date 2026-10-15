#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.request

CHAINS = {
    "USD": ("https://www.tradingview.com/symbols/CBOT-ZQ1%21/contracts/", "ZQV2026"),
    "EUR": ("https://www.tradingview.com/symbols/EUREX-FST31%21/contracts/", "FST3U2026"),
    "CHF": ("https://www.tradingview.com/symbols/ICEEUR-SA31%21/contracts/", "SA3U2026"),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/155 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", errors="replace")
        if r.status != 200:
            raise SystemExit(f"HTTP {r.status} {url}")
        return body


def main():
    out = {}
    for ccy, (url, anchor) in CHAINS.items():
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
            "contains_next_data": "__NEXT_DATA__" in html,
            "contains_contracts_word": "contracts" in html.lower(),
            "excerpt": excerpt[:900],
        }
    print(json.dumps(out, ensure_ascii=False, sort_keys=True))
    if not all(x["anchor_found"] for x in out.values()):
        raise SystemExit("One or more TradingView chains are not server-visible on runner")


if __name__ == "__main__":
    main()
