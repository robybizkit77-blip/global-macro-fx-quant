# USD · EUR · CHF futures: quote and tenor-quality audit

**2026-10-21 · read-only research overlay, NOT OIS curve calibration.**

## What can be verified
The exchange specifications for the relevant futures use the quote convention **100 minus the numerical interest rate**:

- USD: CBOT 30-Day Federal Funds ZQ — CME's official settlement methodology: https://www.cmegroup.com/market-data/settlements/files/30-day-fed-fund-futures-daily-settlement-procedure.pdf
- EUR: Eurex FST3 Three-Month €STR — https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures/estr/Three-Month-Euro-STR-Futures-3402480
- CHF: ICE SA3 Three-Month SARON — https://www.ice.com/products/72270612/Three-Month-Saron-Index-Futures-Contract/specs

The project stores **secondary TradingView public contract-page observations**, *not direct current official exchange clearing settlement feed or an actual OIS swap curve*. A correct `100 − contract price` transformation is necessary but **not sufficient** to establish source rights, contract-level daily repricing or predictive validity.

## Reconciliation against the real dated observations held in the repo

As viewed **21 October 2026**; source quotes carry their own observation dates.

| Currency | Label | Contract | Quote as-of | Fut price | Rate = 100 − price | Expiry | Gap to today + label |
|---|---|---|---|---:|---:|---|---:|
| USD | 3M | ZQZ2026 | 2026-10-20 | 95.930 | 4.070% | 2027-01-04 | −15 days |
| USD | 6M | ZQJ2027 | 2026-10-20 | 95.560 | 4.440% | 2027-05-03 | +14 days |
| USD | 12M | ZQV2027 | 2026-10-20 | 95.315 | 4.685% | 2027-11-01 | +11 days |
| EUR | 3M | FST3V2026 | 2026-10-19 | 97.465 | 2.535% | 2027-01-20 | +1 day |
| EUR | 6M | FST3G2027 | 2026-10-19 | 97.105 | 2.895% | 2027-05-19 | +30 days |
| EUR | 12M | FST3M2027 | 2026-10-20 | 96.900 | 3.100% | 2027-09-15 | −36 days |
| CHF | 3M | SA3U2026 | 2026-10-20 | 100.0475 | −0.0475% | 2026-12-15 | −35 days |
| CHF | 6M | SA3Z2026 | 2026-10-20 | 99.990 | 0.010% | 2027-03-16 | −34 days |
| CHF | 12M | SA3M2027 | 2026-10-20 | 99.665 | 0.335% | 2027-09-14 | −37 days |

**Important:** "Gap" is a calendar deviation between the listed contract's **expiry** and an illustrative today+90/180/365 day target. This does **not** measure the actual interest accrual period or tenor of an OIS swap. In particular ZQ is a monthly average futures product, while FST3 and SA3 reference distinct three-month **forward accrual windows**. Calendar proximity cannot make them mathematically fungible or a continuous 3M/6M/12M OIS curve.

## Implemented rules

The existing research-only `site/control-room-preview/ois-pricing-estimates-v1.js` now shows a dated indicative observation only if:

- `futures_price` is finite; implied `100 − futures_price` agrees with the displayed rate to **0.02 bp**; the originally verified daily-bar timestamp and the displayed tenor's `quote_as_of` agree.
- Exchange ticker, expiry and documented nearest-dated-contract selection identity agree exactly (CBOT:ZQ, EUREX:FST3, ICEEUR:SA3; no continuous contract).
- Expiration is not past, source data are no more than **five calendar days old**, and the expiry deviates by at most **45 calendar days** from the approximate tenor target.
- Each EUR secondary observation agrees with its source contract price, symbol, and source date. **Different EUR trading dates remain visibly different**; cannot join in an official synchronized curve.
- All failures are **WITHHELD for that point**, never replaced by a guessed numeric quote. Show expiry gap beside each accepted estimated observation. A single valid point never qualifies as 3/3 G8 Home coverage.

The thresholds above are **engineering guardrails**, not statistical calibration confidence intervals.

## What we cannot calibrate from the current files

`validation/cb_pricing/history/OIS_ESTIMATED_SNAPSHOTS_V1.jsonl` includes earlier estimated 3/6/12M *values*, but its historical records lack the individual **dated contract identifiers, exchange release dates and contract-to-contract continuity** necessary for an apples-to-apples T/T−1/T−5 comparison. Cross-date or rolling-contract snapshot changes are not a reliable measure of OIS repricing.

Therefore, unlike the separately calibrated NZD cash-carry scenario, **no additive numerical correction** is applied to USD/EUR/CHF futures; no claim is made of a verified futures–OIS basis, surprise-to-policy link, statistical interval, or predictive trading advantage. More precision would require genuinely matched same-contract official history and separate rights.

## Hard invariants

No direct changes to `live_data`, `OIS_DATA`, the production collector or its scheduled workflows, the 24 Legacy Macro scores, 8 cycles, 28 FX pairs, thesis/bias/size, active visual design, or historical releases. The G8 research panel remains **non-operative**; `policy_repricing_allowed=false`, `core_score_effect=NONE`, `backtest_official=false`.

All evidence is an audit of the repo's **existing** secondary quotes and public product conventions as of 2026-10-21, not fresh exchange retrieval or a new historical data licence.
