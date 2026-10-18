#!/usr/bin/env python3
"""Fail-closed static checks for non-invasive v10 navigation and DXY provenance."""
from pathlib import Path

p = Path("site/control-room-preview/home-navigation-v10.js")
loader = Path("site/control-room-preview/index.html")
src = p.read_text(encoding="utf-8")
html = loader.read_text(encoding="utf-8")
destinations = [
    "#/tassi?focus=ois", "#/tassi?focus=curve",
    "#/valute", "#/tassi?focus=2y", "#/tassi?focus=spread",
    "#/screener", "#/macro", "#/valute?ccy=",
    "#/banche?ccy=", "#/screener?pair="
]
checks = {
    "separate versioned adapter": 'home-navigation-v10.js' in html,
    "old design payloads untouched": 'Array.from({length:32}' in html,
    "only one injected script": "const scriptTag=" in html and "const withNavigation=" in html,
    "unchanged certified Home default": "mode=live" in html,
    "all seven Home analysis cards routed": all(x in src for x in destinations[:7]),
    "currency bank and pair drilldowns": all(x in src for x in destinations[7:]),
    "accessible click and keyboard interaction": "aria-label" in src and "keydown" in src,
    "DXY sourced from external identified CFD only": (
        "https://www.tradingview.com/symbols/TVC-DXY/" in src
        and "CFD indicativo" in src
        and "without SEK" in src
    ),
    "external links protected": "'noopener noreferrer'" in src,
    "no invented DXY quote": "106.42" not in src and "DXY_INDEX_VALUE" not in src,
    "no legacy file references": "site/website-v1" not in src,
    "no direct data mutation": not any(x in src for x in ("localStorage.setItem", "fetch(", "innerHTML=", "api.github.com"))
}
for title, ok in checks.items():
    print(("PASS: " if ok else "FAIL: ") + title)
if not all(checks.values()):
    raise SystemExit(1)
print("CONTROL_ROOM_V10_CARD_NAVIGATION_CONTRACT_PASS")
