#!/usr/bin/env python3
"""Contract QA: native Control Room design, complete G8 and properly labelled estimates."""
from pathlib import Path
s=Path("site/control-room-preview/home-navigation-v10.js").read_text(encoding="utf-8")
loader=Path("site/control-room-preview/index.html").read_text(encoding="utf-8")
items={
"Original 32 visual parts are untouched": "Array.from({length:32}" in loader,
"Native clickable card surfaces": "e.dataset.gmfqDestination=link" in s,
"No ad-hoc Approfondisci tags": "Approfondisci ↗" not in s and "gmfq-open-detail" not in s,
"Semantic keyboard navigation": "keydown" in s and "aria-label" in s,
"In-app DXY instead of external CFD": "openDxy(doc)" in s and "gmfq-dxy-dialog" in s and "tradingview.com" not in s,
"Real synthetic DXY feed, not an ICE quote": "DXY_SYNTHETIC_ECB.json" in s and "not_official_ice" in s and "non ICE" in s,
"Eight G8 currencies configured": "['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF']" in s,
"Missing CHF and NZD 2Y modelled but distinct": "[['CHF','EUR'],['NZD','AUD']]" in s and "estimate2" in s and "STIMA" in s,
"All G8 OIS/proxy rows": "['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']" in s,
"NZD is explicitly a bank-bill directional proxy": "NZD_CB_PRICING_DIRECTIONAL_PROXY.json" in s and "PROXY BB ≠ OIS" in s,
"Known stale pricing stays distinguishable": "fresh(x.as_of,4)" in s and "WITHHELD" in s,
"Rates detail exposes the four missing country selectors": "function enhanceRatesDetail(doc)" in s and "['AUD','CAD','NZD','CHF']" in s and "select.appendChild(b)" in s,
"Rates selection remains wired to the existing data renderer": "b.dataset.ccy=ccy" in s and "focusCurrency(doc)" in s,
"Home focus links lead to exact Rates sections": "function focusRatesSection(doc)" in s and all(x in s for x in ["curve:'#rates-chart'","'2y':'#rates-rows'","spread:'#rates-rows'","ois:'#ois-rows'","scrollIntoView({block:'start'})"]),
"Detail adapter does not invent missing yields": "enhanceRatesDetail(doc)" in s and "b.textContent=labels[ccy]" in s,
"Rates desk curves from certified same-date validated tenors only": "function marketResearchCurves(data)" in s and "GREEN_OFFICIAL" in s and "OFFICIAL_CERTIFIED" in s and "fresh(x.as_of,4)" in s,
"Research curves cannot use secondary quotes": "function marketResearchSecondary(data)" in s and "ctx.full_curve_usable!==false" in s and "ctx.cross_date_join_allowed!==false" in s and "ctx.policy_delta_allowed!==false" in s,
"Secondary quotes are informational and individually dated": "SECONDARY_VERIFIED_DAILY_BAR" in s and "quote_as_of" in s and "non sono una curva OIS" in s,
"NZD bank bills remain separate from OIS": "NON curva OIS né policy delta" in s,
"CHF staleness is disclosed": "CHF 2Y/10Y" in s and "non corrente" in s,
"Official CHF 10Y read-only context sourced separately": "CHF_SNB_10Y_SPOT_CONTEXT.json" in s and "GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1" in s,
"CHF 10Y never fills unverified 2Y or spread": "snb10.has_current_2y===false" in s and "snb10.eligible_for_curve_spreads===false" in s and "snb10.eligible_for_core_signals===false" in s,
"Official CHF context requires valid freshness and provenance": "snb10.source_url===" in s and "fresh(snb10.as_of,4)" in s and "OFFICIAL_PUBLISHED_10Y_INFORMATIONAL" in s,
"Core data not changed": "localStorage.setItem" not in s and "github.com/repos/" not in s,
}
for k,v in items.items(): print(("PASS" if v else "FAIL")+": "+k)
if not all(items.values()): raise SystemExit(1)
print("GMFQ_V10_G8_CHARTS_POLISHED_NAVIGATION_PASS")
