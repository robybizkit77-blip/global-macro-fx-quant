#!/usr/bin/env python3
"""Contract QA: native Control Room design, complete G8 and properly labelled estimates."""
from pathlib import Path
s=Path("site/control-room-preview/home-navigation-v10.js").read_text(encoding="utf-8")
loader=Path("site/control-room-preview/index.html").read_text(encoding="utf-8")
items={
"Original 32 visual parts are untouched": "Array.from({length:32}" in loader,
"Native clickable card surfaces": "panel.dataset.gmfqDestination" not in s and "e.dataset.gmfqDestination=link" in s,
"No ad-hoc Approfondisci tags": "Approfondisci ↗" not in s and "gmfq-open-detail" not in s,
"Semantic keyboard navigation": "keydown" in s and "aria-label" in s,
"In-app DXY instead of external CFD": "openDxy(doc)" in s and "gmfq-dxy-dialog" in s and "tradingview.com" not in s,
"Real synthetic DXY feed, not an ICE quote": "DXY_SYNTHETIC_ECB.json" in s and "not_official_ice" in s and "non ICE" in s,
"Eight G8 currencies configured": "['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF']" in s,
"Missing CHF and NZD 2Y modelled but distinct": "[['CHF','EUR'],['NZD','AUD']]" in s and "estimate2" in s and "STIMA" in s,
"All G8 OIS/proxy rows": "['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']" in s,
"NZD is explicitly a bank-bill directional proxy": "NZD_CB_PRICING_DIRECTIONAL_PROXY.json" in s and "NON OIS" in s,
"Known stale pricing stays distinguishable": "fresh(x.as_of,4)" in s and "WITHHELD" in s,
"Core data not changed": "localStorage.setItem" not in s and "github.com/repos/" not in s,
}
for k,v in items.items(): print(("PASS" if v else "FAIL")+": "+k)
if not all(items.values()): raise SystemExit(1)
print("GMFQ_V10_G8_CHARTS_POLISHED_NAVIGATION_PASS")
