# NZD Bank Bill proxy — empirical cash-carry calibration (21 October 2026)

**Status:** `RESEARCH_ONLY`. A usable, approximate, explicitly uncertain model for the user's private research; it is **not** an observed Bills/OIS market basis, spot OIS curve, market-implied OCR, forecast confidence interval or trade signal.

## Public data and historical anchor

The RBNZ's public [Exchange and Wholesale Interest Rates](https://www.rbnz.govt.nz/statistics/key-statistics/exchange-rates-and-wholesale-interest-rates) page lists the **monthly average** 90-day bank bill yield and **end-of-month** Official Cash Rate (OCR). Historical figures were manually checked on 21 October 2026 and preserved in `NZD_BB_CASH_RESEARCH_CALIBRATION_V1_2026-10-21.json`.

1. **Reference OCR plateau**: June 2023–June 2024, OCR 5.50%, 13 monthly bank-bill averages (5.62–5.71%). The median observed gap `90d bill − OCR` is **14.0 bp**.
2. **More recent OCR plateau**: January–June 2026, OCR 2.25%, 6 monthly averages (2.49–2.68%). The median gap is **28.5 bp**.
3. Apply a deliberately simple regime weighting: **30% historical + 70% recent**, yielding **24.15 bp**, rounded to **24 bp**. This is an analytical choice to emphasize current conditions, not an optimized backtest.
4. Define an easy-to-audit descriptive envelope as the smallest and largest *observed* monthly gaps from those windows (12 to 43 bp), padded by 2 bp: **10–45 bp** for the *original pre-holdout training-only interval*. This is **NOT** a statistical confidence interval or a prediction of future basis. Out-of-window 2026 July–September policy transitions were excluded rather than blended into stable-OCR regimes; the exclusion is a judgment call.

Source terminology note: [NZFBF distinguishes OCR-based overnight indexed swaps (NZOS)](https://www.nzfbf.co.nz/benchmarks/closing-rates/) from `NZBO` Bills/OIS basis closing mid-rates. The RBNZ table does **not** contain NZBO observations. Moreover, the RBNZ figure is a monthly-average bill rate against **month-end** OCR, so historical gaps can capture **rate expectations, intra-month OCR changes and credit/liquidity premia**. They are not isolated credit spread estimates.

## Application to existing official ASX futures proxies

The existing `NZD_CB_PRICING_DIRECTIONAL_PROXY.json` contains **ASX-listed NZ 90-day bank bill contracts** selected by closest expiry to today+90/180/365 days. They are NOT spot-duration instruments or a continuously compounded OIS 3M/6M/12M curve.

For each individually dated selected future (quote rate `r_BB` in %), calculate:

- **Central indicative scenario** = `r_BB − 0.24%` (24 bp).
- **Revised illustrative range** = `[r_BB − 0.50%, r_BB − 0.10%]`. The additional 5bp on the upper basis side reflects a held-out adverse month; this interval was revised after reviewing the holdout and has **no independent predictive coverage test**.
- Round displayed percentages to two decimals; retain the actual ASX quote as-of.
- The exact same carry is applied to each future's reference quarter as an acknowledged approximation; no bootstrapping, day-count transformation, cross-contract interpolation, policy meeting decomposition or risk-neutral probabilities.

Example from **20 October 2026 ASX snapshot**, if unaltered:

| Approximate expiry target | Selected BB contract expiry | Bank bill futures implied (%) | Empirical scenario (%) | Illustrative envelope (%) |
|---|---|---:|---:|---:|
| 3M label | 16 Dec 2026 | 3.49 | **3.25** | 2.99–3.39 |
| 6M label | 10 Mar 2027 | 3.83 | **3.59** | 3.33–3.73 |
| 12M label | 15 Sep 2027 | 4.24 | **4.00** | 3.74–4.14 |

These are rate-like **proxy scenarios**, not actual OIS quotes. If the underlying ASX snapshot goes stale or loses maturity/identity metadata, the UI returns `WITHHELD`; a static example in this note never becomes a live rate.



## October 21 check: three untouched months and error diagnostics

The July, August and September 2026 monthly observations from the same [official RBNZ chart](https://www.rbnz.govt.nz/statistics/key-statistics/exchange-rates-and-wholesale-interest-rates) were **not used to choose the original 24bp point estimate**:

| Observation | OCR end-of-month | 90d bank bill monthly average | Observed cash-gap (bp) | Central 24bp error |
|---|---:|---:|---:|---:|
| Jul 2026 | 2.50% | 2.85% | 35 | 11bp |
| Aug 2026 | 2.50% | 2.98% | 48 | 24bp |
| Sep 2026 | 2.75% | 3.13% | 38 | 14bp |

**MAE = 16.33bp**, maximum absolute error = 24bp. The original 10–45bp illustrative basis band included two of three observations; August at 48bp exceeded it. A widened **10–50bp sensitivity band** now includes three of three, but because it was *chosen after seeing this check*, **3/3 is not independent out-of-sample predictive coverage**. This limited test assesses the RBNZ bank-bill-minus-OCR cash gap, **not** the unobserved Bills/OIS swap basis or future quarterly futures errors.

The 24bp central estimate and both 30/70 reference weights are unchanged. We have not optimized on holdout results, and we do not infer a standard deviation or confidence level from just three test months. A future independent set of later observations must be kept separate if assessing the revised 10–50bp envelope.

### Conservative operating rule

One value per tenor is a dated **ASX Bank Bill contract** adjusted by a simple common basis assumption. That adjustment is a research aid, not a precise market OIS rate. Underlying ASX source freshness/maturity/status guards still fail closed; no inferred daily OIS curve, central bank repricing, FX signals or new Macro scores are generated.

## What changes and what stays protected

Changes are restricted to the research-only 3M/6M/12M Rates view, a non-operative Home disclosure, auditable provenance, and static/browser QA checks. The House label stays `4/8 certified + 4/8 other context` while sources remain current; numeric values may change with ASX updates, but the calibration coefficient is fixed until a separately approved review.

**No** changes to core `OIS_DATA`, source `OIS_OPERATIONAL_VIEW`, `NZD_CB_PRICING_DIRECTIONAL_PROXY`, macro scores, FX pair ranks, trade bias, entry/stop, alert schedules, official source tags, 1D/1W official policy repricing or backtest eligibility.

## Later improvements (optional)

When feasible, calculate a moving monthly RBNZ B2 basis using a larger history, avoid month-average vs end-month misalignment, examine stable OCR quarters separately, and validate against actual licensed NZBO/NZOS closes. Until then mark **method confidence C, directional research only**.

The model can be economically useful despite approximation; its uncertainty is conspicuous and cannot trigger trades.
