# Official event clock and market data rights readiness — EUR/USD pilot

**Audit as of 25 October 2026. Research only; no licensed intraday dataset has been added.**

## Source terms update — 25 October 2026

**Dukascopy:** https://www.dukascopy.com/swiss/english/legal-pages/terms-of-use/
Sections 3/4 describe website materials as personal non-commercial use except written agreement, prohibit automated robots/scraping without prior express written consent, and restrict database creation and redistribution. The [historical export page](https://www.dukascopy.com/swiss/english/marketwatch/historical/) says that downloads are free and may support backtests, but **free availability does not override these website Terms of Use**. The separate legal applicability of these conditions to direct BI5 endpoints must be clarified with Dukascopy in writing. Pending that clarification: **all direct automated Dukascopy downloads in our repository are disabled**. We do not claim permission has been obtained.

**CME DataMine:** The [official dataset FAQ](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457319709/CME+DataMine+Support) differentiates EOD/Time & Sales from BBO/Market Depth external redistribution: historical EOD/T&S may be distributed with vendor registration, while BBO/MD external redistribution is restricted. [Historical-data distribution guidance](https://www.cmegroup.com/market-data/distributor/files/cme-group-data-licensing-policy-guidelines-historical-information-distribution.pdf) and the particular data license govern access, end-user rights, website display and downloads. **The FAQ is not itself our license**. A [CME SR3 T&S catalog listing](https://datamine.new.cmegroup.com/catalog/dataset/86e3685d5cf1a886dc98baa696357cfe) is a commercial option; it does not certify that any historical quote has been purchased.

The immediate action is to request written answers from the providers concerning private systematic research, scheduled acquisition/API, keeping raw tick quotes, converting to public derived statistics, dashboard display, and possible commercial publication. **No purchase or data transfer should be initiated based only on a catalogue entry.**

## One official event clock we can ground

The BLS archived September 2026 Employment Situation:
https://www.bls.gov/news.release/archives/empsit_10022026.htm

Its own archived header reports `USDL-26-1549`, embargoed until **Friday 2 October 2026, 08:30 Eastern Time**. The date was in US daylight saving time (EDT, UTC−4), so the **scheduled** cutoff equals **2026-10-02T12:30:00Z**. `validation/news_event_source_readiness_gate_v1.py` validates the calendar/zone transform.

**Important:** a timestamp in an archived release header means a scheduled embargo, *not* an independently recorded first transmission to traders. No first-public-delivery receipt has been obtained, so this does not certify millisecond-level event timing.

## Independent market source inventory (candidate ≠ entitlement)

| Market layer | Market source | Evidence | Current availability | Missing proof |
| --- | --- | --- | --- | --- |
| EUR/USD spot | Dukascopy historical BI5 | Existing one-hour network test, PR #573 | Transport probe only | Explicit usage/publication authorization, permission to retain source bytes, independent quote reprobe |
| USD front-end proxy | CME DataMine SR3 Three-Month SOFR futures Time & Sales | Product catalogue: https://datamine.new.cmegroup.com/catalog/dataset/86e3685d5cf1a886dc98baa696357cfe | Listed, not acquired | Executed market-data entitlement, specific contract, timestamped pre/post prices, conversion methodology |
| Treasury cash benchmark | CME BrokerTec two-year U.S. Treasury book | Publisher product reference: https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457421032 | Listed, not acquired | Executed license, on-the-run/off-the-run security, quote/yield conversion, timestamped pre/post |
| FX alternative | CME DataMine EBS Spot FX | CME historical cash markets: https://www.cmegroup.com/datamine.html | Listed, not acquired | Access and rights to analyse/distribute observations |

CME DataMine describes access via ordering/purchasing historical datasets, with conditions in its Information License Agreement. Catalogue listings alone do not establish research, display or redistribution rights. See https://www.cmegroup.com/market-data/files/information-license-agreement.pdf and https://www.cmegroup.com/market-data/distributor/files/cme-group-data-licensing-policy-guidelines-historical-information-distribution.pdf.

**Instrument interpretation:** the SR3 *futures* curve is not the USD OIS curve. Changes in the three-month SOFR futures contract may be studied as a front-end proxy, with correct contract identification and convexity/basis caveats; never relabel as an observed OIS quote. BrokerTec's Treasury book quotes are security-specific market prices, not automatically an interpolated, generic official 2-year benchmark yield.

## Conservative release gate

```bash
python -m unittest validation.test_news_event_source_readiness_gate_v1 -v
python -m validation.news_event_source_readiness_gate_v1 --out /tmp/gmfq-news-source-readiness.json
```

The emitted receipt must always remain **BLOCKED_NOT_CERTIFIED** while rights, actual delivery time, permitted raw quotes, matched contract and competing-event checks are incomplete. It explicitly protects production scoring, backtesting, 28 pair ranking, Beta/Forward Test, News Pulse, active Preview, data schedules and alert automations.

The register is intentionally **not** an entitlement authorisation record. An operator cannot switch `commercial_use_rights` to `GRANTED` or set `first_public_delivery_receipt` and thereby bypass review: current code throws an error rather than claiming certification. Any future promotion requires a separate code-reviewed trust workflow with independently checkable evidence and an updated CI methodology.

## Subsequent target, not yet accomplished

Obtain a rights-cleared historical instrument at the same event and re-hash the permitted raw data; verify publication timing from a verifiable public-transmission receipt or clearly restrict claims to the embargo clock; compare separately aligned rates and FX windows; test whether there was a competing headline. Only then consider an **observed reaction** flag. Causal attribution will still require additional identification work.

No webpages or market ticks are retrieved by this registry or CI. This is not a proof of any actual measured EUR/USD market reaction.
