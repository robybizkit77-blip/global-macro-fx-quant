# Macro V2 — BLS intraday event evidence gate

**23 October 2026 · Research-only, no trading implication.**

The nine 2026 archived BLS U-3 first releases have verified values and official publication times. The project does **not** hold event-aligned consensus forecasts or licensed intraday observations before and after those release times for US Treasury 2Y, a single USD SOFR/OIS contract, or EUR/USD spot. Daily Treasury observations and ECB reference fixings from the previous audit cannot replace these observations.

## Required acquisition per release

- Pre-release economist survey consensus with actual survey close/publication time strictly before 08:30 New York, provenance and permission to use historical data.
- The *same Treasury 2Y instrument* from a licensed intraday source around 08:25 and 08:35 New York, with verified quote and instrument/venue identities.
- The *same OIS/SOFR instrument and tenor* before/after, not a daily SOFR fixing or unrelated futures expiry.
- EUR/USD spot before/after on the same venue, not the ECB reference fixing determined before the BLS announcement.

The module `validation/macro/v2_bls_intraday_evidence_gate_v1.py` creates nine deliberately empty event templates. It requires source and original timestamps, instrument identity, allowable five-minute checkpoints, source hash fields and licensing flags. **Those metadata fields are input assertions, not proof of entitlement, independent authentication, or economic validity.** Real procurement, spot checks of original records, precision/market-microstructure checks, additional-news controls and independent review are necessary before any causal/predictive study.

## Current coverage

**0/9 complete intraday event windows** in the repository. The available secondary weekly consensus calendar does not contain nine pre-release USD Labour forecast records. The existing OIS snapshot history begins after these releases. The test suite explicitly refuses an invented quote, a forged BLS release time, or a misleading complete/causal claim.

Even if all seven event fields were supplied later, one complete window would be only evidence of synchronized observations: causal claims, a backtest and live Macro/FX promotion would remain prohibited by independent research policy.

## Reproduce

```bash
python -m unittest validation.macro.test_v2_bls_intraday_evidence_gate_v1 -v
python -m validation.macro.v2_bls_intraday_evidence_gate_v1 \
  --json-out /tmp/macro-v2-shadow/event-evidence-gap.json
```

No report writes to `live_data/`, `site/`, `payload/`, `dashboard/`, the legacy 24 macro scores or the 28 pair views. The workflow is a **PR/manual-only** CI check, not a scheduled automation.
