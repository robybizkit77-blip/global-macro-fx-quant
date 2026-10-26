# Beta FX vs 2Y — 52W historical shadow pseudo-OOS (26 October 2026)

**Purpose:** advance the PDF `Il beta dalla A alla Z` chapter 23.3 and 23.4 requirements without pretending to possess real historical *first-release* point-in-time (PIT) vintages or a reliable strategy edge.

## What was really built

Inputs are the repository's already-available official FX reference history `live_data/sections/ECB_G8_PRICE_HISTORY.json` (ECB daily EUR-base fixings) and `live_data/sections/NATIVE_RATES_DATA.json` (currency-specific **2Y government yield** history, with distinct benchmark definitions). The 28 unique G8 pairs are generated as FX cross `FX_quote/EUR ÷ FX_base/EUR`. For each currency pair, dates used for FX and both 2Y yields must be **identical actual observation dates**; the latest triple-matched weekday in each ISO Monday–Friday week is used as a single weekly anchor. Neither forward fill nor assumed observation dates is permitted; full missing weeks never become a spurious weekly change.

- `y_t` = simple FX weekly return `P_t/P_(t−1) - 1` (quote currency per base currency).
- `x_t` = weekly change in the **base-minus-quote** 2Y yield differential, in **percentage points**: `(Y_base-Y_quote)_t - (Y_base-Y_quote)_(t−1)`.
- Estimator = **same unmodified 52-sample OLS with intercept** in `validation/beta/rate_beta_observational_v1.py`.
- For each eligible later observed week `t`, estimate `beta` strictly from 52 prior weekly pairs; the evaluation week's own x/y never enters training.
- Require contiguous consecutive weeks for the full training panel and the next held-out week. If a week is absent, do not bridge; cannot use a rolling window that disguises missing calendar time.
- With enough held-out observations, calculate the PDF's chapter 23.4 variance-reduction *diagnostic*: `1 - Var(y_t - beta_(t-1) x_t) / Var(y_t)`. **Four held-out weeks is only the minimum needed to display a descriptive diagnostic, NOT a statistical proof**, validation, tradable hedge, transaction-cost-adjusted edge or deployment threshold.

## Significant detected real-data problems

- **JPY 2Y** historical `history2.dates`: 246 entries are not strict `YYYY-MM-DD` and 30 inversions occur when the dates are normalized. This is not just a formatting cosmetic: index and date mapping need an independent source-specific chronology audit. The present shadow module **quarantines all seven JPY pairs**, rather than silently re-sorting or interpolating inputs.
- **CHF** reported 2Y observation ends **2026-09-30**, and **NZD** ends **2026-10-16** (current repository snapshots at audit); therefore a historical trial can run only through available original observations. A non-current historical sample is **never called today's rate**.
- **EUR** 2Y is an ECB AAA zero-coupon Svensson curve; **USD** is a Treasury par-yield curve; **GBP** uses a UK nominal zero-coupon curve; **CAD** benchmark GC 2Y, etc. These are *not the same underlying instrument/curve convention*. The script does not certify like-for-like yield-basis comparability.
- Source histories may contain **revised/latest** values rather than *what was first published by the release timestamp*. Observations being dated by day is not enough for true PIT. This is historical **pseudo-OOS** only, not an actual real-time Forward Test or proof of a profitable predictive model.

## Governance

**No promotion.** All outputs are explicitly marked `SHADOW_HISTORICAL_PSEUDO_OOS_NOT_LIVE`, `historical_point_in_time_vintages_verified=false`, `yield_instrument_basis_comparable_across_countries=false`, `b1_b2_rule_validated=false`, `beta_promoted=false`, `trading_performance_claim=false`.

No modification to original Beta 52W estimator contract, Core, ranking, 28 pairs, trade signals, price feeds, dashboard, original Beta, actual Forward Test snapshots or outcome journals. CI runs only on PR/manual trigger. Shadow receipt remains under `/tmp` and is not published as a scored live feed. PDF B1/B2 preregistered definitions remain **unavailable**; do not guess rules or cutoffs.

## How to repeat

```bash
python -m unittest validation.beta.test_weekly_fx_2y_shadow_oos_v1 -v
python -m validation.beta.weekly_fx_2y_shadow_oos_v1 \
  --as-of 2026-10-26 \
  --out /tmp/gmfq-beta-fx-2y-weekly-shadow.json
```

## True Beta launch blockers

1. Repair JPY 2Y historical date identity/chronology **against original Ministry of Finance records** and freeze correct historical series, without guessing.
2. Review rates instrument definition comparability / test matched yield basis or specify why relative benchmark spread is economically valid for this chosen Beta use case.
3. Ensure publication-**vintage PIT** and measurement clock evidence for all 52 training inputs and held-out observations (or explicitly keep the model *research-only*).
4. Build robust-standard-error / outlier and estimator-stability diagnostics and justify optional methods from PDF 23.3.
5. Expand historical genuinely held-out sample and evaluate OOS variance reduction uncertainty. If source data cannot supply it, never interpret a handful of historical weeks as statistical significance.
6. Recover original **B1/B2** rules from their canonical specification; do not invent thresholds.

This completes the first real-data OOS *method implementation* and identifies source blockers. It does not complete full Beta certification.
