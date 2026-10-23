# Macro V2 — Evidence acquisition gate: USD Labour → 2Y / OIS / EURUSD

As of 23 October 2026. **Nine BLS releases, zero complete timestamp-synchronized event windows in the current repository.** This is a source-access audit, not a failed trading signal.

## Data contract
Each event requires original 08:30 NY BLS first-release value, economist consensus timestamped **before** release, Treasury 2Y from the same instrument at 08:25/08:35, USD SOFR OIS of the same contract at 08:25/08:35, and EUR/USD from the same venue and quoting convention at 08:25/08:35. A quote more than 2 minutes away from its target snapshot is rejected. Provenance includes source URL, SHA-256 of archived bytes, verified observation timestamp and authorization to use the dataset.

The existing daily Treasury yields and ECB fixings **cannot** fill intraday slots. Existing October 2026 OIS/futures history **cannot** be backdated to BLS events from February to October 2. The project's current Forex Factory weekly forecast feed has no synchronized historical unemployment-consensus values for those releases.

## Acquisition channels to investigate
- **Economist-survey history:** licensed Bloomberg, Reuters, LSEG, Econoday or comparable event-specific survey history, preserving survey cutoff and redistribution rights. Do not use BLS previous figures as consensus.
- **Treasury intraday:** CME [DataMine](https://www.cmegroup.com/datamine.html) BrokerTec/GovPX products, with instrument identity and date-specific permission verified.
- **Spot FX intraday:** CME DataMine EBS Spot FX or similarly timestamped venue data.
- **USD SOFR OIS:** historical OTC same-tenor swaps (qualified licensed sources). Futures are *not* OIS and daily Term SOFR is not an 08:25/08:35 OIS quote.

Even complete prices and survey consensus cannot alone certify a causal link, predictive trading edge, or OOS performance. Market release co-timing, liquidity and dealer quality must be investigated separately.

## Control
`validation/macro/v2_bls_intraday_evidence_gate_v1.py` builds nine blank rows with seven required evidence slots each and strictly validates quoted timestamp, instrument identity, venue, licensed rights, and source-byte hashes. No fabricated fill values. Results live under `/tmp` only. Live scoring, D.json, pair theses and backtests remain blocked. This does **not** create any automation.

```bash
python -m unittest validation.macro.test_v2_bls_intraday_evidence_gate_v1 -v
python -m validation.macro.v2_bls_intraday_evidence_gate_v1 --json-out /tmp/macro-v2-shadow/event-evidence-gap.json
```
