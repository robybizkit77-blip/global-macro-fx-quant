# NZD Bank Bill proxy — empirical cash-carry calibration (21 October 2026)

**Status:** `RESEARCH_ONLY`. A usable, approximate, explicitly uncertain model for the user's private research; it is **not** an observed Bills/OIS market basis, spot OIS curve, market-implied OCR, forecast confidence interval or trade signal.

## Public data and historical anchor

The RBNZ's public [Exchange and Wholesale Interest Rates](https://www.rbnz.govt.nz/statistics/key-statistics/exchange-rates-and-wholesale-interest-rates) page lists the **monthly average** 90-day bank bill yield and **end-of-month** Official Cash Rate (OCR). Historical figures were manually checked on 21 October 2026 and preserved in `NZD_BB_CASH_RESEARCH_CALIBRATION_V1_2026-10-21.json`.

1. **Reference OCR plateau**: June 2023–June 2024, OCR 5.50%, 13 monthly bank-bill averages (5.62–5.71%). The median observed gap `90d bill − OCR` is **14.0 bp**.
2. **More recent OCR plateau**: January–June 2026, OCR 2.25%, 6 monthly averages (2.49–2.68%). The median gap is **28.5 bp**.
3. Apply a deliberately simple regime weighting: **30% historical + 70% recent**, yielding **24.15 bp**, rounded to **24 bp**. This is an analytical choice to emphasize current conditions, not an optimized backtest.
4. Define an easy-to-audit descriptive envelope as the smallest and largest *observed* monthly gaps from those windows (12 to 43 bp), padded by 2 bp: **10–45 bp**. This is **NOT** a statistical confidence interval or a prediction of future basis. Out-of-window 2026 July–September policy transitions were excluded rather than blended into stable-OCR regimes; the exclusion is a judgment call.

Source terminology note: [NZFBF distinguishes OCR-based overnight indexed swaps (NZOS)](https://www.nzfbf.co.nz/benchmarks/closing-rates/) from `NZBO` Bills/OIS basis closing mid-rates. The RBNZ table does **not** contain NZBO observations. Moreover, the RBNZ figure is a monthly-average bill rate against **month-end** OCR, so historical gaps can capture **rate expectations, intra-month OCR changes and credit/liquidity premia**. They are not isolated credit spread estimates.

## Application to existing official ASX futures proxies

The existing `NZD_CB_PRICING_DIRECTIONAL_PROXY.json` contains **ASX-listed NZ 90-day bank bill contracts** selected by closest expiry to today+90/180/365 days. They are NOT spot-duration instruments or a continuously compounded OIS 3M/6M/12M curve.

For each individually dated selected future (quote rate `r_BB` in %), calculate:

- **Central indicative scenario** = `r_BB − 0.24%` (24 bp).
- **Illustrative range** = `[r_BB − 0.45%, r_BB − 0.10%]`.
- Round displayed percentages to two decimals; retain the actual ASX quote as-of.
- The exact same carry is applied to each future's reference quarter as an acknowledged approximation; no bootstrapping, day-count transformation, cross-contract interpolation, policy meeting decomposition or risk-neutral probabilities.

Example from **20 October 2026 ASX snapshot**, if unaltered:

| Approximate expiry target | Selected BB contract expiry | Bank bill futures implied (%) | Empirical scenario (%) | Illustrative envelope (%) |
|---|---|---:|---:|---:|
| 3M label | 16 Dec 2026 | 3.49 | **3.25** | 3.04–3.39 |
| 6M label | 10 Mar 2027 | 3.83 | **3.59** | 3.38–3.73 |
| 12M label | 15 Sep 2027 | 4.24 | **4.00** | 3.79–4.14 |

These are rate-like **proxy scenarios**, not actual OIS quotes. If the underlying ASX snapshot goes stale or loses maturity/identity metadata, the UI returns `WITHHELD`; a static example in this note never becomes a live rate.

## What changes and what stays protected

Changes are restricted to the research-only 3M/6M/12M Rates view, a non-operative Home disclosure, auditable provenance, and static/browser QA checks. The House label stays `4/8 certified + 4/8 other context` while sources remain current; numeric values may change with ASX updates, but the calibration coefficient is fixed until a separately approved review.

**No** changes to core `OIS_DATA`, source `OIS_OPERATIONAL_VIEW`, `NZD_CB_PRICING_DIRECTIONAL_PROXY`, macro scores, FX pair ranks, trade bias, entry/stop, alert schedules, official source tags, 1D/1W official policy repricing or backtest eligibility.

## Later improvements (optional)

When feasible, calculate a moving monthly RBNZ B2 basis using a larger history, avoid month-average vs end-month misalignment, examine stable OCR quarters separately, and validate against actual licensed NZBO/NZOS closes. Until then mark **method confidence C, directional research only**.

The model can be economically useful despite approximation; its uncertainty is conspicuous and cannot trigger trades.
